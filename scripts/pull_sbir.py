#!/usr/bin/env python3
"""SBIR/STTR awards to companies in the Michiana cities, from SBIR.gov's public bulk award file.

    python3 scripts/pull_sbir.py                 # downloads the monthly file, writes data/sbir.json
    python3 scripts/pull_sbir.py awards.csv      # or reads a CSV exported from https://www.sbir.gov/awards

SBIR.gov publishes every award as one CSV, refreshed monthly (about 65 MB without abstracts):
https://data.www.sbir.gov/mod_awarddatapublic_no_abstract/award_data_no_abstract.csv
Awards whose company city is in the region are matched to company files by website domain, then
by name. Firms with awards that are not yet in the map are listed in data/sbir.json for review.
"""
import csv, io, json, sys, datetime, urllib.request
from common import P, companies, matcher, uei_index, company_path, set_field

BULK = "https://data.www.sbir.gov/mod_awarddatapublic_no_abstract/award_data_no_abstract.csv"
IN_CITIES = {"south bend", "mishawaka", "elkhart", "goshen", "plymouth", "bremen", "walkerton", "argos", "warsaw", "nappanee", "la porte", "laporte",
             "michigan city", "granger", "notre dame", "middlebury", "bristol", "wakarusa", "syracuse", "winona lake", "osceola", "new carlisle",
             "north liberty", "lakeville", "culver", "knox", "rochester", "ligonier", "kendallville", "columbia city", "lagrange", "albion",
             "pierceton", "milford", "cromwell", "bourbon", "topeka", "shipshewana", "howe", "westville", "new paris", "millersburg", "elkhart lake"}
MI_CITIES = {"niles", "benton harbor", "st. joseph", "saint joseph", "st joseph", "dowagiac", "cassopolis", "edwardsburg", "buchanan", "stevensville",
             "paw paw", "south haven", "union pier", "coloma", "berrien springs", "three oaks", "new buffalo", "bridgman", "watervliet", "hartford",
             "bangor", "lawton", "decatur", "marcellus", "vandalia", "three rivers", "sturgis", "constantine", "white pigeon", "centreville"}
CITY_SETS = {"Indiana": IN_CITIES, "IN": IN_CITIES, "Michigan": MI_CITIES, "MI": MI_CITIES}

def domain(u):
    u = (u or "").lower().strip()
    for pfx in ("https://", "http://", "www."):
        if u.startswith(pfx):
            u = u[len(pfx):]
    return u.split("/")[0]

def rows_from(source):
    if source:
        with open(source, newline="", encoding="utf-8-sig") as fh:
            yield from csv.DictReader(fh)
        return
    req = urllib.request.Request(BULK, headers={"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"})
    with urllib.request.urlopen(req, timeout=600) as r:
        text = io.TextIOWrapper(r, encoding="utf-8-sig", errors="replace", newline="")
        yield from csv.DictReader(text)

def main(args):
    cs = companies(); match = matcher(cs); by_uei = uei_index(cs); has_uei = {c["_id"] for c in cs if c.get("uei")}
    by_domain = {domain(c["website"]): c["_id"] for c in cs if c.get("website")}
    by_company, firms, learned, n = {}, {}, {}, 0
    for row in rows_from(args[0] if args else None):
        n += 1
        allowed = CITY_SETS.get((row.get("State") or "").strip())
        if not allowed or (row.get("City") or "").strip().lower() not in allowed:
            continue
        firm = (row.get("Company") or "").strip(); city = (row.get("City") or "").strip().title()
        state = "IN" if (row.get("State") or "").strip() in ("Indiana", "IN") else "MI"
        try:
            amt = float(row.get("Award Amount") or 0)
        except ValueError:
            amt = 0
        agency = (row.get("Agency") or "").replace("Department of War", "Department of Defense").strip()
        year = (row.get("Award Year") or "").strip(); phase = (row.get("Phase") or "").strip(); uei = (row.get("UEI") or "").strip()
        title = (row.get("Award Title") or "").strip()
        try:
            staff = int(float(row.get("Number Employees") or 0))
        except ValueError:
            staff = 0
        f = firms.setdefault(firm, {"city": city, "state": state, "count": 0, "amount": 0, "agencies": set(), "website": row.get("Company Website") or "",
                                    "uei": uei, "years": [], "titles": [], "staff": 0, "staff_year": ""})
        f["count"] += 1; f["amount"] += amt; f["agencies"].add(agency); f["years"].append(year); f["titles"].append((year, title))
        if staff and year >= f["staff_year"]:
            f["staff"], f["staff_year"] = staff, year
        cid = by_uei.get(uei) or by_domain.get(domain(row.get("Company Website"))) or match(firm, city)
        if cid and uei and cid not in has_uei and uei not in by_uei:
            learned.setdefault(cid, uei)
        if cid:
            e = by_company.setdefault(cid, {"count": 0, "amount": 0, "agencies": [], "years": [], "phases": {}, "firms": []})
            e["count"] += 1; e["amount"] += amt; e["phases"][phase] = e["phases"].get(phase, 0) + 1
            if agency and agency not in e["agencies"]: e["agencies"].append(agency)
            if year and year not in e["years"]: e["years"].append(year)
            if firm not in e["firms"]: e["firms"].append(firm)
    for e in by_company.values():
        e["amount"] = round(e["amount"]); e["years"].sort()
    def matched(f, d):
        return by_uei.get(d["uei"]) or by_domain.get(domain(d["website"])) or match(f, d["city"])
    unmatched = sorted(((f, d) for f, d in firms.items() if not matched(f, d)), key=lambda kv: -kv[1]["amount"])
    json.dump({"source": "SBIR.gov public award data file (monthly)", "pulled": datetime.date.today().isoformat(), "companies": by_company,
               "firms_not_in_map": [{"firm": f, "city": d["city"], "state": d["state"], "count": d["count"], "amount": round(d["amount"]),
                                     "agencies": sorted(x for x in d["agencies"] if x), "website": d["website"], "uei": d["uei"],
                                     "first_year": min(y for y in d["years"] if y) if any(d["years"]) else "", "last_year": max(d["years"]) if d["years"] else "",
                                     "titles": [t for y, t in sorted(d["titles"], reverse=True)[:5]], "staff": d["staff"], "staff_year": d["staff_year"]}
                                    for f, d in unmatched]},
              open(P("data", "sbir.json"), "w"), indent=0)
    for cid, uei in learned.items():
        path = company_path(cid)
        if path:
            set_field(path, "uei", uei)
    print("read %d awards; %d firms in Michiana cities; matched %d companies; %d local SBIR firms not in the map; stored %d UEIs"
          % (n, len(firms), len(by_company), len(unmatched), len(learned)))

if __name__ == "__main__":
    main(sys.argv[1:])
