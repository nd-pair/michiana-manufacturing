#!/usr/bin/env python3
"""Manufacturing employment and wages from the BLS Quarterly Census of Employment and Wages.

    python3 scripts/pull_qcew.py        # writes data/qcew.json

Two views, both private ownership, annual averages:
- by county: NAICS 31-33 total for each Michiana county, from the industry slice 1013;
- by sector: each county's 3-digit NAICS rows from the area slices, folded into the map's
  sectors (same NAICS mapping as the HIFLD import) and summed over the region. BLS withholds
  cells that would disclose a single employer; those count as zero, so the sector sums are a
  lower bound and the note on the chart says so.
"""
import csv, io, json, urllib.request, datetime
from concurrent.futures import ThreadPoolExecutor
from common import P, COUNTIES
from import_hifld import SECTOR_BY_NAICS3

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
FIRST = 2014

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
        return r.read().decode("utf-8", "replace")

def main():
    years = list(range(FIRST, datetime.date.today().year))
    counties = {k: {} for k in COUNTIES}
    for y in years:
        try:
            text = get("https://data.bls.gov/cew/data/api/%d/a/industry/1013.csv" % y)
        except Exception as e:
            print(y, "county totals skipped:", e); continue
        for row in csv.DictReader(io.StringIO(text)):
            if row.get("own_code") == "5" and row.get("area_fips") in counties:
                counties[row["area_fips"]][y] = {"estab": int(row["annual_avg_estabs"] or 0), "emp": int(row["annual_avg_emplvl"] or 0), "pay": int(row["avg_annual_pay"] or 0)}
    sectors, withheld = {}, {}
    def area(job):
        y, fips = job
        try:
            return y, fips, get("https://data.bls.gov/cew/data/api/%d/a/area/%s.csv" % (y, fips))
        except Exception as e:
            return y, fips, None
    jobs = [(y, f) for y in years for f in COUNTIES]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for y, fips, text in ex.map(area, jobs):
            if not text:
                print(y, fips, "area slice skipped"); continue
            for row in csv.DictReader(io.StringIO(text)):
                code = row.get("industry_code", "")
                if row.get("own_code") != "5" or len(code) != 3 or code not in SECTOR_BY_NAICS3:
                    continue
                sec = SECTOR_BY_NAICS3[code]
                emp = int(row.get("annual_avg_emplvl") or 0)
                if row.get("disclosure_code") == "N":
                    withheld.setdefault(str(y), 0); withheld[str(y)] += 1
                sectors.setdefault(sec, {}); sectors[sec][y] = sectors[sec].get(y, 0) + emp
    data = {"source": "BLS QCEW, private, annual averages", "pulled": datetime.date.today().isoformat(),
            "counties": {k: {"name": COUNTIES[k], "years": counties[k]} for k in COUNTIES},
            "sectors": {s: {str(y): v for y, v in sorted(d.items())} for s, d in sectors.items()},
            "withheld_cells": withheld}
    json.dump(data, open(P("data", "qcew.json"), "w"), indent=0)
    print("counties: %d with data; sectors: %s" % (sum(1 for k in counties if counties[k]), ", ".join("%s %d" % (s, d[max(d)]) for s, d in sorted(sectors.items()))))

if __name__ == "__main__":
    main()
