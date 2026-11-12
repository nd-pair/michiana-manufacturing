#!/usr/bin/env python3
"""FDA medical-device establishment registrations in the Michiana cities, from openFDA.

    python3 scripts/pull_fda.py        # writes data/fda.json
"""
import json, time, urllib.parse, urllib.request, datetime
from common import P, companies, matcher

API = "https://api.fda.gov/device/registrationlisting.json"
QUERIES = [("IN", c) for c in ["WARSAW", "SOUTH BEND", "MISHAWAKA", "ELKHART", "GOSHEN", "PLYMOUTH", "WINONA LAKE", "SYRACUSE", "BREMEN", "LA PORTE",
                              "MICHIGAN CITY", "GRANGER", "NAPPANEE", "MIDDLEBURY", "BRISTOL", "COLUMBIA CITY", "KENDALLVILLE", "LIGONIER", "ROCHESTER", "KNOX"]] + \
          [("MI", c) for c in ["NILES", "BENTON HARBOR", "ST. JOSEPH", "SAINT JOSEPH", "STEVENSVILLE", "DOWAGIAC", "CASSOPOLIS", "SOUTH HAVEN", "PAW PAW"]]

def fetch(state, city):
    out, skip = [], 0
    while True:
        q = urllib.parse.urlencode({"search": 'registration.state_code:"%s" AND registration.city:"%s"' % (state, city), "limit": 100, "skip": skip})
        req = urllib.request.Request(API + "?" + q, headers={"User-Agent": "michiana-manufacturing/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return out
            raise
        out += d.get("results", [])
        if len(d.get("results", [])) < 100:
            return out
        skip += 100; time.sleep(0.3)

def main():
    cs = companies(); match = matcher(cs)
    by_company, establishments = {}, []
    for state, city in QUERIES:
        for r in fetch(state, city):
            reg = r.get("registration", {}); name = reg.get("name") or ""
            kinds = sorted({x.get("code", "") for x in r.get("proprietary_name", []) if False} | {ptype for ptype in [] })
            roles = sorted({o.get("operation_code", "").title() for o in reg.get("owner_operator", {}).get("official_correspondent", []) if False})
            ops = sorted({x for e in r.get("establishment_type", []) for x in ([e] if isinstance(e, str) else [])})
            products = sorted({p.get("openfda", {}).get("device_name", "") for p in r.get("products", []) if p.get("openfda", {}).get("device_name")})[:6]
            establishments.append({"name": name, "city": city.title(), "state": state, "fei": reg.get("fei_number"), "types": ops, "products": products})
            cid = match(name, city)
            if cid:
                by_company[cid] = {"fei": reg.get("fei_number"), "establishment_types": ops, "device_names": products}
        time.sleep(0.3)
    data = {"source": "openFDA device registration and listing", "pulled": datetime.date.today().isoformat(), "companies": by_company,
            "establishments_not_in_map": [e for e in establishments if not match(e["name"], e["city"])][:200]}
    json.dump(data, open(P("data", "fda.json"), "w"), indent=0)
    print("%d registered establishments in the region; matched %d companies" % (len(establishments), len(by_company)))

if __name__ == "__main__":
    main()
