#!/usr/bin/env python3
"""Workforce figures from the BLS public data API: occupations, monthly jobs and unemployment.

    python3 scripts/pull_bls.py          # writes data/bls.json
    BLS_API_KEY=... python3 scripts/pull_bls.py   # optional key: larger requests, higher daily limit

- Occupations (OEWS, Occupational Employment and Wage Statistics, annual): jobs and median annual
  wage for production, engineering and technical occupations in the region's four metro areas,
  with U.S. figures for comparison. BLS suppresses estimates it cannot publish reliably; those are
  missing, not zero.
- Monthly manufacturing jobs (CES, Current Employment Statistics, not seasonally adjusted) for
  the four metro areas, in thousands, about three years.
- Unemployment rate and labor force (LAUS, Local Area Unemployment Statistics) for every county
  in the region, monthly, with the U.S. rate.
Without a key the API allows 25 requests a day of up to 25 series each; one run uses about ten.
"""
import datetime, json, os, sys, urllib.request
from common import P, COUNTIES

UA = {"Content-Type": "application/json", "User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
METROS = {"43780": ("South Bend–Mishawaka", "18"), "21140": ("Elkhart–Goshen", "18"), "35660": ("Niles", "26"), "33140": ("Michigan City–La Porte", "18")}
OCCUPATIONS = [  # 2018 SOC codes as OEWS uses them
    ("000000", "All occupations"), ("510000", "Production occupations (all)"), ("170000", "Architecture and engineering occupations (all)"),
    ("113051", "Industrial production managers"), ("511011", "Production supervisors"),
    ("172112", "Industrial engineers"), ("172141", "Mechanical engineers"), ("172071", "Electrical engineers"), ("151252", "Software developers"),
    ("173026", "Industrial engineering technicians"), ("173024", "Electro-mechanical and mechatronics technicians"), ("173027", "Mechanical engineering technicians"),
    ("499041", "Industrial machinery mechanics"), ("472111", "Electricians"),
    ("514041", "Machinists"), ("514111", "Tool and die makers"), ("519161", "CNC tool operators"), ("519162", "CNC tool programmers"),
    ("514121", "Welders, cutters, solderers and brazers"), ("514031", "Cutting, punching and press machine setters"),
    ("512090", "Assemblers and fabricators (misc.)"), ("519061", "Inspectors, testers and samplers"),
    ("512028", "Electrical and electromechanical assemblers"), ("512041", "Structural metal fabricators and fitters"),
    ("514081", "Multiple machine tool setters and operators"), ("514072", "Molding and casting machine setters"),
    ("519124", "Coating and painting machine setters"), ("517011", "Cabinetmakers and bench carpenters"),
    ("517042", "Woodworking machine setters"), ("519111", "Packaging and filling machine operators"),
    ("519198", "Production helpers"), ("537062", "Hand laborers and material movers"),
    ("537064", "Hand packers and packagers"), ("537051", "Industrial truck and tractor operators"),
]

def fetch(ids, start=None, end=None):
    key = os.environ.get("BLS_API_KEY")
    url = "https://api.bls.gov/publicAPI/%s/timeseries/data/" % ("v2" if key else "v1")
    size = 50 if key else 25
    out = {}
    for i in range(0, len(ids), size):
        body = {"seriesid": ids[i:i + size]}
        if start: body.update(startyear=str(start), endyear=str(end))
        if key: body["registrationkey"] = key
        r = json.load(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(), headers=UA), timeout=90))
        if r.get("status") != "REQUEST_SUCCEEDED":
            raise SystemExit("BLS API: %s %s" % (r.get("status"), r.get("message")))
        for s in r["Results"]["series"]:
            out[s["seriesID"]] = s["data"]
    return out

def num(v):
    try:
        return float(v.replace(",", ""))
    except (ValueError, AttributeError):
        return None   # "-" and "*" mark suppressed estimates

def main():
    only = sys.argv[sys.argv.index("--occupations") + 1:] if "--occupations" in sys.argv else None
    if only:
        return merge_occupations(only)
    data = {"source": "BLS public data API (OEWS, CES, LAUS)", "pulled": datetime.date.today().isoformat()}
    # occupations: employment (01) and annual median wage (13) per metro, and the U.S.
    occ_ids = {}
    for code, _ in OCCUPATIONS:
        for m in METROS:
            for dt in ("01", "13"):
                occ_ids["OEUM%07d000000%s%s" % (int(m), code, dt)] = (m, code, dt)
        for dt in ("01", "13"):
            occ_ids["OEUN0000000000000%s%s" % (code, dt)] = ("US", code, dt)
    got = fetch(list(occ_ids))
    year, occ = None, {code: {"name": name, "metros": {}, "us": {}} for code, name in OCCUPATIONS}
    for sid, (area, code, dt) in occ_ids.items():
        pts = got.get(sid) or []
        if not pts:
            continue
        year = max(year or "", pts[0]["year"])
        v = num(pts[0]["value"]); k = "emp" if dt == "01" else "median"
        (occ[code]["us"] if area == "US" else occ[code]["metros"].setdefault(area, {}))[k] = v
    data["occupations"] = {"year": year, "metros": {k: v[0] for k, v in METROS.items()}, "list": [dict(code=c, **occ[c]) for c, _ in OCCUPATIONS]}
    # monthly manufacturing jobs per metro, and unemployment per county
    y1 = datetime.date.today().year
    ces = {"SMU%s%s3000000001" % (st, m): m for m, (_, st) in METROS.items()}
    laus = {}
    for f in COUNTIES:
        laus["LAUCN%s0000000003" % f] = (f, "rate"); laus["LAUCN%s0000000006" % f] = (f, "force")
    got = fetch(list(ces) + list(laus) + ["LNU04000000"], y1 - 2, y1)
    series = lambda pts: [[p["year"] + "-" + p["period"][1:], num(p["value"])] for p in sorted(pts, key=lambda p: (p["year"], p["period"])) if p["period"].startswith("M") and p["period"] != "M13"]
    data["ces"] = {m: {"name": METROS[m][0], "months": series(got.get(sid) or [])} for sid, m in ces.items()}
    counties = {f: {"name": COUNTIES[f]} for f in COUNTIES}
    for sid, (f, k) in laus.items():
        counties[f][k] = series(got.get(sid) or [])
    data["laus"] = {"counties": counties, "us_rate": series(got.get("LNU04000000") or [])}
    json.dump(data, open(P("data", "bls.json"), "w"), indent=0)
    n_occ = sum(1 for o in data["occupations"]["list"] if o["metros"])
    print("occupations %s: %d of %d with metro data; CES months: %s; LAUS counties: %d"
          % (year, n_occ, len(OCCUPATIONS), {v["name"]: len(v["months"]) for v in data["ces"].values()}, sum(1 for c in counties.values() if c["rate"])))

def merge_occupations(codes):
    """Fetch a few occupations and add them to data/bls.json, keeping everything else."""
    data = json.load(open(P("data", "bls.json")))
    names = dict(OCCUPATIONS)
    ids = {}
    for code in codes:
        for m in METROS:
            for dt in ("01", "13"):
                ids["OEUM%07d000000%s%s" % (int(m), code, dt)] = (m, code, dt)
        for dt in ("01", "13"):
            ids["OEUN0000000000000%s%s" % (code, dt)] = ("US", code, dt)
    got = fetch(list(ids))
    lst = {o["code"]: o for o in data["occupations"]["list"]}
    for code in codes:
        lst[code] = {"code": code, "name": names[code], "metros": {}, "us": {}}
    for sid, (area, code, dt) in ids.items():
        pts = got.get(sid) or []
        if pts:
            v = num(pts[0]["value"]); k = "emp" if dt == "01" else "median"
            (lst[code]["us"] if area == "US" else lst[code]["metros"].setdefault(area, {}))[k] = v
    data["occupations"]["list"] = [lst[c] for c, _ in OCCUPATIONS if c in lst]
    json.dump(data, open(P("data", "bls.json"), "w"), indent=0)
    print("added %d occupations; %d with metro data" % (len(codes), sum(1 for c in codes if lst[c]["metros"])))

if __name__ == "__main__":
    main()
