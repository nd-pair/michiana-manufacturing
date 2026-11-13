#!/usr/bin/env python3
"""Inputs for the Physical-AI Opportunity Index that are not on the BLS API.

    python3 scripts/pull_workforce.py            # all three sources
    python3 scripts/pull_workforce.py onet qwi   # only some

- onet: task traits per occupation from O*NET 31.0 (work context and work activities, CC BY 4.0,
  onetcenter.org); traits and elements are set in data/opportunity.toml. Writes data/task_fit.json.
- qwi: private manufacturing (NAICS 31-33) employment by age and turnover from the Census Bureau's
  Quarterly Workforce Indicators (LEHD bulk files; the Indiana and Michigan files are streamed and
  filtered, not stored), for the region's counties and the U.S. Writes data/qwi.json.
- bea: manufacturing value added (GDP) by county from the Bureau of Economic Analysis table CAGDP2.
  Writes data/bea.json.
Each source is independent; a failure leaves its previous file in place.
"""
import csv, datetime, gzip, io, json, sys, tomllib, urllib.request, zipfile
from collections import defaultdict
from common import P, COUNTIES

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
ONET = "https://www.onetcenter.org/dl_files/database/db_31_0_csv/%s.csv"
QWI = "https://lehd.ces.census.gov/data/qwi/latest_release/%s/qwi_%s_sa_f_%s_ns_op_u.csv.gz"
BEA = "https://apps.bea.gov/regional/zip/CAGDP2.zip"

def get(url, timeout=600):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)

def onet():
    spec = tomllib.load(open(P("data", "opportunity.toml"), "rb"))
    want = {e: t["id"] for t in spec["trait"] for e in t["elements"]}
    vals = defaultdict(lambda: defaultdict(list))      # 6-digit SOC -> element -> values (all O*NET detail codes)
    titles = {}
    for name, scale in (("work_context", "CX"), ("work_activities", "IM")):
        text = io.TextIOWrapper(get(ONET % name), encoding="utf-8")
        for r in csv.DictReader(text):
            if r["Element ID"] in want and r["Scale ID"] == scale and r.get("Recommend Suppress") != "Y":
                soc = r["O*NET-SOC Code"][:7].replace("-", "")
                vals[soc][r["Element ID"]].append(float(r["Data Value"]))
                titles.setdefault(soc, r["Title"])
    out = {}
    for soc, els in vals.items():
        traits = {}
        for t in spec["trait"]:
            xs = [sum(els[e]) / len(els[e]) for e in t["elements"] if els.get(e)]
            if xs:
                traits[t["id"]] = round(100 * (sum(xs) / len(xs) - 1) / 4, 1)
        if len(traits) == len(spec["trait"]):
            out[soc] = {"title": titles[soc], "traits": traits, "fit": round(sum(traits.values()) / len(traits), 1)}
    # broad OEWS groups ending in 0 (such as 51-2090) take the mean of their detailed occupations
    for soc in list(out):
        broad = soc[:5] + "0"
        if broad != soc and broad not in out:
            kids = [v for k, v in out.items() if k[:5] == soc[:5] and k[-1] != "0"]
            out[broad] = {"title": "(group) " + kids[0]["title"], "fit": round(sum(k["fit"] for k in kids) / len(kids), 1),
                          "traits": {t: round(sum(k["traits"][t] for k in kids) / len(kids), 1) for t in kids[0]["traits"]}}
    json.dump({"source": "O*NET 31.0 database (work context, work activities), CC BY 4.0", "pulled": datetime.date.today().isoformat(),
               "traits": [{"id": t["id"], "name": t["name"]} for t in spec["trait"]], "occupations": out},
              open(P("data", "task_fit.json"), "w"), indent=0)
    print("onet: task fit for %d occupations" % len(out))

def qwi():
    keep = lambda r: r["industry"] == "31-33" and r["sex"] == "0" and r["agegrp"] in ("A00", "A07", "A08") and r["ownercode"] == "A05"
    def rows(st, geo):
        with get(QWI % (st, st, geo)) as resp:
            for r in csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8")):
                if keep(r):
                    yield r
    num = lambda v: float(v) if v not in ("", None) else None
    region = defaultdict(lambda: defaultdict(dict))     # quarter -> county -> agegrp -> row
    for st in ("in", "mi"):
        for r in rows(st, "gc"):
            if r["geography"] in COUNTIES:
                region["%s-Q%s" % (r["year"], r["quarter"])][r["geography"]][r["agegrp"]] = r
    us = defaultdict(dict)
    for r in rows("us", "gn"):
        us["%s-Q%s" % (r["year"], r["quarter"])][r["agegrp"]] = r
    def summary(get_rows, age_q=None, turn_q=None):
        """Mean over the latest four quarters with data (limited to the given quarters, so region and
        U.S. cover the same period): share of workers 55+, and employment-weighted turnover."""
        age, turn = [], []
        for q in sorted(get_rows, reverse=True):
            groups = get_rows[q]
            e = sum(num(g["A00"]["Emp"]) or 0 for g in groups if "A00" in g)
            old = sum((num(g.get("A07", {}).get("Emp")) or 0) + (num(g.get("A08", {}).get("Emp")) or 0) for g in groups)
            if e and len(age) < 4 and (age_q is None or q in age_q):
                age.append((q, old / e))
            tw = [(num(g["A00"]["TurnOvrS"]), num(g["A00"]["EmpS"]) or num(g["A00"]["Emp"]) or 0) for g in groups if "A00" in g and num(g["A00"].get("TurnOvrS")) is not None]
            if tw and sum(w for _, w in tw) and len(turn) < 4 and (turn_q is None or q in turn_q):
                turn.append((q, sum(t * w for t, w in tw) / sum(w for _, w in tw)))
            if len(age) == 4 and len(turn) == 4:
                break
        return {"age55": round(sum(v for _, v in age) / len(age), 4), "age_quarters": [q for q, _ in age],
                "turnover": round(sum(v for _, v in turn) / len(turn), 4), "turnover_quarters": [q for q, _ in turn]}
    nat = summary({q: [g] for q, g in us.items()})
    reg = summary({q: list(c.values()) for q, c in region.items()}, set(nat["age_quarters"]), set(nat["turnover_quarters"]))
    # yearly history: the mean of each year's four quarters where both region and U.S. have them
    def per_quarter(get_rows):
        out = {}
        for q, groups in get_rows.items():
            e = sum(num(g["A00"]["Emp"]) or 0 for g in groups if "A00" in g)
            old = sum((num(g.get("A07", {}).get("Emp")) or 0) + (num(g.get("A08", {}).get("Emp")) or 0) for g in groups)
            tw = [(num(g["A00"]["TurnOvrS"]), num(g["A00"]["EmpS"]) or num(g["A00"]["Emp"]) or 0) for g in groups if "A00" in g and num(g["A00"].get("TurnOvrS")) is not None]
            out[q] = {"age55": old / e if e else None, "turnover": sum(t * w for t, w in tw) / sum(w for _, w in tw) if tw and sum(w for _, w in tw) else None}
        return out
    rq, uq = per_quarter({q: list(c.values()) for q, c in region.items()}), per_quarter({q: [g] for q, g in us.items()})
    history = {}
    for y in sorted({q[:4] for q in rq}):
        row = {}
        for k in ("age55", "turnover"):
            qs = [q for q in ("%s-Q%d" % (y, i) for i in range(1, 5)) if (rq.get(q) or {}).get(k) is not None and (uq.get(q) or {}).get(k) is not None]
            if len(qs) == 4:
                row[k] = round(sum(rq[q][k] for q in qs) / 4, 4); row["us_" + k] = round(sum(uq[q][k] for q in qs) / 4, 4)
        if row:
            history[y] = row
    json.dump({"source": "U.S. Census Bureau, LEHD Quarterly Workforce Indicators (private, NAICS 31-33)", "pulled": datetime.date.today().isoformat(),
               "region": reg, "us": nat, "history": history}, open(P("data", "qwi.json"), "w"), indent=1)
    print("qwi: region 55+ %.1f%% turnover %.1f%%; U.S. 55+ %.1f%% turnover %.1f%%" % (100 * reg["age55"], 100 * reg["turnover"], 100 * nat["age55"], 100 * nat["turnover"]))

def bea():
    z = zipfile.ZipFile(io.BytesIO(get(BEA).read()))
    name = next(n for n in z.namelist() if n.startswith("CAGDP2__ALL_AREAS") and n.endswith(".csv"))
    want = set(COUNTIES) | {"00000"}
    out = defaultdict(dict)
    for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="latin-1")):
        fips = (r.get("GeoFIPS") or "").strip().strip('"').strip()
        if fips in want and (r.get("LineCode") or "").strip() == "12":
            for k, v in r.items():
                if k and k.isdigit():
                    try:
                        out[fips][k] = int(float(v)) * 1000     # thousands of current dollars
                    except (ValueError, TypeError):
                        pass                                    # (D): withheld
    json.dump({"source": "U.S. Bureau of Economic Analysis, CAGDP2 (GDP by county, manufacturing), current dollars", "pulled": datetime.date.today().isoformat(),
               "manufacturing_gdp": out}, open(P("data", "bea.json"), "w"), indent=0)
    print("bea: manufacturing GDP for %d areas, latest year %s" % (len(out), max(max(v) for v in out.values() if v)))

if __name__ == "__main__":
    for part in (sys.argv[1:] or ["onet", "qwi", "bea"]):
        try:
            {"onet": onet, "qwi": qwi, "bea": bea}[part]()
        except Exception as e:
            print(part, "skipped:", type(e).__name__, e)
