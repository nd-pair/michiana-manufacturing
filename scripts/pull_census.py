#!/usr/bin/env python3
"""Manufacturing by county from four Census Bureau datasets (api.census.gov; key optional, see
common.census_api). Writes data/census.json, shown on the Occupations tab (Workforce, Counties).

    python3 scripts/pull_census.py

- Economic Census 2022 (ecnbasic): manufacturing establishments, jobs, payroll and value of
  shipments per county, in total and by 3-digit industry, and for the U.S. Runs every five years.
- American Community Survey 5-year: residents who work in manufacturing and their median earnings
  (table B24031, C24050), per county and for the U.S. Counts where workers live, not where they work.
- Business Dynamics Statistics: manufacturing establishments that opened and closed each year, per
  county and for the U.S.
- Nonemployer Statistics: manufacturing businesses with no paid employees (mostly one person).
Each dataset is independent; one that fails keeps its part of the previous file.
"""
import datetime, json, os
from collections import defaultdict
from common import P, COUNTIES, census_api

STATES = defaultdict(list)
for f in COUNTIES:
    STATES[f[:2]].append(f[2:])
MFG = "31-33"

def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None

def by_county(path, params):
    """Rows for all the region's counties, keyed by 5-digit FIPS."""
    out = []
    for st, cs in STATES.items():
        for r in census_api(path, dict(params, **{"for": "county:" + ",".join(cs), "in": "state:" + st})):
            r["fips"] = r["state"] + r["county"]
            out.append(r)
    return out

def latest(fn, years):
    """The first year in `years` for which fn(year) works and returns rows."""
    for y in years:
        try:
            rows = fn(y)
        except RuntimeError:
            continue
        if rows:
            return y, rows
    raise RuntimeError("no year of %s available" % fn.__name__)

def economic_census():
    year = 2022
    get = "NAICS2022,NAICS2022_LABEL,INDLEVEL,ESTAB,EMP,PAYANN,RCPTOT,RCPTOT_F,EMP_F"
    counties = {}
    for r in by_county("%d/ecnbasic" % year, {"get": get}):
        code = r["NAICS2022"]
        if not (code == MFG or (r["INDLEVEL"] == "3" and code[:2] in ("31", "32", "33"))):
            continue
        withheld = bool(r.get("RCPTOT_F") or r.get("EMP_F"))
        row = {"estab": num(r["ESTAB"]), "emp": None if r.get("EMP_F") else num(r["EMP"]),
               "pay": None if r.get("EMP_F") else num(r["PAYANN"]), "ship": None if r.get("RCPTOT_F") else num(r["RCPTOT"])}
        c = counties.setdefault(r["fips"], {"industries": []})
        if code == MFG:
            c.update(row)
        else:
            c["industries"].append(dict(row, naics=code, name=r["NAICS2022_LABEL"], withheld=withheld))
    for c in counties.values():
        c["industries"].sort(key=lambda i: -(i["ship"] or 0))
    us = census_api("%d/ecnbasic" % year, {"get": "ESTAB,EMP,PAYANN,RCPTOT", "NAICS2022": MFG, "for": "us:1"})[0]
    return {"year": year, "units": "pay and shipments in $1,000", "counties": counties,
            "us": {"estab": num(us["ESTAB"]), "emp": num(us["EMP"]), "pay": num(us["PAYANN"]), "ship": num(us["RCPTOT"])}}

def acs():
    get = "B24031_001E,B24031_006E,B24031_006M,C24050_001E,C24050_004E,C24050_074E"
    def fetch(y):
        return by_county("%d/acs/acs5" % y, {"get": get}), census_api("%d/acs/acs5" % y, {"get": get, "for": "us:1"})
    year, (rows, us) = latest(fetch, range(datetime.date.today().year - 1, 2019, -1))
    pick = lambda r: {"workers": num(r["C24050_004E"]), "production": num(r["C24050_074E"]), "employed": num(r["C24050_001E"]),
                      "median": num(r["B24031_006E"]), "median_moe": num(r["B24031_006M"]), "median_all": num(r["B24031_001E"])}
    return {"years": "%d–%d" % (year - 4, year), "counties": {r["fips"]: pick(r) for r in rows}, "us": pick(us[0])}

def bds():
    get = "YEAR,ESTAB,ESTABS_ENTRY,ESTABS_EXIT"
    rows = by_county("timeseries/bds", {"get": get, "NAICS": MFG, "time": "from 2005"})
    us = census_api("timeseries/bds", {"get": get, "NAICS": MFG, "time": "from 2005", "for": "us:1"})
    series = lambda rs: {r["YEAR"]: [num(r["ESTAB"]), num(r["ESTABS_ENTRY"]), num(r["ESTABS_EXIT"])] for r in sorted(rs, key=lambda r: r["YEAR"])}
    counties = defaultdict(list)
    for r in rows:
        counties[r["fips"]].append(r)
    return {"fields": ["establishments", "opened", "closed"], "counties": {f: series(rs) for f, rs in counties.items()}, "us": series(us)}

def nonemployer():
    get = "NAICS2022,NESTAB,NRCPTOT"
    year, rows = latest(lambda y: by_county("%d/nonemp" % y, {"get": get, "NAICS2022": MFG}), range(datetime.date.today().year - 1, 2019, -1))
    return {"year": year, "units": "receipts in $1,000", "counties": {r["fips"]: {"estab": num(r["NESTAB"]), "rcpt": num(r["NRCPTOT"])} for r in rows}}

def main():
    path = P("data", "census.json")
    try:
        out = json.load(open(path))
    except FileNotFoundError:
        out = {}
    out["source"] = ("U.S. Census Bureau via api.census.gov: Economic Census 2022, American Community Survey 5-year, "
                     "Business Dynamics Statistics, Nonemployer Statistics")
    ok = 0
    for name, fn in (("economic_census", economic_census), ("acs", acs), ("bds", bds), ("nonemployer", nonemployer)):
        try:
            out[name] = fn()
            ok += 1
            print("%s: %d counties" % (name, len(out[name]["counties"])))
        except Exception as e:
            print("%s: failed (%s); keeping the previous data" % (name, e))
    if not ok:
        raise SystemExit("no Census dataset could be pulled")
    out["pulled"] = datetime.date.today().isoformat()
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    print("wrote data/census.json")

if __name__ == "__main__":
    main()
