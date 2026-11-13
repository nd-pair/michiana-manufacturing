"""The Physical-AI Opportunity Index, from data/opportunity.toml and the pulled datasets. Used by build.py.

Every part compares the region with the U.S. (100 = the U.S. average). A pillar is the mean of its
parts; the index is the weighted geometric mean of the pillars, so a pillar near zero, or falling
manufacturing jobs, pay or value added, pulls the whole index down.
"""
import math, tomllib
from common import P

def _ratio(local, us, invert=False):
    if not local or not us:
        return None
    return round(100 * (us / local if invert else local / us), 1)

def compute(bls, qcew, qwi, bea, task, available_share):
    spec = tomllib.load(open(P("data", "opportunity.toml"), "rb"))
    occ = (bls.get("occupations") or {}).get("list", [])
    fit = (task or {}).get("occupations", {})
    by = {o["code"]: o for o in occ}
    allocc = by.get("000000")
    local_all = sum((m.get("emp") or 0) for m in allocc["metros"].values()) if allocc else 0
    us_all = (allocc or {}).get("us", {}).get("emp") or 0
    detail = [o for o in occ if not o["code"].endswith("0000")]
    loc = lambda o: sum((m.get("emp") or 0) for m in o["metros"].values())
    pillars = []

    # 1. task fit
    rows = [o for o in detail if o["code"] in fit and o["us"].get("emp")]
    lf = sum(loc(o) * fit[o["code"]]["fit"] for o in rows) / local_all if local_all else None
    uf = sum(o["us"]["emp"] * fit[o["code"]]["fit"] for o in rows) / us_all if us_all else None
    pillars.append({"id": "task", "name": "Task fit", "what": "hard, repetitive or hazardous work in local jobs that humanoids could take on",
                    "parts": [{"name": "Task-fit-weighted production jobs per job", "local": lf and round(lf, 2), "us": uf and round(uf, 2), "score": _ratio(lf, uf),
                               "note": "%d occupations, O*NET task traits weighted by jobs" % len(rows)}]})

    # 2. high-mix potential
    t = (qcew.get("specialization") or {}).get("total", {})
    size_l = t.get("emp") / t["estab"] if t.get("estab") else None
    size_u = t.get("us_emp") / t["us_estab"] if t.get("us_estab") else None
    pillars.append({"id": "highmix", "name": "High-mix potential", "what": "job shops and custom, short-run industries, where flexible robots beat fixed automation",
                    "parts": [{"name": "Share of manufacturing jobs in custom and short-run industries", "local": t.get("highmix_share"), "us": t.get("us_highmix_share"),
                               "score": _ratio(t.get("highmix_share"), t.get("us_highmix_share")), "unit": "share", "note": "lower bound where BLS withholds county figures"},
                              {"name": "Workers per manufacturing establishment (smaller scores higher)", "local": size_l and round(size_l, 1), "us": size_u and round(size_u, 1),
                               "score": _ratio(size_l, size_u, invert=True)}]})

    # 3. labor pressure
    L = bls.get("laus") or {}
    rates = [(c["rate"][-1][1], (c.get("force") or [[None, 0]])[-1][1] or 0) for c in L.get("counties", {}).values() if c.get("rate") and c["rate"][-1][1] is not None]
    ur = sum(r * f for r, f in rates) / sum(f for _, f in rates) if rates and sum(f for _, f in rates) else None
    uu = L.get("us_rate", [[None, None]])[-1][1] if L.get("us_rate") else None
    q = qwi or {}
    pillars.append({"id": "labor", "name": "Labor pressure", "what": "a tight, aging, high-turnover workforce, where robots fill roles employers cannot staff",
                    "parts": [{"name": "Unemployment rate (lower scores higher)", "local": ur and round(ur, 1), "us": uu, "score": _ratio(ur, uu, invert=True), "unit": "%"},
                              {"name": "Manufacturing workers aged 55 and older", "local": q.get("region", {}).get("age55"), "us": q.get("us", {}).get("age55"),
                               "score": _ratio(q.get("region", {}).get("age55"), q.get("us", {}).get("age55")), "unit": "share"},
                              {"name": "Quarterly manufacturing turnover", "local": q.get("region", {}).get("turnover"), "us": q.get("us", {}).get("turnover"),
                               "score": _ratio(q.get("region", {}).get("turnover"), q.get("us", {}).get("turnover")), "unit": "share"}]})

    # 4. adoption readiness
    rd = [by[c] for c in spec["readiness"]["soc"] if c in by and by[c]["us"].get("emp")]
    rl = 1000 * sum(loc(o) for o in rd) / local_all if local_all else None
    ru = 1000 * sum(o["us"]["emp"] for o in rd) / us_all if us_all else None
    pillars.append({"id": "readiness", "name": "Adoption readiness", "what": "people who install, program and maintain automation",
                    "parts": [{"name": "Mechanics, electricians, technicians and engineers per 1,000 jobs", "local": rl and round(rl, 1), "us": ru and round(ru, 1), "score": _ratio(rl, ru)}]})

    # 5. local supply (no U.S. benchmark: scaled so that half of a humanoid's cost available locally = 100)
    sc = spec["supply"]["scale"]
    pillars.append({"id": "supply", "name": "Local supply", "what": "the share of a humanoid's cost available from two or more local suppliers",
                    "parts": [{"name": "Share of a humanoid's cost available locally", "local": available_share, "us": None,
                               "score": round(sc * available_share, 1) if available_share is not None else None, "unit": "pct",
                               "note": "scored as %g times the share, so half of the robot = 100" % sc}]})

    # 6. shared prosperity: jobs and pay over five years, value added per job
    def growth(years):
        ys = sorted(years)
        if len(ys) < 6:
            return None, None, None
        a, b = years[ys[-6]], years[ys[-1]]
        return b["emp"] / a["emp"], b["pay"] / a["pay"], (ys[-6], ys[-1])
    reg = {}
    for c in qcew.get("counties", {}).values():
        for y, v in c["years"].items():
            r = reg.setdefault(str(y), {"emp": 0, "wages": 0})
            r["emp"] += v["emp"]; r["wages"] += v["emp"] * v["pay"]
    reg = {y: {"emp": v["emp"], "pay": v["wages"] / v["emp"]} for y, v in reg.items() if v["emp"]}
    ge, gp, span = growth(reg)
    ue, up, _ = growth(qcew.get("us") or {})
    gdp = (bea or {}).get("manufacturing_gdp", {})
    va_l = va_u = vyear = None
    if gdp.get("00000"):
        vyear = max(y for y in gdp["00000"] if (qcew.get("us") or {}).get(y))
        cs = [f for f in qcew.get("counties", {}) if gdp.get(f, {}).get(vyear) and qcew["counties"][f]["years"].get(vyear)]
        if cs:
            va_l = sum(gdp[f][vyear] for f in cs) / sum(qcew["counties"][f]["years"][vyear]["emp"] for f in cs)
            va_u = gdp["00000"][vyear] / qcew["us"][vyear]["emp"]
    pillars.append({"id": "prosperity", "name": "Shared prosperity", "what": "manufacturing jobs, pay and value added per job, so the index rises only if workers gain too",
                    "parts": [{"name": "Manufacturing job growth %s–%s" % span if span else "Manufacturing job growth", "local": ge and round(ge - 1, 3), "us": ue and round(ue - 1, 3),
                               "score": _ratio(ge, ue), "unit": "growth"},
                              {"name": "Manufacturing pay growth %s–%s" % span if span else "Manufacturing pay growth", "local": gp and round(gp - 1, 3), "us": up and round(up - 1, 3),
                               "score": _ratio(gp, up), "unit": "growth"},
                              {"name": "Manufacturing value added per job, %s" % vyear, "local": va_l and round(va_l), "us": va_u and round(va_u),
                               "score": _ratio(va_l, va_u), "unit": "usd", "note": "counties BEA publishes"}]})

    for p in pillars:
        s = [x["score"] for x in p["parts"] if x["score"] is not None]
        p["score"] = round(sum(s) / len(s), 1) if s else None
        p["weight"] = spec["weights"].get(p["id"], 1)
    have = [p for p in pillars if p["score"]]
    w = sum(p["weight"] for p in have)
    index = round(math.exp(sum(p["weight"] * math.log(p["score"]) for p in have) / w), 1) if have and w else None

    # occupation table: jobs, task fit and its strongest traits, pay
    tnames = {t["id"]: t["name"] for t in (task or {}).get("traits", [])}
    table = []
    for o in detail:
        f = fit.get(o["code"])
        jobs = loc(o)
        if not jobs:
            continue
        ms = [m for m in o["metros"].values() if m.get("emp") and m.get("median")]
        med = sum(m["emp"] * m["median"] for m in ms) / sum(m["emp"] for m in ms) if ms else None
        top = sorted((f or {}).get("traits", {}).items(), key=lambda kv: -kv[1])
        table.append({"code": o["code"], "name": o["name"], "jobs": jobs, "per1000": round(1000 * jobs / local_all, 1) if local_all else None,
                      "fit": f and f["fit"], "traits": [tnames.get(k, k) for k, v in top if v >= 50][:3], "median": med and round(med), "us_median": o["us"].get("median"),
                      "readiness": o["code"] in spec["readiness"]["soc"]})
    return {"index": index, "pillars": pillars, "occupations": sorted(table, key=lambda r: -(r["jobs"] * (r["fit"] or 0))),
            "oews_year": (bls.get("occupations") or {}).get("year"), "qcew_year": (qcew.get("specialization") or {}).get("year"), "bea_year": vyear,
            "qwi_quarters": (q.get("region") or {}).get("age_quarters", []), "sources": {k: (v or {}).get("source", "") for k, v in (("task", task), ("qwi", qwi), ("bea", bea))}}
