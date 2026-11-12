#!/usr/bin/env python3
"""SBIR/STTR awards for companies in the map, from a CSV exported from SBIR.gov.

The SBIR.gov API sits behind a bot filter that rejects scripts, so this script reads the public
award export instead: on https://www.sbir.gov/awards choose State = Indiana (and Michigan), export
the results as CSV, and run

    python3 scripts/pull_sbir.py path/to/awards.csv [another.csv ...]   # writes data/sbir.json

Awards whose company city is in the Michiana list are matched to company files by name.
"""
import csv, json, sys, datetime
from common import P, companies, matcher

CITIES = {"south bend", "mishawaka", "elkhart", "goshen", "plymouth", "bremen", "walkerton", "argos", "warsaw", "nappanee", "la porte", "laporte",
          "michigan city", "granger", "notre dame", "niles", "benton harbor", "st. joseph", "saint joseph", "st joseph", "middlebury", "bristol",
          "wakarusa", "syracuse", "winona lake", "osceola", "new carlisle", "north liberty", "lakeville", "culver", "knox", "rochester", "ligonier",
          "kendallville", "columbia city", "dowagiac", "cassopolis", "edwardsburg", "buchanan", "stevensville", "paw paw", "south haven", "lagrange"}

def col(row, *names):
    for n in names:
        for k in row:
            if k and k.strip().lower() == n:
                return row[k]
    return ""

def main(paths):
    if not paths:
        sys.exit(__doc__)
    cs = companies(); match = matcher(cs)
    by_company, firms = {}, {}
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                city = col(row, "city", "company city").strip().lower()
                if city not in CITIES:
                    continue
                firm = col(row, "company", "firm", "company name").strip()
                amt = float((col(row, "award amount", "amount") or "0").replace("$", "").replace(",", "") or 0)
                agency = col(row, "agency"); year = col(row, "award year", "year")
                f = firms.setdefault(firm, {"city": city.title(), "count": 0, "amount": 0, "agencies": set()})
                f["count"] += 1; f["amount"] += amt; f["agencies"].add(agency)
                cid = match(firm, city)
                if cid:
                    e = by_company.setdefault(cid, {"count": 0, "amount": 0, "agencies": [], "years": []})
                    e["count"] += 1; e["amount"] += amt
                    if agency and agency not in e["agencies"]: e["agencies"].append(agency)
                    if year and year not in e["years"]: e["years"].append(year)
    for e in by_company.values():
        e["amount"] = round(e["amount"])
    unmatched = sorted(((f, d) for f, d in firms.items() if not match(f, d["city"])), key=lambda kv: -kv[1]["amount"])
    json.dump({"source": "SBIR.gov award export", "pulled": datetime.date.today().isoformat(), "companies": by_company,
               "firms_not_in_map": [{"firm": f, "city": d["city"], "count": d["count"], "amount": round(d["amount"]), "agencies": sorted(x for x in d["agencies"] if x)} for f, d in unmatched[:100]]},
              open(P("data", "sbir.json"), "w"), indent=0)
    print("matched %d companies; %d local SBIR firms not in the map" % (len(by_company), len(unmatched)))

if __name__ == "__main__":
    main(sys.argv[1:])
