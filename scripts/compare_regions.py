#!/usr/bin/env python3
"""Monthly comparison of the Physical-AI Opportunity Index across the regions in data/regions.toml.

    python3 scripts/compare_regions.py             # refresh what is due, score, write data/comparison.json
    python3 scripts/compare_regions.py --offline   # score from the cache only

Same pillars, parts, weights and U.S. benchmarks as the map (scripts/opportunity.py, data/opportunity.toml),
so run it after pull_qcew.py, pull_bls.py and pull_workforce.py, whose files it reads for the U.S. side.
Shown at the bottom of the site's Physical AI readiness tab.

Sources and how often they are fetched:
- QCEW (data.bls.gov/cew, no API limit): county manufacturing jobs, establishments and pay, by 6-digit
  NAICS for the latest year in data/qcew.json; county totals for five years earlier and for the BEA year.
  Every run.
- BEA CAGDP2: county manufacturing value added. Every run (one zip file).
- Census QWI (LEHD bulk files, one per state): workers 55+ and turnover. Downloaded again only when the
  state's file changed (its Last-Modified date); the filtered rows are cached.
- BLS OEWS (BLS API): occupations per metro area. Fetched again only when data/bls.json has a newer
  survey year than the cache; Michiana's come from data/bls.json.
- BLS LAUS (BLS API): unemployment, latest month per county. Every run; Michiana's from data/bls.json.
With the BLS_API_KEY secret a normal month takes 2 API requests, and the yearly occupation refresh 8 more.

data/comparison.json holds the latest scores, a monthly history, and the cached inputs. An unavailable
source leaves the cached values in place; a region missing a pillar gets no index.
"""
import csv, datetime, gzip, io, json, math, os, sys, time, tomllib, urllib.error, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
from common import P
import pull_bls as b

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
QCEW_AREA = "https://data.bls.gov/cew/data/api/%s/a/area/%s.csv"
QCEW_IND = "https://data.bls.gov/cew/data/api/%s/a/industry/1013.csv"
QWI = "https://lehd.ces.census.gov/data/qwi/latest_release/%s/qwi_%s_sa_f_gc_ns_op_u.csv.gz"
BEA = "https://apps.bea.gov/regional/zip/CAGDP2.zip"
STATES = {"01": "al", "02": "ak", "04": "az", "05": "ar", "06": "ca", "08": "co", "09": "ct", "10": "de", "11": "dc", "12": "fl", "13": "ga",
          "15": "hi", "16": "id", "17": "il", "18": "in", "19": "ia", "20": "ks", "21": "ky", "22": "la", "23": "me", "24": "md", "25": "ma",
          "26": "mi", "27": "mn", "28": "ms", "29": "mo", "30": "mt", "31": "ne", "32": "nv", "33": "nh", "34": "nj", "35": "nm", "36": "ny",
          "37": "nc", "38": "nd", "39": "oh", "40": "ok", "41": "or", "42": "pa", "44": "ri", "45": "sc", "46": "sd", "47": "tn", "48": "tx",
          "49": "ut", "50": "vt", "51": "va", "53": "wa", "54": "wv", "55": "wi", "56": "wy"}
OUT = P("data", "comparison.json")

def get(url, timeout=300, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
        except (urllib.error.URLError, TimeoutError) as e:
            if i == tries - 1:
                raise
            print("  retry %s (%s)" % (url, e), flush=True); time.sleep(15)

def fl(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None

def ratio(l, u, inv=False):
    return (100 * (u / l if inv else l / u)) if l and u else None

def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None

# ---------------------------------------------------------------- inputs

def qcew_area(year, fips, spec, hum):
    """County totals the index needs: all jobs, manufacturing jobs and establishments, jobs in high-mix
    industries, and establishments in each build-to-print part's industries."""
    six = {}
    agg = {"all": 0, "mfg": 0, "mfg_estab": 0, "hm": 0, "parts": {}}
    for r in csv.DictReader(io.TextIOWrapper(get(QCEW_AREA % (year, fips)), encoding="utf-8", errors="replace")):
        c = r["industry_code"]
        if r.get("own_code") != "5":
            continue
        emp, est = fl(r["annual_avg_emplvl"]) or 0, fl(r["annual_avg_estabs"]) or 0
        if c == "10":
            agg["all"] = emp
        elif c == "31-33":
            agg["mfg"], agg["mfg_estab"] = emp, est
        elif len(c) == 6 and c.isdigit() and c[:2] in ("31", "32", "33"):
            six[c] = (emp, est)
    agg["hm"] = sum(e for k, (e, _) in six.items() if k.startswith(tuple(spec["highmix"]["naics"])))
    for comp in hum["component"]:
        if comp.get("build_to_print"):
            agg["parts"][comp["id"]] = sum(n for k, (_, n) in six.items() if k.startswith(tuple(comp.get("naics", []))))
    return fips, agg

def qcew_totals(year, counties):
    out = {}
    for r in csv.DictReader(io.TextIOWrapper(get(QCEW_IND % year), encoding="utf-8", errors="replace")):
        if r.get("own_code") == "5" and r["area_fips"] in counties:
            out[r["area_fips"]] = {"emp": fl(r["annual_avg_emplvl"]) or 0, "pay": fl(r["avg_annual_pay"]) or 0}
    return out

def bea_gdp(counties):
    z = zipfile.ZipFile(io.BytesIO(get(BEA, timeout=600).read()))
    name = next(n for n in z.namelist() if n.startswith("CAGDP2__ALL_AREAS") and n.endswith(".csv"))
    out = {}
    for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="latin-1")):
        f = (r.get("GeoFIPS") or "").strip().strip('"').strip()
        if f in counties and (r.get("LineCode") or "").strip() == "12":
            out[f] = {k: int(fl(v)) * 1000 for k, v in r.items() if k and k.isdigit() and fl(v) is not None}   # thousands of dollars
    return out

def qwi_state(st, counties):
    """Rows for the state's counties over the last four years or so: quarter -> [all workers, workers 55+, turnover, stable workers]."""
    keep = {}
    with get(QWI % (st, st), timeout=900) as resp:
        for r in csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8")):
            if r["geography"] in counties and r["industry"] == "31-33" and r["sex"] == "0" and r["ownercode"] == "A05" and r["agegrp"] in ("A00", "A07", "A08") and r["year"] >= str(datetime.date.today().year - 4):
                g = keep.setdefault(r["geography"], {}).setdefault("%s-Q%s" % (r["year"], r["quarter"]), [None, 0.0, None, None])
                if r["agegrp"] == "A00":
                    g[0], g[2], g[3] = fl(r["Emp"]), fl(r["TurnOvrS"]), fl(r["EmpS"])
                else:
                    g[1] += fl(r["Emp"]) or 0
    return keep

# ---------------------------------------------------------------- scoring

def score(reg, inp, bench, spec, hum):
    cs, A = reg["counties"], [inp["qcew"].get(f, {}) for f in reg["counties"]]
    us, Y = bench["qcew_us"], bench["year"]
    pillars, parts, facts = {}, {}, {}

    # task fit and adoption readiness: occupations in the region's metro areas
    jobs = {c: sum((inp["oews"].get(m) or {}).get(c) or 0 for m in reg["msas"]) for c in bench["occ_us"]}
    local_all, us_all = jobs.get("000000"), bench["occ_us"].get("000000")
    fit, occ_us = bench["fit"], bench["occ_us"]
    detail = [c for c in occ_us if not c.endswith("0000") and c in fit and occ_us[c]]
    lf = sum(jobs[c] * fit[c]["fit"] for c in detail) / local_all if local_all else None
    parts["task"] = [ratio(lf, sum(occ_us[c] * fit[c]["fit"] for c in detail) / us_all)]
    rd = [c for c in spec["readiness"]["soc"] if occ_us.get(c)]
    rl = 1000 * sum(jobs.get(c) or 0 for c in rd) / local_all if local_all else None
    parts["readiness"] = [ratio(rl, 1000 * sum(occ_us[c] for c in rd) / us_all)]
    facts.update(metro_jobs=local_all, readiness_per_1000=rl and round(rl, 1))

    # high-mix: share of manufacturing jobs in high-mix industries, and establishment size (inverted)
    m_emp, m_est = sum(a.get("mfg", 0) for a in A), sum(a.get("mfg_estab", 0) for a in A)
    t_emp, hm_emp = sum(a.get("all", 0) for a in A), sum(a.get("hm", 0) for a in A)
    parts["highmix"] = [ratio(hm_emp / m_emp if m_emp else None, bench["us_hm"] / us[Y]["emp"]),
                        ratio(m_emp / m_est if m_est else None, us[Y]["emp"] / us[Y]["estab"], inv=True)]
    facts.update(mfg_jobs=round(m_emp), mfg_share=round(m_emp / t_emp, 3) if t_emp else None, highmix_share=round(hm_emp / m_emp, 3) if m_emp else None)

    # labor pressure: unemployment (inverted), workers 55+, turnover; QWI over the U.S. quarters
    ls = [inp["laus"][f] for f in cs if (inp["laus"].get(f) or {}).get("rate") is not None and inp["laus"][f].get("force")]
    ur = sum(v["rate"] * v["force"] for v in ls) / sum(v["force"] for v in ls) if ls else None
    def qmean(qs, f):
        vals = []
        for q in qs:
            gs = [inp["qwi"].get(c, {}).get(q) for c in cs]
            gs = [g for g in gs if g and g[0]]
            if gs:
                vals.append(f(gs))
        return sum(vals) / len(vals) if vals and len(vals) == len(qs) else None
    age = qmean(bench["qwi_us"]["age_quarters"], lambda gs: sum(g[1] for g in gs) / sum(g[0] for g in gs))
    def turn(gs):
        tw = [(g[2], g[3] or g[0]) for g in gs if g[2] is not None]
        return sum(t * w for t, w in tw) / sum(w for _, w in tw) if tw and sum(w for _, w in tw) else None
    tv = qmean(bench["qwi_us"]["turnover_quarters"], turn)
    parts["labor"] = [ratio(ur, bench["us_rate"], inv=True), ratio(age, bench["qwi_us"]["age55"]), ratio(tv, bench["qwi_us"]["turnover"])]
    facts.update(unemployment=ur and round(ur, 2), age55=age and round(age, 3), turnover=tv and round(tv, 3))

    # local supply: twice the share of a humanoid's cost whose build-to-print parts have 2+ establishments
    avail = sum(c["cost"] for c in hum["component"] if c.get("build_to_print") and sum((a.get("parts") or {}).get(c["id"], 0) for a in A) >= 2)
    parts["supply"] = [spec["supply"]["scale"] * avail]

    # shared prosperity: five-year job and pay growth, value added per job
    y0, T = str(int(Y) - 5), inp["totals"]
    have = [f for f in cs if f in T.get(y0, {}) and f in T.get(Y, {})]
    e0, e1 = sum(T[y0][f]["emp"] for f in have), sum(T[Y][f]["emp"] for f in have)
    w0, w1 = sum(T[y0][f]["emp"] * T[y0][f]["pay"] for f in have), sum(T[Y][f]["emp"] * T[Y][f]["pay"] for f in have)
    vy = bench["va_year"]
    vc = [f for f in cs if (inp["bea"].get(f) or {}).get(vy) and (T.get(vy) or {}).get(f, {}).get("emp")]
    va = sum(inp["bea"][f][vy] for f in vc) / sum(T[vy][f]["emp"] for f in vc) if vc else None
    parts["prosperity"] = [ratio(e1 / e0 if e0 else None, us[Y]["emp"] / us[y0]["emp"]),
                           ratio((w1 / e1) / (w0 / e0) if e0 and e1 else None, us[Y]["pay"] / us[y0]["pay"]),
                           ratio(va, bench["us_va"])]
    facts.update(job_growth=round(e1 / e0 - 1, 3) if e0 else None, va_per_job=va and round(va))

    for k, v in parts.items():
        pillars[k] = mean(v)
    W = spec["weights"]
    index = math.exp(sum(W[k] * math.log(v) for k, v in pillars.items()) / sum(W[k] for k in pillars)) if all(pillars.values()) else None
    rnd = lambda x: None if x is None else round(x, 1)
    return {"index": rnd(index), "pillars": {k: rnd(v) for k, v in pillars.items()}, "parts": {k: [rnd(x) for x in v] for k, v in parts.items()},
            "missing": [k for k, v in pillars.items() if not v], "facts": facts}

# ---------------------------------------------------------------- main

def main(offline=False):
    regions = tomllib.load(open(P("data", "regions.toml"), "rb"))["region"]
    spec = tomllib.load(open(P("data", "opportunity.toml"), "rb")); hum = tomllib.load(open(P("data", "humanoid.toml"), "rb"))
    qcew, bls = json.load(open(P("data", "qcew.json"))), json.load(open(P("data", "bls.json")))
    qwi_us, bea_us = json.load(open(P("data", "qwi.json")))["us"], json.load(open(P("data", "bea.json")))["manufacturing_gdp"]["00000"]
    old = json.load(open(OUT)) if os.path.exists(OUT) else {}
    cache = old.get("cache") or {}
    for k in ("qcew", "totals", "bea", "qwi", "qwi_files", "oews", "oews_year", "laus"):
        cache.setdefault(k, {})
    counties = sorted({f for r in regions for f in r["counties"]})
    Y = str(qcew["specialization"]["year"])
    vy = max(y for y in bea_us if y in qcew["us"])
    log = []

    def step(name, fn):
        try:
            fn(); log.append(name + ": ok")
        except Exception as e:
            log.append("%s: failed (%s), cached values kept" % (name, e)); print("  " + log[-1], flush=True)

    if not offline:
        def do_qcew():
            with ThreadPoolExecutor(8) as ex:
                got = dict(ex.map(lambda f: qcew_area(Y, f, spec, hum), counties))
            cache["qcew"] = got; cache["qcew_year"] = Y
            for y in sorted({str(int(Y) - 5), Y, vy}):
                cache["totals"][y] = qcew_totals(y, set(counties))
        step("qcew", do_qcew)
        step("bea", lambda: cache.update(bea=bea_gdp(set(counties))))

        def do_qwi():
            for sf in sorted({f[:2] for f in counties}):
                st = STATES[sf]
                lm = urllib.request.urlopen(urllib.request.Request(QWI % (st, st), headers=UA, method="HEAD"), timeout=60).headers.get("Last-Modified", "")
                if lm and cache["qwi_files"].get(st) == lm:
                    continue
                print("  qwi %s (%s)" % (st, lm), flush=True)
                rows = qwi_state(st, {f for f in counties if f[:2] == sf})
                for f in [f for f in cache["qwi"] if f[:2] == sf]:
                    del cache["qwi"][f]
                cache["qwi"].update(rows); cache["qwi_files"][st] = lm
        step("qwi", do_qwi)

        # Michiana's occupations and unemployment come from data/bls.json; the others from the BLS API
        home_msas = {m for o in bls["occupations"]["list"] for m in o["metros"]}
        codes = [o["code"] for o in bls["occupations"]["list"]]
        oy = str(bls["occupations"].get("year"))
        def do_oews():
            due = sorted({m for r in regions for m in r["msas"] if m not in home_msas and (cache["oews_year"].get(m) != oy or m not in cache["oews"])})
            if not due:
                return
            ids = {"OEUM%07d000000%s01" % (int(m), c): (m, c) for m in due for c in codes}
            print("  oews: %d series for %d metro areas" % (len(ids), len(due)), flush=True)
            got = b.fetch(list(ids))
            new = {}
            for sid, (m, c) in ids.items():
                pts = got.get(sid) or []
                if pts and b.num(pts[0]["value"]) is not None:
                    new.setdefault(m, {})[c] = b.num(pts[0]["value"])
            for m, v in new.items():
                if v.get("000000"):
                    cache["oews"][m] = v; cache["oews_year"][m] = oy
        step("oews", do_oews)
        def do_laus():
            need = [f for f in counties if f not in bls["laus"]["counties"]]
            y = int(bls["laus"]["us_rate"][-1][0][:4])
            ids = {}
            for f in need:
                ids["LAUCN%s0000000003" % f] = (f, "rate"); ids["LAUCN%s0000000006" % f] = (f, "force")
            got = b.fetch(list(ids), y - 1, y)
            for sid, (f, k) in ids.items():
                pts = sorted((p for p in got.get(sid) or [] if p["period"].startswith("M") and p["period"] != "M13" and b.num(p["value"]) is not None),
                             key=lambda p: (p["year"], p["period"]))
                if pts:
                    cache["laus"].setdefault(f, {})[k] = b.num(pts[-1]["value"])
                    cache["laus"][f]["month"] = "%s-%s" % (pts[-1]["year"], pts[-1]["period"][1:])
        step("laus", do_laus)

    # assemble inputs; Michiana's metro occupations and county unemployment from data/bls.json
    oews = {m: dict(v) for m, v in cache["oews"].items()}
    for o in bls["occupations"]["list"]:
        for m, v in o["metros"].items():
            if v.get("emp"):
                oews.setdefault(m, {})[o["code"]] = v["emp"]
    laus = dict(cache["laus"])
    for f, c in bls["laus"]["counties"].items():
        if c.get("rate") and c["rate"][-1][1] is not None:
            laus[f] = {"rate": c["rate"][-1][1], "force": (c.get("force") or [[None, 0]])[-1][1] or 0, "month": c["rate"][-1][0]}
    inp = {"qcew": cache["qcew"], "totals": cache["totals"], "bea": cache["bea"], "qwi": cache["qwi"], "oews": oews, "laus": laus}
    if not cache["qcew"] or cache.get("qcew_year") != Y:
        print("compare_regions: no QCEW county data for %s yet; nothing scored" % Y)
        return
    bench = {"year": Y, "qcew_us": qcew["us"], "us_hm": qcew["highmix_history"][Y]["us_hm"], "us_rate": bls["laus"]["us_rate"][-1][1],
             "qwi_us": qwi_us, "va_year": vy, "us_va": bea_us[vy] / qcew["us"][vy]["emp"],
             "fit": json.load(open(P("data", "task_fit.json")))["occupations"],
             "occ_us": {o["code"]: (o.get("us") or {}).get("emp") for o in bls["occupations"]["list"]}}

    results = {r["name"]: dict(score(r, inp, bench, spec, hum), university=r.get("university", ""), home=bool(r.get("home"))) for r in regions}
    ranking = sorted((n for n in results if results[n]["index"] is not None), key=lambda n: -results[n]["index"])
    month = datetime.date.today().strftime("%Y-%m")
    history = old.get("history") or {}
    history[month] = {n: {"index": v["index"], "pillars": v["pillars"]} for n, v in results.items()}
    out = {"note": "Comparison of the Physical-AI Opportunity Index across data/regions.toml, same method as the map; shown on the Physical AI readiness tab.",
           "updated": datetime.date.today().isoformat(), "log": log,
           "inputs": {"qcew_year": Y, "prosperity_span": [str(int(Y) - 5), Y], "value_added_year": vy, "oews_year": str(bls["occupations"].get("year")),
                      "unemployment_us_month": bls["laus"]["us_rate"][-1][0], "unemployment_county_months": sorted({v.get("month") for v in laus.values() if v.get("month")}),
                      "qwi_age_quarters": qwi_us["age_quarters"], "qwi_turnover_quarters": qwi_us["turnover_quarters"]},
           "ranking": ranking, "regions": results, "history": dict(sorted(history.items())), "cache": cache}
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print("compare_regions: %d regions scored, %d with a full index (%s)" % (len(results), len(ranking), "; ".join(log) or "offline"))
    for i, n in enumerate(ranking, 1):
        v = results[n]
        print("  %2d. %-32s %5.1f  %s" % (i, n, v["index"], "  ".join("%s %s" % (k, "–" if x is None else round(x)) for k, x in v["pillars"].items())))
    for n, v in results.items():
        if v["missing"]:
            print("  %s: no index, missing %s" % (n, ", ".join(v["missing"])))

if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
