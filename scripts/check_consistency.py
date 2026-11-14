#!/usr/bin/env python3
"""Internal consistency checks of the company files on the map. Changes nothing.

    python3 scripts/check_consistency.py [out.csv]     # default: audits/consistency-check.csv

Checks every company on the map (not closed, presumed closed or removed):
- location: the coordinates fall in one of the region's counties (data/region_counties_detail.json);
- duplicate: another file has the same street address, the same street address under another postal
  town within 2 km (Sawyer and Bridgman), the same name within 300 m, or a name sharing a word on the
  same street within 100 m (Hydro Elkhart at 3408 and Hydro Extrusion at 3406 Reedy Drive);
- headcount: a site headcount above 5,000, or a headcount that looks company-wide;
- sector: the sector disagrees with the NAICS code's usual sector (scripts/import_hifld.py);
- precision: placed at a city's center instead of a street address;
- osha_id: one OSHA establishment on two files (all files, also removed ones).
Each row is one finding for a person to look at; the summary line counts them by kind.
"""
import csv, json, math, re, sys
from common import P, COUNTIES, companies, norm
from import_hifld import SECTOR_BY_NAICS3
from import_osha import addr_key, county_of

def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else P("audits", "consistency-check.csv")
    zips = json.load(open(P("data", "region_zips.json")))["zips"]
    cs = [c for c in companies() if not any(c.get(k) for k in ("closed", "presumed_closed", "removed"))]
    rows = []
    add = lambda c, kind, detail: rows.append({"kind": kind, "file": "companies/" + c["_file"], "name": c["name"], "address": c.get("address", ""), "detail": detail})
    by_addr, by_street, by_name = {}, {}, {}
    for c in cs:
        k = addr_key(c.get("address", ""), c.get("city", ""))
        if k:
            by_addr.setdefault(k, []).append(c)
            by_street.setdefault(addr_key(c["address"].split(",")[0], "-"), []).append(c)
        by_name.setdefault(norm(c["name"]), []).append(c)
        if "lat" in c:
            cty = county_of(c["lat"], c["lon"])
            z = (re.search(r"\b(\d{5})(?:-\d{4})?\s*$", c.get("address", "")) or [None, ""])[1]
            if cty not in COUNTIES:   # ZIP codes cross county lines (Walkerton), so only a point outside the region is flagged
                add(c, "location", "coordinates %.4f, %.4f are %s" % (c["lat"], c["lon"], "in county %s, outside the region" % cty if cty else "outside the mapped counties"))
        if c.get("location_precision") == "city":
            add(c, "precision", "placed approximately, not at its street address (%s)" % (c.get("status_note") or "the center of %s" % c.get("city", "")))
        e = c.get("employees")
        if e and e > 5000 and c.get("employees_scope", "site") == "site":
            add(c, "headcount", "%d employees at one site" % e)
        n3 = str(c.get("naics", ""))[:3]
        if n3 in SECTOR_BY_NAICS3 and c.get("sector") and c["sector"] != SECTOR_BY_NAICS3[n3] and c.get("kind", "company") == "company":
            add(c, "sector", "sector %s, but NAICS %s is usually %s" % (c["sector"], c.get("naics"), SECTOR_BY_NAICS3[n3]))
    for k, group in by_addr.items():
        if len(group) > 1:
            for c in group:
                add(c, "duplicate", "same address as " + "; ".join("%s (%s)" % (o["name"], o["_file"]) for o in group if o is not c))
    for group in by_street.values():   # the same street address filed under two postal towns
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a.get("city") != b.get("city") and "lat" in a and "lat" in b and km((a["lat"], a["lon"]), (b["lat"], b["lon"])) < 2:
                    add(a, "duplicate", "same street address under another town within 2 km: %s (%s)" % (b.get("address", ""), b["_file"]))
    from check_sites import key as site_key
    GENERIC = {"inc", "llc", "co", "corp", "company", "the", "of", "and", "industries", "products", "manufacturing", "mfg",
               "group", "international", "usa", "plant", "division", "systems", "rv", "homes"}
    sig = lambda c: {w for w in norm(c["name"]).split() if len(w) > 2 and w not in GENERIC}
    by_road = {}
    for c in cs:
        if "lat" in c and site_key(c.get("address", ""))[1]:
            by_road.setdefault((site_key(c["address"])[1], c.get("city", "")), []).append(c)
    for group in by_road.values():   # a related name next door on the same street: often one plant, filed twice
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                town = set(norm(a.get("city", "")).split())   # "Walkerton - ARCo" and "Walkerton Tool & Die" share only the town
                if (norm(a["name"]) != norm(b["name"]) and (sig(a) & sig(b)) - town and km((a["lat"], a["lon"]), (b["lat"], b["lon"])) < 0.1
                        and addr_key(a.get("address", ""), a.get("city", "")) != addr_key(b.get("address", ""), b.get("city", ""))):
                    add(a, "duplicate", "a related name on the same street within 100 m: %s, %s (%s)" % (b["name"], b.get("address", ""), b["_file"]))
    for n, group in by_name.items():
        located = [c for c in group if "lat" in c]
        for i, a in enumerate(located):
            for b in located[i + 1:]:
                if km((a["lat"], a["lon"]), (b["lat"], b["lon"])) < 0.3 and addr_key(a.get("address", ""), a.get("city", "")) != addr_key(b.get("address", ""), b.get("city", "")):
                    add(a, "duplicate", "same name within 300 m: %s (%s)" % (b.get("address", ""), b["_file"]))
    # one OSHA establishment on two files: a removed duplicate or a company-wide file still holding a plant's filing
    by_osha = {}
    for c in companies():
        if c.get("osha_id"):
            by_osha.setdefault(str(c["osha_id"]), []).append(c)
    for i, group in by_osha.items():
        if len(group) > 1:
            for c in group:
                add(c, "osha_id", "OSHA establishment %s is also on %s" % (i, "; ".join(o["_file"] for o in group if o is not c)))
    rows.sort(key=lambda r: (r["kind"], r["name"]))
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["kind", "file", "name", "address", "detail"]); w.writeheader(); w.writerows(rows)
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print("%d companies checked: %s; wrote %s" % (len(cs), ", ".join("%s %d" % kv for kv in sorted(kinds.items())) or "no findings", out))

if __name__ == "__main__":
    main()
