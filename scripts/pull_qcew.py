#!/usr/bin/env python3
"""Manufacturing employment and wages from the BLS Quarterly Census of Employment and Wages.

    python3 scripts/pull_qcew.py        # writes data/qcew.json

Two views, both private ownership, annual averages:
- by county: NAICS 31-33 total for each Michiana county, from the industry slice 1013;
- by sector: each county's 3-digit NAICS rows from the area slices, folded into the map's
  sectors (same NAICS mapping as the HIFLD import) and summed over the region. BLS withholds
  cells that would disclose a single employer; those count as zero, so the sector sums are a
  lower bound and the note on the chart says so.
- specialization, for the latest year: every 3-digit manufacturing industry's jobs, establishments
  and pay summed over the region, its location quotient (the region's share of private jobs in the
  industry divided by the U.S. share; above 1 means the region is specialized in it), and the county
  where it is most concentrated by BLS's own county quotient.
"""
import csv, io, json, urllib.request, datetime, tomllib
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
    us_years = {}
    for y in years:
        try:
            text = get("https://data.bls.gov/cew/data/api/%d/a/industry/1013.csv" % y)
        except Exception as e:
            print(y, "county totals skipped:", e); continue
        for row in csv.DictReader(io.StringIO(text)):
            if row.get("own_code") == "5" and row.get("area_fips") in counties:
                counties[row["area_fips"]][y] = {"estab": int(row["annual_avg_estabs"] or 0), "emp": int(row["annual_avg_emplvl"] or 0), "pay": int(row["avg_annual_pay"] or 0)}
            elif row.get("own_code") == "5" and row.get("area_fips") == "US000":
                us_years[str(y)] = {"estab": int(row["annual_avg_estabs"] or 0), "emp": int(row["annual_avg_emplvl"] or 0), "pay": int(row["avg_annual_pay"] or 0)}
    sectors, withheld = {}, {}
    def area(job):
        y, fips = job
        try:
            return y, fips, get("https://data.bls.gov/cew/data/api/%d/a/area/%s.csv" % (y, fips))
        except Exception as e:
            return y, fips, None
    jobs = [(y, f) for y in years for f in COUNTIES]
    texts = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for y, fips, text in ex.map(area, jobs):
            if not text:
                print(y, fips, "area slice skipped"); continue
            texts[(y, fips)] = text
            for row in csv.DictReader(io.StringIO(text)):
                code = row.get("industry_code", "")
                if row.get("own_code") != "5" or len(code) != 3 or code not in SECTOR_BY_NAICS3:
                    continue
                sec = SECTOR_BY_NAICS3[code]
                emp = int(row.get("annual_avg_emplvl") or 0)
                if row.get("disclosure_code") == "N":
                    withheld.setdefault(str(y), 0); withheld[str(y)] += 1
                sectors.setdefault(sec, {}); sectors[sec][y] = sectors[sec].get(y, 0) + emp
    spec = specialization(texts, years)
    data = {"source": "BLS QCEW, private, annual averages", "pulled": datetime.date.today().isoformat(), "specialization": spec,
            "counties": {k: {"name": COUNTIES[k], "years": counties[k]} for k in COUNTIES}, "us": us_years,
            "sectors": {s: {str(y): v for y, v in sorted(d.items())} for s, d in sectors.items()},
            "withheld_cells": withheld}
    json.dump(data, open(P("data", "qcew.json"), "w"), indent=0)
    print("counties: %d with data; sectors: %s" % (sum(1 for k in counties if counties[k]), ", ".join("%s %d" % (s, d[max(d)]) for s, d in sorted(sectors.items()))))

NAICS3 = {"311": "Food", "312": "Beverages and tobacco", "313": "Textile mills", "314": "Textile products", "315": "Apparel", "316": "Leather",
          "321": "Wood products", "322": "Paper", "323": "Printing", "324": "Petroleum and coal products", "325": "Chemicals",
          "326": "Plastics and rubber", "327": "Glass, concrete and other mineral products", "331": "Primary metals",
          "332": "Fabricated metal products", "333": "Machinery", "334": "Computers and electronics", "335": "Electrical equipment and appliances",
          "336": "Transportation equipment (incl. RVs)", "337": "Furniture", "339": "Miscellaneous (incl. medical devices)"}

def specialization(texts, years):
    """Latest year with every county's area slice: region totals per 3-digit manufacturing industry and the U.S. comparison."""
    year = next((y for y in sorted(years, reverse=True) if all((y, f) in texts for f in COUNTIES)), None)
    if year is None:
        return {}
    try:
        us = list(csv.DictReader(io.StringIO(get("https://data.bls.gov/cew/data/api/%d/a/area/US000.csv" % year))))
    except Exception as e:
        print("US slice skipped:", e); return {}
    num = lambda r, k: float(r.get(k) or 0)
    def rows(rs):
        return {r["industry_code"]: r for r in rs if r.get("own_code") == "5" and r.get("industry_code") in NAICS3}
    us_tot = next(r for r in us if r.get("own_code") == "5" and r.get("industry_code") == "10")
    us_rows, us_mfg = rows(us), next(r for r in us if r.get("own_code") == "5" and r.get("industry_code") == "31-33")
    reg = {k: {"emp": 0, "estab": 0, "wages": 0.0, "withheld": False, "top": None} for k in NAICS3}
    reg_tot = reg_mfg_emp = reg_mfg_wages = reg_mfg_estab = 0
    hm = tuple(tomllib.load(open(P("data", "opportunity.toml"), "rb"))["highmix"]["naics"])
    six = lambda r: r.get("own_code") == "5" and len(r.get("industry_code", "")) == 6 and r["industry_code"].isdigit() and r["industry_code"][:2] in ("31", "32", "33")
    reg_hm = 0.0
    for f in COUNTIES:
        rs = list(csv.DictReader(io.StringIO(texts[(year, f)])))
        for r in rs:
            if r.get("own_code") != "5":
                continue
            if r["industry_code"] == "10":
                reg_tot += num(r, "annual_avg_emplvl")
            elif r["industry_code"] == "31-33":
                reg_mfg_emp += num(r, "annual_avg_emplvl"); reg_mfg_wages += num(r, "total_annual_wages"); reg_mfg_estab += num(r, "annual_avg_estabs")
            if six(r) and r["industry_code"].startswith(hm):
                reg_hm += num(r, "annual_avg_emplvl")
        for k, r in rows(rs).items():
            e = reg[k]
            e["emp"] += num(r, "annual_avg_emplvl"); e["estab"] += num(r, "annual_avg_estabs"); e["wages"] += num(r, "total_annual_wages")
            if r.get("disclosure_code") == "N":
                e["withheld"] = True
            lq = num(r, "lq_annual_avg_emplvl")
            if lq and (not e["top"] or lq > e["top"][1]):
                e["top"] = (COUNTIES[f], round(lq, 1))
    out = []
    for k, e in reg.items():
        u = us_rows.get(k)
        if not u or not e["estab"]:
            continue
        share, us_share = e["emp"] / reg_tot, num(u, "annual_avg_emplvl") / num(us_tot, "annual_avg_emplvl")
        out.append({"naics": k, "name": NAICS3[k], "emp": round(e["emp"]), "estab": round(e["estab"]),
                    "pay": round(e["wages"] / e["emp"]) if e["emp"] else None, "us_pay": round(num(u, "avg_annual_pay")),
                    "lq": round(share / us_share, 2) if us_share else None, "withheld": e["withheld"],
                    "top_county": e["top"][0] if e["top"] else "", "top_lq": e["top"][1] if e["top"] else None})
    us_hm = sum(num(r, "annual_avg_emplvl") for r in us if six(r) and r["industry_code"].startswith(hm))
    mfg_lq = (reg_mfg_emp / reg_tot) / (num(us_mfg, "annual_avg_emplvl") / num(us_tot, "annual_avg_emplvl"))
    return {"year": year, "industries": sorted(out, key=lambda r: -(r["lq"] or 0)),
            "total": {"emp": round(reg_mfg_emp), "share": round(reg_mfg_emp / reg_tot, 3), "lq": round(mfg_lq, 2),
                      "pay": round(reg_mfg_wages / reg_mfg_emp), "us_pay": round(num(us_mfg, "avg_annual_pay")),
                      "us_share": round(num(us_mfg, "annual_avg_emplvl") / num(us_tot, "annual_avg_emplvl"), 3),
                      "estab": round(reg_mfg_estab), "us_emp": round(num(us_mfg, "annual_avg_emplvl")), "us_estab": round(num(us_mfg, "annual_avg_estabs")),
                      "highmix_share": round(reg_hm / reg_mfg_emp, 3), "us_highmix_share": round(us_hm / num(us_mfg, "annual_avg_emplvl"), 3)}}

if __name__ == "__main__":
    main()
