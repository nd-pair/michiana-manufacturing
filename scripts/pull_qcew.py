#!/usr/bin/env python3
"""Manufacturing employment and wages by county and year, from the BLS Quarterly Census of Employment and Wages.

    python3 scripts/pull_qcew.py        # writes data/qcew.json

Uses the QCEW open-data CSV slices by industry (NAICS supersector 1013 = Manufacturing, private
ownership), annual averages, for the Michiana counties. No key needed.
"""
import csv, io, json, urllib.request, datetime
from common import P, COUNTIES

def main():
    series = {k: {} for k in COUNTIES}
    years = list(range(2010, datetime.date.today().year))
    for y in years:
        url = "https://data.bls.gov/cew/data/api/%d/a/industry/1013.csv" % y
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "michiana-manufacturing/1.0"}), timeout=120) as r:
                text = r.read().decode("utf-8", "replace")
        except Exception as e:
            print(y, "skipped:", e); continue
        n = 0
        for row in csv.DictReader(io.StringIO(text)):
            if row.get("own_code") == "5" and row.get("area_fips") in series:
                series[row["area_fips"]][y] = {"estab": int(row["annual_avg_estabs"] or 0), "emp": int(row["annual_avg_emplvl"] or 0), "pay": int(row["avg_annual_pay"] or 0)}
                n += 1
        print(y, n, "county rows")
    data = {"source": "BLS QCEW, NAICS 31-33 manufacturing, private, annual averages", "pulled": datetime.date.today().isoformat(),
            "counties": {k: {"name": COUNTIES[k], "years": series[k]} for k in COUNTIES}}
    json.dump(data, open(P("data", "qcew.json"), "w"), indent=0)

if __name__ == "__main__":
    main()
