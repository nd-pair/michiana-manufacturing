#!/usr/bin/env python3
"""How much of the region's manufacturing the map covers, against the Census Bureau's County
Business Patterns (CBP). Changes nothing.

    python3 scripts/check_coverage.py [YEAR]      # default: the latest CBP county file that exists

Downloads the public CBP county file (www2.census.gov, no key), counts the manufacturing
establishments (NAICS 31-33) in each of the region's counties, in total and with 20 or more
employees, and by 3-digit industry, and compares them with the manufacturing sites on the map
(placed in a county by their coordinates). Then does the same per ZIP code, from the CBP ZIP
tables on api.census.gov (key optional, see common.census_api; the map's sites are placed by the
ZIP code in their address), so the gaps can be looked for street by street. Writes
audits/coverage-check.csv, ZIP rows sorted by the number of 20+ employee establishments missing.

Read the numbers as rough: CBP counts employer establishments in the year it covers; the map's
size classes rest on reported or estimated headcounts; a site the map shows as one plant can be two
establishments in CBP, or the reverse.
"""
import csv, datetime, io, json, re, sys, urllib.request, zipfile
from common import P, COUNTIES, companies, census_api
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
    out += zip_rows(sites, year)
    with open(P("audits", "coverage-check.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    E = sum(v[0] for v in cbp.values()); E20 = sum(v[1] for v in cbp.values())
    M = sum(v[0] for v in mp.values()); M20 = sum(v[1] for v in mp.values())
    print("CBP %d (%s): the map has %d of %d manufacturing establishments (%d%%), %d of %d with 20+ employees (%d%%); wrote audits/coverage-check.csv"
          % (year, url, M, E, round(100 * M / E), M20, E20, round(100 * M20 / E20)))

def zip_rows(sites, year):
    """Per ZIP code: CBP establishments (all, and 20+ employees) against the map's sites in that ZIP."""
    zips = json.load(open(P("data", "region_zips.json")))["zips"]
    try:
        rows = census_api("%d/cbp" % year, {"get": "ESTAB,EMPSZES", "for": "zip code:" + ",".join(sorted(zips)), "NAICS2017": "31-33"})
    except RuntimeError as e:
        print("ZIP codes skipped: %s" % e)
        return []
    cbp = {}
    for r in rows:
        z = cbp.setdefault(r["zip code"], [0, 0])
        if r["EMPSZES"] == "001":
            z[0] = int(r["ESTAB"])
        elif r["EMPSZES"][:2] in ("24", "25", "26"):   # 20-49 ... 1,000 or more
            z[1] += int(r["ESTAB"])
    mp = {}
    for c in sites:
        m = re.search(r"\b(\d{5})(?:-\d{4})?\s*$", c.get("address", ""))
        if m and m.group(1) in zips:
            z = mp.setdefault(m.group(1), [0, 0])
            z[0] += 1
            z[1] += c.get("employees_scope", "site") == "site" and (c.get("employees") or 0) >= 20
    out = []
    for z in set(cbp) | set(mp):
        e, e20 = cbp.get(z, (0, 0)); m, m20 = mp.get(z, (0, 0))
        out.append({"level": "zip", "key": "%s (%s)" % (z, COUNTIES.get(zips.get(z), "")), "cbp_establishments": e, "map_sites": m,
                    "coverage_pct": round(100 * m / e) if e else "", "cbp_20_plus": e20, "map_20_plus": m20,
                    "coverage_20_plus_pct": round(100 * m20 / e20) if e20 else ""})
    out.sort(key=lambda r: (-(r["cbp_20_plus"] - r["map_20_plus"]), -(r["cbp_establishments"] - r["map_sites"])))
    print("ZIP codes: %d with CBP manufacturing establishments; the 5 with the most 20+ employee establishments missing: %s"
          % (len(cbp), ", ".join("%s %d of %d" % (r["key"], r["map_20_plus"], r["cbp_20_plus"]) for r in out[:5])))
    return out

if __name__ == "__main__":
    main()
