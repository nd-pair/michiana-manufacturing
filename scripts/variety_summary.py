#!/usr/bin/env python3
"""Summarize the variety and end-market fields of the company files.

    python3 scripts/variety_summary.py          # writes data/variety.json and prints two counties

Reads the active manufacturers (NAICS 31-33, not removed, closed, presumed closed or unconfirmed) and
the fields described in CURATION.md under "Variety and end markets": `made_to_order`, `job_shop`,
`product_lines`, `end_markets`. Writes data/variety.json with

- coverage: how many active manufacturers (and how many with a website) have each field;
- by county (ZIP code of the address -> county, data/region_zips.json):
  - share of jobs in made-to-order firms: headcount of firms with made_to_order = "yes" over the
    headcount of firms with the field recorded (and the same with "mixed" counted as made to order);
  - share of jobs in job shops (job_shop = true over firms with the field recorded);
  - mean product lines, plain and headcount-weighted;
  - end-market concentration: a Herfindahl index over end markets, each firm's headcount split
    equally across the markets it lists (1 = every job in one market; 1/HHI = the effective
    number of markets), with the top markets' shares;
- counties_site_scope_only: the same, without firms whose fields come from a larger parent's site
  (variety_scope = "company").

Weights are site headcounts (`employees` with employees_scope "site"); company-wide headcounts are
left out of the weighted figures, since they include jobs outside the region. The fields describe the
firms as their websites present them today, so these are descriptions of the current region, not
inputs to a forecast. Coverage is partial (firms with a website, mostly); every figure carries the
number of firms and jobs it rests on.
"""
import collections, datetime, json, re, tomllib
from common import P, COUNTIES, companies

FIELDS = ("made_to_order", "job_shop", "product_lines", "end_markets")

def active(c):
    return str(c.get("naics") or "")[:2] in ("31", "32", "33") and not any(
        k in c for k in ("removed", "closed", "presumed_closed", "unconfirmed"))

def site_jobs(c):
    return (c.get("employees") or 0) if c.get("employees_scope", "site") == "site" else 0

def county(c, zips):
    m = re.search(r"\b(\d{5})(?:-\d{4})?\s*$", c.get("address") or "")
    return zips.get(m[1]) if m else None

def summarize(fs):
    """Figures for one group of firms."""
    out = {"firms": len(fs), "jobs": sum(site_jobs(c) for c in fs)}
    mto = [c for c in fs if c.get("made_to_order") in ("yes", "no", "mixed")]
    jw = sum(site_jobs(c) for c in mto)
    out["made_to_order"] = {
        "firms_recorded": len(mto), "jobs_recorded": jw,
        "firms": dict(collections.Counter(c["made_to_order"] for c in mto)),
        "job_share_yes": round(sum(site_jobs(c) for c in mto if c["made_to_order"] == "yes") / jw, 3) if jw else None,
        "job_share_yes_or_mixed": round(sum(site_jobs(c) for c in mto if c["made_to_order"] != "no") / jw, 3) if jw else None,
    }
    js = [c for c in fs if isinstance(c.get("job_shop"), bool)]
    jw = sum(site_jobs(c) for c in js)
    out["job_shop"] = {"firms_recorded": len(js), "jobs_recorded": jw, "firms_true": sum(c["job_shop"] for c in js),
                       "job_share": round(sum(site_jobs(c) for c in js if c["job_shop"]) / jw, 3) if jw else None}
    pl = [c for c in fs if isinstance(c.get("product_lines"), int)]
    jw = sum(site_jobs(c) for c in pl)
    out["product_lines"] = {
        "firms_recorded": len(pl),
        "mean": round(sum(c["product_lines"] for c in pl) / len(pl), 2) if pl else None,
        "median": sorted(c["product_lines"] for c in pl)[len(pl) // 2] if pl else None,
        "job_weighted_mean": round(sum(c["product_lines"] * site_jobs(c) for c in pl) / jw, 2) if jw else None,
    }
    em = [c for c in fs if c.get("end_markets")]
    jobs = collections.Counter()
    for c in em:
        for m in c["end_markets"]:
            jobs[m] += site_jobs(c) / len(c["end_markets"])
    tot = sum(jobs.values())
    hhi = sum((v / tot) ** 2 for v in jobs.values()) if tot else None
    out["end_markets"] = {
        "firms_recorded": len(em), "jobs_recorded": round(tot),
        "hhi": round(hhi, 3) if hhi else None,
        "effective_markets": round(1 / hhi, 2) if hhi else None,
        "mean_markets_per_firm": round(sum(len(c["end_markets"]) for c in em) / len(em), 2) if em else None,
        "job_shares": {m: round(v / tot, 3) for m, v in jobs.most_common()} if tot else {},
        "firm_counts": dict(collections.Counter(m for c in em for m in c["end_markets"]).most_common()),
    }
    return out

def main():
    zips = json.load(open(P("data", "region_zips.json")))["zips"]
    vocab = {m["name"] for m in tomllib.load(open(P("data", "end_markets.toml"), "rb"))["market"]}
    cs = [c for c in companies() if active(c)]
    bad = [(c["_file"], m) for c in cs for m in c.get("end_markets", []) if m not in vocab]
    if bad:
        raise SystemExit("end market(s) not in data/end_markets.toml: %s" % bad[:10])
    web = [c for c in cs if c.get("website")]
    coverage = {"active_manufacturers": len(cs), "with_website": len(web),
                "checked": sum(1 for c in cs if c.get("variety_checked")),
                "any_field": sum(1 for c in cs if any(f in c for f in FIELDS))}
    for f in FIELDS:
        coverage[f] = {"all": sum(1 for c in cs if f in c), "with_website": sum(1 for c in web if f in c)}
    jobs_all = sum(site_jobs(c) for c in cs)
    coverage["site_jobs"] = {"all": jobs_all, "in_firms_with_any_field": sum(site_jobs(c) for c in cs if any(f in c for f in FIELDS))}
    by = collections.defaultdict(list)
    for c in cs:
        by[county(c, zips) or "unknown"].append(c)
    out = {
        "generated": datetime.date.today().isoformat(),
        "note": "Firm-level variety and end-market fields from each company's own website (CURATION.md, 'Variety and end markets'); "
                "describes firms as they are today. Weights are site headcounts; company-wide headcounts are left out.",
        "coverage": coverage,
        "region": summarize(cs),
        "counties": {k: dict(name=COUNTIES.get(k, k), **summarize(v)) for k, v in sorted(by.items())},
        # the same, leaving out firms whose fields describe a larger parent (variety_scope = "company")
        "counties_site_scope_only": {k: dict(name=COUNTIES.get(k, k), **summarize([c for c in v if c.get("variety_scope") != "company"]))
                                     for k, v in sorted(by.items())},
    }
    with open(P("data", "variety.json"), "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    print("coverage: %d active manufacturers, %d with a website, %d checked; any field: %d" % (
        len(cs), len(web), coverage["checked"], coverage["any_field"]))
    for f in FIELDS:
        print("  %-14s %4d  (%d of them with a website)" % (f, coverage[f]["all"], coverage[f]["with_website"]))
    e, s = out["counties"].get("18039"), out["counties"].get("18141")
    if e and s:
        def row(label, fn):
            print("  %-44s %16s %16s" % (label, fn(e), fn(s)))
        print("\n  %-44s %16s %16s" % ("", "Elkhart 18039", "St. Joseph 18141"))
        row("active manufacturers / site jobs", lambda d: "%d / %d" % (d["firms"], d["jobs"]))
        row("made_to_order recorded (firms / jobs)", lambda d: "%d / %d" % (d["made_to_order"]["firms_recorded"], d["made_to_order"]["jobs_recorded"]))
        row("  job share made to order (yes)", lambda d: d["made_to_order"]["job_share_yes"])
        row("  job share made to order (yes or mixed)", lambda d: d["made_to_order"]["job_share_yes_or_mixed"])
        row("job_shop recorded (firms) / job share", lambda d: "%d / %s" % (d["job_shop"]["firms_recorded"], d["job_shop"]["job_share"]))
        row("product_lines recorded (firms)", lambda d: d["product_lines"]["firms_recorded"])
        row("  mean / job-weighted mean product lines", lambda d: "%s / %s" % (d["product_lines"]["mean"], d["product_lines"]["job_weighted_mean"]))
        row("end_markets recorded (firms / jobs)", lambda d: "%d / %d" % (d["end_markets"]["firms_recorded"], d["end_markets"]["jobs_recorded"]))
        row("  end-market HHI (effective markets)", lambda d: "%s (%s)" % (d["end_markets"]["hhi"], d["end_markets"]["effective_markets"]))
        row("  largest end market (job share)", lambda d: next(("%s %.2f" % kv for kv in d["end_markets"]["job_shares"].items()), "-"))
        e2, s2 = out["counties_site_scope_only"]["18039"], out["counties_site_scope_only"]["18141"]
        print("  %-44s %16s %16s" % ("without parent-level (company-scope) records:", "", ""))
        print("  %-44s %16s %16s" % ("  job share made to order (yes)", e2["made_to_order"]["job_share_yes"], s2["made_to_order"]["job_share_yes"]))
        print("  %-44s %16s %16s" % ("  end-market HHI", e2["end_markets"]["hhi"], s2["end_markets"]["hhi"]))

if __name__ == "__main__":
    main()
