#!/usr/bin/env python3
"""Add and update manufacturers from OSHA's establishment-specific injury and illness data (Form 300A).

    python3 scripts/import_osha.py ITA_300A_Summary_Data_2025_through_08-31-2026.csv   # or the .zip
    python3 scripts/import_osha.py FILE --dry-run                                       # report only
    python3 scripts/import_osha.py FILE --geocache cache.json                           # reuse earlier geocodes

Download the latest "300A Summary Data" file by hand from
https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data (OSHA's site turns away scripts,
and the data changes once a year: establishments file by March 2 for the previous calendar year).
Establishments with 20 or more employees in manufacturing must file, so this covers most plants of
that size, though not every establishment that should file does. It is public data from the U.S.
Department of Labor.

What the script does:
- keeps establishments in Indiana or Michigan with a NAICS 31-33 code whose ZIP code lies mostly in
  one of the region's counties (data/region_zips.json, from the Census ZIP-county relationship file);
- matches each to a company file by its OSHA establishment ID (`osha_id`, written on the first
  match), then by street number, street name and city, then by normalized name and city;
- when the match is by address only and the names share no word, the filer is a successor, a renamed
  company or a new tenant, and it is the plant at that address now. An imported (HIFLD) file is
  rewritten to the filer: name, NAICS, products, sector and headcount from OSHA, the old name kept in
  `formerly`, the old website dropped, and a `status_note` saying so. A hand-written file only gets
  `osha_occupant` (the filer's name) for a person to review;
- a same-name filing brings back a file marked `presumed_closed`;
- on a match, writes `osha_id`, and replaces the headcount with OSHA's annual average employees when
  the file's headcount is an estimate (such as HIFLD's) or missing; reported headcounts stay;
- otherwise geocodes the address with the Census geocoder, checks that it falls in a region county
  and writes a new company file, named <company>--<city>--<street number>.toml;
- a headcount repeated at several addresses of one company is company-wide, not a plant's: it goes on
  one file only, with employees_scope = "company"; departments filed at one address keep the largest;
- writes data/osha.json: the filing year and every regional establishment with its company file,
  so a plant missing from the next year's file can be flagged for review (scripts/check_closed.py).
Re-running is safe: existing files are never overwritten, only the fields above are set.
"""
import csv, datetime, io, json, os, re, sys, time, tomllib, urllib.parse, urllib.request, zipfile
from common import P, COUNTIES, companies, norm, company_path, set_field, del_field, set_list
from import_hifld import SECTOR_BY_NAICS3, titlecase, slug, q

SOURCE = "OSHA Injury Tracking Application, Form 300A establishment data (U.S. Department of Labor)"
DIR = {"n", "s", "e", "w", "north", "south", "east", "west", "ne", "nw", "se", "sw"}
STATE = {"18": "IN", "26": "MI"}

def rows_from(path):
    """Rows with lower-case column names (OSHA's capitalization varies between years)."""
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        fh = io.TextIOWrapper(z.open(name), encoding="utf-8-sig", errors="replace")
    else:
        fh = open(path, encoding="utf-8-sig", errors="replace")
    return ({k.strip().lower(): (v or "") for k, v in r.items() if k} for r in csv.DictReader(fh))

def addr_key(addr, city):
    t = re.findall(r"[a-z0-9]+", (addr or "").lower())
    if not t or not t[0].isdigit():
        return None
    rest = [w for w in t[1:] if w not in DIR]
    return (t[0], rest[0] if rest else "", (city or "").lower().strip())

DEPT = re.compile(r"(?i)^(administration|audit|claims|parts|service\w*|diesel service|gas service|hr\b.*|chassis receiving|receiving|shipping|"
                  r"warehouse|customer care\b.*|maintenance|cnc building|wire harness|headquarters|corporate|office|components|wrapping|countertops|"
                  r"assembly|lamination\b.*|main plant|main|plant|facility|site|division)$")

def strip_codes(n):
    """Drop plant numbers and codes: 'Plant 23', 'PLT 150', '#130', '(1806)', '058', 'C730031', 'DTI #1'."""
    n = re.sub(r"(?i)\b(plant|plt|bldg|building|store|location)\s*#?\s*[\w-]*\d[\w-]*", " ", n)
    n = re.sub(r"#\s*\w+|\(\s*\d+\s*\)|\b[A-Z]?\d{2,}[A-Za-z]?\b|\b\d\b|\b\d+_\d+\b", " ", n)
    return re.sub(r"\s+", " ", re.sub(r"^[\s\-–,/]+|[\s\-–,/]+$", "", re.sub(r"\s*[-–]\s*[-–]\s*", " - ", n))).strip()

def clean_name(est, company, city):
    """The establishment's own name where it is a real name; the company's where it is a place, street,
    department or plant number. A trailing ' - <city>' and plant codes are dropped."""
    est, company = (est or "").strip(), strip_codes((company or "").strip())
    n = re.sub(r"\s*[-–]\s*(%s|[a-z .]+,?\s+(in|mi))\b.*$" % re.escape(city), "", est, flags=re.I).strip() if city else est
    n = re.sub(r",\s*\d+\s+\w.*$", "", n)                      # 'StairSupplies, 1010 Eisenhower Dr. South'
    if city:
        n = re.sub(r"(?i)[\s\-–,]+%s(,?\s+(in|mi))?\s*$" % re.escape(city), "", n)   # 'Wieland Designs Topeka', 'MasterBrand Goshen'
    n = re.sub(r"(?i)\s+(llc|inc\.?)?\s*(wa|in|mi)$", lambda m: (" " + m[1]) if m[1] else "", n)
    coded = bool(re.search(r"\b(?=\w*[a-z])(?=\w*\d)\w+\b", n, re.I))   # 'FCE1-FOAM', 'IN222', '3MUS'
    n = re.sub(r"(?i)[\s\-–&,]+(plant|&)?$", "", strip_codes(n)).strip()
    generic = (not n or coded or len(re.sub(r"[^a-z]", "", n.lower())) < 4 or norm(n) in ("", norm(city)) or DEPT.match(n)
               or re.fullmatch(r"(?i).*\b(ave|avenue|st|street|rd|road|dr|drive|cr\d*)\.?", n)
               or re.fullmatch(r"(?i)(us\s+)?[a-z .]+,?\s+(in|mi|indiana|michigan)", n)
               or norm(n) in {norm(x) for x in ("Elkhart", "South Bend", "Goshen", "Middlebury", "Bremen", "Kendallville", "Sawyer", "Etna Green",
                                                 "South Haven", "New Paris", "Mishawaka", "Nappanee", "Michigan City", "Akron")})
    if company and n and norm(company).startswith(norm(n)) and len(norm(company)) > len(norm(n)):
        n = company                                                  # 'Global' of Global Composites Inc.
    name = company if generic and company else (n or company or est)
    name = re.sub(r"(?i)^dba\s+", "", name).strip()
    if name.isupper() and len(name) <= 4:
        return name
    return titlecase(name) if name.isupper() or name.islower() else name

def census_geo(address):
    """(lat, lon, county FIPS) from the Census geocoder, or None."""
    qs = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"})
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen("https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?" + qs, timeout=40))
            m = r.get("result", {}).get("addressMatches") or []
            if not m:
                return None
            cty = (m[0].get("geographies", {}).get("Counties") or [{}])[0].get("GEOID", "")
            return float(m[0]["coordinates"]["y"]), float(m[0]["coordinates"]["x"]), cty
        except Exception:
            time.sleep(2)
    return None

def main(args):
    dry = "--dry-run" in args
    gpath = args[args.index("--geocache") + 1] if "--geocache" in args else None
    files = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--geocache")]
    gcache = json.load(open(gpath)) if gpath and os.path.exists(gpath) else {}
    if not files:
        sys.exit(__doc__)
    zips = json.load(open(P("data", "region_zips.json")))["zips"]
    keep = [r for r in rows_from(files[0]) if r.get("state") in ("IN", "MI") and (r.get("zip_code") or "")[:5] in zips
            and (r.get("naics_code") or "")[:2] in ("31", "32", "33")]
    year = max((r.get("year_filing_for") or "" for r in keep), default="")
    # a figure one company reports at two or more addresses (100+) or three or more is its company-wide count
    from collections import Counter
    who = lambda r: " ".join(norm(r.get("company_name") or r["establishment_name"]).split()[:2])   # "Thor Motor Coach - C730027" = "Thor Motor Coach, Inc"
    emp_of = lambda r: int(float(r.get("annual_average_employees") or 0))
    seen_addr = {}
    for r in keep:
        seen_addr.setdefault((who(r), emp_of(r)), set()).add(addr_key(r["street_address"], r["city"]))
    company_wide = {k for k, v in seen_addr.items() if k[1] and (len(v) >= 3 or (len(v) >= 2 and k[1] >= 100))}
    placed = set()
    cs = [c for c in companies()]
    by_osha = {str(c["osha_id"]): c["_id"] for c in cs if c.get("osha_id")}
    by_addr, by_name = {}, {}
    for c in cs:
        k = addr_key(c.get("address", ""), c.get("city", ""))
        if k:
            by_addr.setdefault(k, c["_id"])
        by_name.setdefault((norm(c["name"]), (c.get("city") or "").lower()), c["_id"])
        z = re.findall(r"\b(\d{5})(?:-\d{4})?\s*$", c.get("address", ""))
        if z:
            by_name.setdefault((norm(c["name"]), z[0]), c["_id"])
    by_id = {c["_id"]: c for c in cs}
    existing = set(os.listdir(P("companies")))
    out, matched, updated, written, outside, nogeo, new_addr, pending, occupants, restored = {}, 0, 0, 0, [], [], {}, [], 0, 0
    today = datetime.date.today().isoformat()
    for r in sorted(keep, key=lambda r: -int(r.get("annual_average_employees") or 0)):
        eid, city = str(r["establishment_id"]).strip(), titlecase(r["city"].strip()) if r["city"].isupper() else r["city"].strip()
        emp = emp_of(r) or None
        scope = "site"
        if (who(r), emp_of(r)) in company_wide:
            if (who(r), emp_of(r)) in placed:
                emp = None                       # already on another site of this company
            else:
                placed.add((who(r), emp_of(r))); scope = "company"
        by_address = None if by_osha.get(eid) else by_addr.get(addr_key(r["street_address"], city))
        cid = by_osha.get(eid) or by_address \
            or next((by_name[k] for nm in (r["establishment_name"], r["company_name"], clean_name(r["establishment_name"], r["company_name"], city))
                     for k in ((norm(nm or "-"), city.lower()), (norm(nm or "-"), r["zip_code"][:5])) if k in by_name), None)
        if cid:
            c, path = by_id[cid], company_path(cid)
            filer = clean_name(r["establishment_name"], r["company_name"], city)
            words = lambda s: {w for w in norm(s).split() if len(w) >= 2}
            if cid == by_address and not words(c["name"]) & (words(r["establishment_name"]) | words(r["company_name"]) | words(filer)):
                # same address, different name: a successor, a rename or a new tenant. Note it for a person; keep the file's facts
                out[eid] = {"company": cid, "employees": emp, "naics": r["naics_code"], "occupant": filer}; occupants += 1
                if dry or not path:
                    continue
                if not (c.get("source") or "").startswith("HIFLD"):
                    set_field(path, "osha_occupant", "%s (OSHA Form 300A filer at this address, %s)" % (filer, year))
                    continue
                desc = (r.get("industry_description") or "").strip()
                old = c["name"]
                set_field(path, "name", filer)
                set_field(path, "formerly", "; ".join(x for x in (c.get("formerly"), old) if x))
                set_field(path, "status_note", "Named from OSHA's %s Form 300A filing at this address; the earlier record here, %s (HIFLD), is a predecessor or a former occupant." % (year, old))
                set_field(path, "naics", r["naics_code"]); set_field(path, "sector", SECTOR_BY_NAICS3.get(r["naics_code"][:3], c.get("sector")))
                set_list(path, "products", [desc or "Manufacturing"])
                set_field(path, "description", "NAICS %s: %s." % (r["naics_code"], desc.lower() or "manufacturing"))
                set_field(path, "osha_id", eid)
                for k in ("website", "uei", "osha_occupant", "presumed_closed", "presumed_closed_reason", "humanoid", "humanoid_evidence", "humanoid_note"):
                    del_field(path, k)
                if emp:
                    set_field(path, "employees", emp); set_field(path, "employees_scope", scope)
                    set_field(path, "employees_year", int(year) if year.isdigit() else year); set_field(path, "employees_quality", "reported")
                    set_field(path, "employees_note", "OSHA Form 300A, annual average employees at this establishment, %s" % year)
                else:
                    for k in ("employees", "employees_scope", "employees_year", "employees_quality", "employees_note"):
                        del_field(path, k)
                set_field(path, "source", SOURCE + "; the earlier record at this address came from HIFLD")
                text = open(path, encoding="utf-8").read()
                text = re.sub(r"\A# .*\n# Imported from the HIFLD.*\n", lambda m: "# %s\n# Imported from HIFLD, then updated from OSHA's Form 300A filing at this address (public); edit freely.\n" % filer, text)
                open(path, "w", encoding="utf-8").write(text)
                set_field(path, "updated", today)
                continue
            out[eid] = {"company": cid, "employees": emp, "naics": r["naics_code"]}; matched += 1
            if dry or not path:
                continue
            if not c.get("osha_id"):
                set_field(path, "osha_id", eid); by_osha[eid] = cid
            if c.get("presumed_closed"):
                del_field(path, "presumed_closed"); del_field(path, "presumed_closed_reason"); restored += 1
            if c.get("unconfirmed"):   # a same-name filing at this address confirms the plant
                del_field(path, "unconfirmed"); del_field(path, "unconfirmed_reason")
            if emp and scope == "site" and c.get("employees_scope", "site") == "site" and (not c.get("employees") or c.get("employees_quality") == "estimate"
                                                                      or re.search(r"(?i)estimate", c.get("employees_note", ""))):
                set_field(path, "employees", emp); set_field(path, "employees_year", int(year) if year.isdigit() else year)
                set_field(path, "employees_quality", "reported")
                set_field(path, "employees_note", "OSHA Form 300A, annual average employees at this establishment, %s" % year)
                updated += 1
            continue
        name = clean_name(r["establishment_name"], r["company_name"], city)
        street = re.sub(r"\s+", " ", r["street_address"]).strip().rstrip(",")
        st, z = r["state"], r["zip_code"][:5]
        address = "%s, %s, %s %s" % (street, city, st, z)
        fname = "%s--%s--%s.toml" % (slug(name), slug(city), slug(street.split(" ")[0] or "x"))
        ak = addr_key(street, city)
        if fname in existing or (ak and ak in new_addr):
            if ak in new_addr and emp and scope == "site":
                new_addr[ak][1] = max(new_addr[ak][1] or 0, emp)   # departments filed separately at one plant: the largest
            if ak in new_addr:
                out[eid] = {"company": new_addr[ak][0], "employees": emp, "naics": r["naics_code"]}
            continue
        g = gcache.get(address)
        if g is None and not dry:
            g = census_geo(address); time.sleep(0.2)
            if g:
                gcache[address] = list(g)
        if g and g[2] not in COUNTIES:
            outside.append("%s (%s, county %s)" % (name, city, g[2])); continue
        if not g and not dry:
            nogeo.append("%s, %s" % (name, address))
        n3 = r["naics_code"][:3]
        sector = SECTOR_BY_NAICS3.get(n3, "Medical devices & other")
        desc = (r.get("industry_description") or "").strip()
        lines = ["# %s" % name, "# Imported from OSHA's Form 300A establishment data (public); edit freely.", "",
                 "name = %s" % q(name), 'kind = "company"', "city = %s" % q(city), 'state = "%s"' % st, "address = %s" % q(address)]
        if g:
            lines += ["lat = %.5f" % g[0], "lon = %.5f" % g[1]]
        lines += ['osha_id = "%s"' % eid, "", "sector = %s" % q(sector), "products = [%s]" % q(desc or "Manufacturing"),
                  'naics = "%s"' % r["naics_code"], ""]
        if emp:
            lines += ["employees = %d" % emp, 'employees_scope = "%s"' % scope, "employees_year = %s" % (year if year.isdigit() else q(year)),
                      'employees_quality = "reported"', 'employees_note = "OSHA Form 300A, annual average employees at this establishment, %s"' % year, ""]
        if r.get("company_name") and norm(r["company_name"]) != norm(name):
            lines += ["parent = %s" % q(r["company_name"].strip())]
        lines += ["description = %s" % q("NAICS %s: %s." % (r["naics_code"], desc.lower() or "manufacturing")), "",
                  "source = %s" % q(SOURCE), 'updated = "%s"' % today, ""]
        if g is None and not dry:
            continue   # not geocoded: listed below for a person to add by hand
        cid_new = re.sub(r"[^a-z0-9]+", "-", fname[:-5].lower()).strip("-")
        out[eid] = {"company": cid_new, "employees": emp, "naics": r["naics_code"]}
        if ak:
            new_addr[ak] = [cid_new, emp, fname, lines]
        pending.append((fname, lines, ak))
        existing.add(fname); written += 1
    for fname, lines, ak in pending:   # write after merging departments: the headcount is the plant's total
        tot = new_addr.get(ak, [None, None])[1] if ak else None
        if tot:
            lines = [("employees = %d" % tot) if l.startswith("employees = ") else l for l in lines]
        if not dry:
            with open(P("companies", fname), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
    if gpath and not dry:
        json.dump(gcache, open(gpath, "w"))
    if not dry:
        prev = json.load(open(P("data", "osha.json"))) if os.path.exists(P("data", "osha.json")) else {}
        years = prev.get("years", {})
        years[year] = out
        json.dump({"source": SOURCE, "file": os.path.basename(files[0]), "imported": today, "latest_year": year,
                   "years": dict(sorted(years.items()))}, open(P("data", "osha.json"), "w"), indent=0)
    print("%d regional manufacturing establishments in %s (filing year %s): %d matched, %d at a file's address under another name (file updated to the filer), %d presumed-closed restored, %d headcounts updated, %d new files %s, %d outside the region, %d not geocoded"
          % (len(keep), os.path.basename(files[0]), year, matched, occupants, restored, updated, written,
             "would be written" if dry else "written", len(outside), len(nogeo)))
    for x in nogeo:
        print("  not geocoded, add by hand if wanted:", x)

if __name__ == "__main__":
    main(sys.argv[1:])
