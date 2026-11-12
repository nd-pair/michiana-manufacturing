#!/usr/bin/env python3
"""U.S. patents assigned to companies on the map, from the USPTO's PatentsView PatentSearch API.

    PATENTSVIEW_API_KEY=... python3 scripts/pull_patents.py      # writes data/patents.json

The API needs a free key: request one at https://patentsview.org/apis/keyrequest and store it as
the repository secret PATENTSVIEW_API_KEY; the monthly refresh passes it in. Without a key the
script does nothing and the site simply shows no patent figures.

Patents granted since 2015 whose assignee is located in a Michiana city are matched to company
files by exact name, then by name and city. Each matched patent also becomes a timeline event.
"""
import datetime, json, os, sys, time, urllib.request
from common import P, companies, matcher, norm, exact_name_index
from pull_sbir import IN_CITIES, MI_CITIES

API = "https://search.patentsview.org/api/v1/patent/"
SINCE = "2015-01-01"

def search(key, state, cities):
    q = {"_and": [{"_gte": {"patent_date": SINCE}}, {"assignees.assignee_state": state},
                  {"_or": [{"assignees.assignee_city": c.title()} for c in sorted(cities)]}]}
    fields = ["patent_id", "patent_title", "patent_date", "assignees.assignee_organization", "assignees.assignee_city", "assignees.assignee_state"]
    out, after = [], None
    while True:
        body = {"q": q, "f": fields, "s": [{"patent_id": "asc"}], "o": {"size": 1000}}
        if after:
            body["o"]["after"] = after
        req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"X-Api-Key": key, "Content-Type": "application/json",
                                                                                     "User-Agent": "michiana-manufacturing/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
        rows = d.get("patents") or []
        out += rows
        if len(rows) < 1000:
            return out
        after = rows[-1]["patent_id"]
        time.sleep(1.5)        # the API allows 45 requests a minute

def main():
    key = os.environ.get("PATENTSVIEW_API_KEY", "").strip()
    if not key:
        print("PATENTSVIEW_API_KEY is not set; skipping patents (see the docstring for how to get a key)")
        return
    cs = companies(); match = matcher(cs); by_name = exact_name_index(cs)
    patents = search(key, "IN", IN_CITIES) + search(key, "MI", MI_CITIES)
    by_company, events = {}, []
    for p in patents:
        for a in p.get("assignees") or []:
            org = a.get("assignee_organization") or ""
            city = a.get("assignee_city") or ""
            if city.lower() not in IN_CITIES | MI_CITIES:
                continue
            cid = by_name.get(norm(org)) or match(org, city)
            if not cid:
                continue
            e = by_company.setdefault(cid, {"count": 0, "latest": []})
            e["count"] += 1
            e["latest"].append({"id": p["patent_id"], "title": p.get("patent_title", ""), "date": p.get("patent_date", "")})
            events.append({"date": p.get("patent_date", ""), "company": cid, "kind": "patent", "amount": None,
                           "title": "U.S. patent %s: %s" % (p["patent_id"], (p.get("patent_title") or "").strip()),
                           "source": "https://patents.google.com/patent/US%s" % p["patent_id"]})
            break
    for e in by_company.values():
        e["latest"] = sorted(e["latest"], key=lambda x: x["date"], reverse=True)[:5]
    json.dump({"source": "USPTO PatentsView PatentSearch API, patents granted since %s" % SINCE, "pulled": datetime.date.today().isoformat(),
               "companies": by_company, "events": sorted(events, key=lambda e: e["date"], reverse=True)},
              open(P("data", "patents.json"), "w"), indent=0)
    print("%d patents with a Michiana assignee; matched %d companies" % (len(patents), len(by_company)))

if __name__ == "__main__":
    main()
