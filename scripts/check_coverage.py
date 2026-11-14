#!/usr/bin/env python3
"""How much of the region's manufacturing the map covers, against the Census Bureau's County
Business Patterns (CBP). Changes nothing.

    python3 scripts/check_coverage.py [YEAR]      # default: the latest CBP county file that exists

Downloads the public CBP county file (www2.census.gov, no key), counts the manufacturing
establishments (NAICS 31-33) in each of the region's counties, in total and with 20 or more
employees, and by 3-digit industry, and compares them with the manufacturing sites on the map
(placed in a county by their coordinates). Writes audits/coverage-check.csv.

Read the numbers as rough: CBP counts employer establishments in the year it covers; the map's
size classes rest on reported or estimated headcounts; a site the map shows as one plant can be two
establishments in CBP, or the reverse.
"""
import csv, datetime, io, sys, urllib.request, zipfile
from common import P, COUNTIES, companies
from import_osha import county_of
from build import is_manufacturer

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}

def cbp_rows(year):
    yy = str(year)[2:]
    url = "https://www2.census.gov/programs-surveys/cbp/datasets/%s/cbp%sco.zip" % (year, yy)
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    return csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="latin-1")), url

def main():
    years = [int(sys.argv[1])] if len(sys.argv) > 1 else range(datetime.date.today().year - 2, 2019, -1)
    for year in years:
        try:
            rows, url = cbp_rows(year)
            break
        except Exception:
            continue
    else:
        sys.exit("no CBP county file found")
    num = lambda r, k: int(r[k]) if r.get(k, "").isdigit() else 0
    cbp, cbp3 = {}, {}
    for r in rows:
        f = r["fipstate"] + r["fipscty"]
        if f not in COUNTIES:
            continue
        if r["naics"] == "31----":
            cbp[f] = (int(r["est"]), sum(num(r, k) for k in ("n20_49", "n50_99", "n100_249", "n250_499", "n500_999", "n1000")))
        elif len(r["naics"]) == 6 and r["naics"].endswith("///") and r["naics"][:2] in ("31", "32", "33"):
            cbp3[r["naics"][:3]] = cbp3.get(r["naics"][:3], 0) + int(r["est"])
    sites = [c for c in companies() if "lat" in c and is_manufacturer(c) and not any(c.get(k) for k in ("closed", "presumed_closed", "removed"))]
    mp, mp3 = {f: [0, 0] for f in COUNTIES}, {}
    for c in sites:
        f = county_of(c["lat"], c["lon"])
        if f in mp:
            mp[f][0] += 1
            if c.get("employees_scope", "site") == "site" and (c.get("employees") or 0) >= 20:
                mp[f][1] += 1
        k = str(c.get("naics", ""))[:3]
        if k[:2] in ("31", "32", "33"):
            mp3[k] = mp3.get(k, 0) + 1
    out = []
    for f, name in COUNTIES.items():
        e, e20 = cbp.get(f, (0, 0))
        out.append({"level": "county", "key": name, "cbp_establishments": e, "map_sites": mp[f][0], "coverage_pct": round(100 * mp[f][0] / e) if e else "",
                    "cbp_20_plus": e20, "map_20_plus": mp[f][1], "coverage_20_plus_pct": round(100 * mp[f][1] / e20) if e20 else ""})
    for k, e in sorted(cbp3.items(), key=lambda kv: -kv[1]):
        out.append({"level": "naics3", "key": k, "cbp_establishments": e, "map_sites": mp3.get(k, 0), "coverage_pct": round(100 * mp3.get(k, 0) / e) if e else "",
                    "cbp_20_plus": "", "map_20_plus": "", "coverage_20_plus_pct": ""})
    with open(P("audits", "coverage-check.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    E = sum(v[0] for v in cbp.values()); E20 = sum(v[1] for v in cbp.values())
    M = sum(v[0] for v in mp.values()); M20 = sum(v[1] for v in mp.values())
    print("CBP %d (%s): the map has %d of %d manufacturing establishments (%d%%), %d of %d with 20+ employees (%d%%); wrote audits/coverage-check.csv"
          % (year, url, M, E, round(100 * M / E), M20, E20, round(100 * M20 / E20)))

if __name__ == "__main__":
    main()
