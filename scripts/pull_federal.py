#!/usr/bin/env python3
"""Federal awards (contracts and grants) to recipients in the Michiana counties, from USAspending.gov.

    python3 scripts/pull_federal.py        # writes data/federal.json

For each recipient located in the region: total obligated amount since FY2016 for contracts and for
grants, matched to our company files by name. Also the regional totals by awarding agency, for the
federal-footprint panel. Public API, no key.
"""
import json, sys, time, urllib.request, datetime
from common import P, COUNTIES, companies, matcher

API = "https://api.usaspending.gov/api/v2/search/spending_by_category/%s/"
TIME = [{"start_date": "2015-10-01", "end_date": datetime.date.today().isoformat()}]
LOCS = [{"country": "USA", "state": "IN" if k.startswith("18") else "MI", "county": k[2:]} for k in COUNTIES]
TYPES = {"contracts": ["A", "B", "C", "D"], "grants": ["02", "03", "04", "05"]}   # procurement contracts and grants; loans, direct payments and insurance are left out

def post(kind, filters, page):
    body = json.dumps({"filters": filters, "limit": 100, "page": page}).encode()
    req = urllib.request.Request(API % kind, data=body, headers={"Content-Type": "application/json", "User-Agent": "michiana-manufacturing/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(3)

def all_pages(kind, filters):
    out, page = [], 1
    while True:
        d = post(kind, filters, page)
        out += d.get("results", [])
        if not d.get("page_metadata", {}).get("hasNext"):
            return out
        page += 1
        if page > 40:
            return out

def main():
    cs = companies(); match = matcher(cs)
    by_company, agencies = {}, {}
    for label, codes in TYPES.items():
        filters = {"time_period": TIME, "award_type_codes": codes, "recipient_locations": LOCS}
        recips = all_pages("recipient", filters)
        print("%s: %d recipients" % (label, len(recips)))
        for r in recips:
            cid = match(r["name"])
            if not cid:
                continue
            e = by_company.setdefault(cid, {"contracts": 0, "grants": 0, "recipient_names": []})
            e[label] += r.get("amount") or 0
            if r["name"] not in e["recipient_names"]:
                e["recipient_names"].append(r["name"])
        for a in all_pages("awarding_agency", filters):
            agencies.setdefault(a["name"], {"contracts": 0, "grants": 0})[label] += a.get("amount") or 0
    for e in by_company.values():
        e["total"] = round(e["contracts"] + e["grants"])
        for k in ("contracts", "grants"):
            e[k] = round(e[k])
    top = sorted(agencies.items(), key=lambda kv: -(kv[1]["contracts"] + kv[1]["grants"]))[:12]
    data = {"source": "USAspending.gov: procurement contracts and grants by recipient and awarding agency, FY2016 to date, recipients located in the Michiana counties",
            "pulled": datetime.date.today().isoformat(), "companies": by_company,
            "agencies": [{"name": n, **{k: round(v) for k, v in d.items()}} for n, d in top]}
    json.dump(data, open(P("data", "federal.json"), "w"), indent=0)
    print("matched %d companies; top agencies: %s" % (len(by_company), ", ".join(a["name"] for a in data["agencies"][:5])))

if __name__ == "__main__":
    main()
