#!/usr/bin/env python3
"""Import manufacturing facilities from the HIFLD "General Manufacturing Facilities" dataset.

    python3 scripts/import_hifld.py            # fetch, write new companies/*.toml, report
    python3 scripts/import_hifld.py --dry-run  # report only

Source: the U.S. Department of Homeland Security's HIFLD General Manufacturing Facilities layer
(NAICS 31-33, public data), as served by the Department of Energy's NETL ArcGIS service after the
HIFLD portal closed in 2025. Every record has a name, street address, county, 6-digit NAICS code
and description, a product line, a website and an employee estimate.

What the script does:
- fetches every facility inside the Michiana bounding box and keeps the counties listed below;
- maps the 3-digit NAICS sector to one of our sectors (data/sectors.toml);
- skips a facility when a company file already exists with the same website domain or the same
  normalized name (so hand-written entries win), and when a file for that facility exists;
- writes one TOML file per facility, named <company>--<city>--<street number>.toml.
Re-running is safe: existing files are never overwritten.
"""
import datetime, json, os, re, sys, tomllib, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
HIFLD_YEAR = 2022   # the DHS base dataset behind the NETL layer; its employee figures carry no survey date of their own
URL = "https://arcgis.netl.doe.gov/server/rest/services/Hosted/ManFacNAICS3133_Emissions/FeatureServer/0/query"
BBOX = {"xmin": -87.1, "ymin": 41.15, "xmax": -85.55, "ymax": 42.05, "spatialReference": {"wkid": 4326}}
COUNTIES = {"ELKHART", "ST JOSEPH", "MARSHALL", "LA PORTE", "KOSCIUSKO", "STARKE", "FULTON", "LAGRANGE", "NOBLE",
            "WHITLEY", "BERRIEN", "CASS", "VAN BUREN"}
SECTOR_BY_NAICS3 = {
    "331": "Metal", "332": "Metal",
    "333": "Mechatronics & automation",
    "334": "Electronics", "335": "Electronics",
    "336": "Vehicles & RVs",
    "325": "Materials & composites", "326": "Materials & composites", "327": "Materials & composites",
    "321": "Wood, paper & furniture", "322": "Wood, paper & furniture", "323": "Wood, paper & furniture", "337": "Wood, paper & furniture",
    "311": "Food & consumer goods", "312": "Food & consumer goods", "313": "Food & consumer goods", "314": "Food & consumer goods",
    "315": "Food & consumer goods", "316": "Food & consumer goods",
    "339": "Medical devices & other",
}
SMALL = {"and", "of", "the", "for", "in", "at", "by", "de", "&"}
KEEP_UPPER = {"LLC", "LP", "LLP", "USA", "US", "RV", "CNC", "EDM", "PVC", "HVAC", "OEM", "II", "III", "IV", "AM", "PM", "HQ", "ATC", "CTS",
              "MTI", "BCI", "GSM", "A&E", "R&D", "DMLS", "UV", "LED", "AC", "DC", "A/C", "NA", "T&M", "JM", "RVS", "CNC", "PCB", "ABS", "EPS", "LLC."}
SUFFIX = {"INC": "Inc.", "INC.": "Inc.", "CORP": "Corp.", "CORP.": "Corp.", "CO": "Co.", "CO.": "Co.", "LTD": "Ltd.", "LTD.": "Ltd.", "MFG": "Mfg.", "MFG.": "Mfg.", "DIV": "Div.", "DIV.": "Div."}

def titlecase(s):
    out = []
    for w in s.strip().split():
        u = w.upper().strip(",")
        if u in SUFFIX:
            out.append(SUFFIX[u] + ("," if w.endswith(",") else ""))
        elif u.strip(".") in KEEP_UPPER or u in KEEP_UPPER or re.fullmatch(r"(?:[A-Z]\.){2,}", u):
            out.append(w.upper())   # also dotted initials: R.R. Donnelley, K.M.C. Corp., Viking R.V.
        elif w.lower() in SMALL and out:
            out.append(w.lower())
        elif "-" in w:
            out.append("-".join(p.capitalize() for p in w.split("-")))
        elif "'" in w:
            out.append(w[0].upper() + w[1:].lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)

def norm_name(s):
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    s = re.sub(r"\b(inc|incorporated|llc|corp|corporation|co|company|ltd|lp|llp|the|of|usa)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def domain(url):
    if not url:
        return ""
    u = url.lower().strip()
    u = re.sub(r"^https?://", "", u); u = re.sub(r"^www\.", "", u)
    return u.split("/")[0]

def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def fetch():
    feats, off = [], 0
    while True:
        params = {"where": "1=1", "geometry": json.dumps(BBOX), "geometryType": "esriGeometryEnvelope", "inSR": "4326", "outSR": "4326",
                  "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true", "resultOffset": str(off),
                  "resultRecordCount": "2000", "f": "json"}
        with urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(params), timeout=120) as r:
            d = json.load(r)
        if "error" in d:
            sys.exit("service error: %s" % d["error"])
        feats += d.get("features", [])
        if not d.get("exceededTransferLimit"):
            return feats
        off += 2000

def parse_address(a):
    # "1215 WEST DEWEY STREET, BREMEN, IN, 46506"
    parts = [p.strip() for p in a.split(",")]
    if len(parts) >= 4:
        street, city, state, zip_ = parts[0], parts[-3], parts[-2], parts[-1]
    elif len(parts) == 3:
        street, city, state, zip_ = parts[0], parts[1], parts[2][:2], parts[2][2:].strip()
    else:
        return a, "", "", ""
    return titlecase(street), titlecase(city), state.upper(), zip_

def main():
    dry = "--dry-run" in sys.argv
    sectors = {s["name"] for s in tomllib.load(open(P("data", "sectors.toml"), "rb"))["sector"]}
    missing = set(SECTOR_BY_NAICS3.values()) - sectors
    if missing:
        sys.exit("add these sectors to data/sectors.toml first: %s" % ", ".join(sorted(missing)))
    existing_names, existing_domains, existing_files = set(), set(), set(os.listdir(P("companies")))
    for n in existing_files:
        if n.endswith(".toml"):
            c = tomllib.load(open(P("companies", n), "rb"))
            existing_names.add(norm_name(c["name"]))
            if c.get("website"):
                existing_domains.add(domain(c["website"]))
    feats = fetch()
    written, skipped_dup, skipped_county, skipped_exists = 0, [], 0, 0
    for f in feats:
        a, g = f["attributes"], f["geometry"]
        if (a.get("county") or "").upper() not in COUNTIES:
            skipped_county += 1; continue
        name = re.sub(r"\(h ?q\)", "(HQ)", titlecase(a["name"]), flags=re.I); street, city, state, zip_ = parse_address(a["facility_address"] or "")
        if (a.get("county") or "").upper() == "ST JOSEPH" and (state or "").upper() not in ("IN", "INDIANA"):
            skipped_county += 1; continue   # St. Joseph County exists in both states; only Indiana's (South Bend) is in the region
        if not city:
            continue
        dom = domain(a.get("web"))
        if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", dom or ""):
            dom = ""             # HIFLD writes "NOT AVAILABLE" where it has no website
        if norm_name(name) in existing_names or (dom and dom in existing_domains):
            skipped_dup.append(name); continue
        fname = "%s--%s--%s.toml" % (slug(name), slug(city), slug(street.split(" ")[0] or "x"))
        if fname in existing_files:
            skipped_exists += 1; continue
        sector = SECTOR_BY_NAICS3.get((a.get("naics_ss_code") or "")[:3])
        if not sector:
            continue
        naics6 = a.get("naics_ni_code") or ""; ndesc = titlecase(a.get("naicsdescr") or a.get("naicc_ss_desc") or "")
        product = titlecase(a.get("product") or "")
        tags = [ndesc] if ndesc else []
        raw = (a.get("naicsdescr") or a.get("naicc_ss_desc") or "").strip().lower()
        desc = (product + ". " if product else "") + ("NAICS %s: %s." % (naics6, raw) if naics6 and raw else "")
        lines = ["# %s" % name, "# Imported from the HIFLD General Manufacturing Facilities dataset (public); edit freely.", "",
                 "name = %s" % q(name), 'kind = "company"', "city = %s" % q(city), "state = %s" % q(state),
                 "address = %s" % q("%s, %s, %s %s" % (street, city, state, zip_)), "lat = %.5f" % g["y"], "lon = %.5f" % g["x"]]
        if dom:
            lines.append("website = %s" % q("https://" + dom))
        lines += ["", "sector = %s" % q(sector), "products = [%s]" % ", ".join(q(t) for t in tags)]
        if naics6:
            lines.append("naics = %s" % q(naics6))
        lines.append("")
        if a.get("emp"):
            lines += ["employees = %d" % int(a["emp"]), 'employees_scope = "site"', "employees_year = %d" % HIFLD_YEAR, 'employees_quality = "estimate"',
                      'employees_note = "HIFLD General Manufacturing Facilities estimate (base dataset %d)"' % HIFLD_YEAR]
        lines += ["", "description = %s" % q(desc), "", 'source = "HIFLD General Manufacturing Facilities (U.S. DHS), via DOE NETL"',
                  "updated = %s" % q(datetime.date.today().isoformat()), ""]
        if not dry:
            with open(P("companies", fname), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
        existing_files.add(fname); written += 1
    print("fetched %d; outside Michiana counties %d; duplicates of hand-written entries %d; already imported %d; %s %d"
          % (len(feats), skipped_county, len(skipped_dup), skipped_exists, "would write" if dry else "written", written))
    if skipped_dup:
        print("skipped as duplicates:", "; ".join(sorted(set(skipped_dup))))

if __name__ == "__main__":
    main()
