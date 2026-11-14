#!/usr/bin/env python3
"""Layoff and closure notices (WARN) for the region's Indiana counties, from the Indiana Department of
Workforce Development.

    python3 scripts/pull_warn.py        # writes data/warn.json

Employers with 100 or more workers must give 60 days' notice of a plant closing or mass layoff under
the federal WARN Act; Indiana DWD publishes every notice it receives, back to 2008, in one table
(company, city, affected workers, notice date, layoff or closing date, NAICS, notice type). This keeps
the notices since 2016 from cities in the region's Indiana counties, and matches each to a company file
in the same city by normalized name (or its first three words) when exactly one file fits; notices
from outside manufacturing (NAICS 31-33) are left out. A closing notice (type CL) is a dated source for that plant's closure. When its closing date has
passed, the plant was imported (HIFLD or OSHA, not a hand-written file), and the plant has not filed
with OSHA for a later year, the file is marked closed with the notice as its source; listing a plant
that no longer exists is worse than missing one. Closing notices for hand-written files (often a
whole company, such as Forest River) go to the closure review (scripts/check_closed.py) instead.

Michigan publishes its notices only through a search page on michigan.gov, with no table or export,
so Berrien, Cass and Van Buren counties are not covered here.
"""
import datetime, html, json, os, re, sys, tomllib, urllib.request
from common import P, COUNTIES, companies, norm, company_path, set_field

URL = "https://www.in.gov/dwd/warn-notices/current-warn-notices/"
UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
SINCE = "2016-01-01"
TYPES = {"CL": "closing", "LO": "layoff", "RIF": "reduction in force", "RL": "relocation"}

def date(s):
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    return "%s-%02d-%02d" % (m[3], int(m[1]), int(m[2])) if m else ""

def region_cities(cs):
    """Indiana cities in the region: every Indiana city with a company file, and data/places.toml."""
    cities = {c["city"].strip().lower() for c in cs if c.get("state") == "IN" and c.get("city")}
    try:
        places = tomllib.load(open(P("data", "places.toml"), "rb"))
        for k, v in places.items():
            if isinstance(v, dict) and v.get("state", "IN") == "IN":
                cities.add(k.strip().lower())
    except Exception:
        pass
    return cities

def main():
    page = urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=60).read().decode("utf-8", "replace")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) >= 8 and cells[0] != "Company":
            rows.append(cells)
    if len(rows) < 100:
        sys.exit("only %d rows on %s; the page layout may have changed" % (len(rows), URL))
    cs = [c for c in companies() if not c.get("removed")]
    cities = region_cities(cs)
    idx = {}
    for c in cs:
        n, city = norm(c["name"]), (c.get("city") or "").strip().lower()
        for k in {(n, city), (" ".join(n.split()[:3]), city), (" ".join(n.split()[:2]), city)}:
            idx.setdefault(k, set()).add(c["_id"])
    def match(name, city):
        """The one company file in this city with this name; None when there is none or several (a person picks)."""
        n, city = norm(name), city.strip().lower()
        for k in ((n, city), (" ".join(n.split()[:3]), city), (" ".join(n.split()[:2]), city)):
            if k[0] and len(idx.get(k, ())) == 1:
                return next(iter(idx[k]))
            if k[0] and idx.get(k):
                return None
        return None
    notices = []
    for company, city, workers, notice, effective, naics, industry, kind, *_ in rows:
        nd = date(notice)
        if not nd or nd < SINCE or city.strip().lower() not in cities:
            continue
        if not (naics.strip()[:2] in ("31", "32", "33") or "manufactur" in industry.lower()):
            continue
        cid = match(company, city) or match(re.sub(r"(?i)\b(dba|d/b/a)\b.*$", "", company), city)
        if not cid:
            dba = re.search(r"(?i)\b(?:dba|d/b/a)\s+(.+)$", company)
            cid = dba and match(dba[1], city)
        company = re.sub(r"<[^>]*$|/td>$", "", company).strip()
        notices.append({"company": company, "city": city, "workers": int(workers) if workers.isdigit() else None,
                        "notice_date": nd, "effective": date(effective), "naics": naics, "industry": industry,
                        "type": kind, "type_name": TYPES.get(kind, kind), "match": cid or ""})
    notices.sort(key=lambda n: n["notice_date"], reverse=True)
    json.dump({"source": "Indiana Department of Workforce Development, WARN notices (%s)" % URL, "pulled": datetime.date.today().isoformat(),
               "since": SINCE, "covers": "Indiana counties of the region; Michigan notices are not published as a table", "notices": notices},
              open(P("data", "warn.json"), "w"), indent=0)
    # close imported plants whose closing date has passed, unless they filed with OSHA afterwards
    filed = {}
    if os.path.exists(P("data", "osha.json")):
        for y, est in json.load(open(P("data", "osha.json"))).get("years", {}).items():
            for v in est.values():
                if not v.get("occupant"):
                    filed[v["company"]] = max(filed.get(v["company"], ""), y)
    by_id, today, closed_now = {c["_id"]: c for c in cs}, datetime.date.today().isoformat(), []
    for n in notices:
        c = by_id.get(n["match"])
        eff = n["effective"] or n["notice_date"]
        if not c or n["type"] != "CL" or eff > today or c.get("closed") or c.get("presumed_closed"):
            continue
        if not (c.get("source") or "").startswith(("HIFLD", "OSHA")) or filed.get(c["_id"], "") > eff[:4]:
            continue
        path = company_path(c["_id"])
        set_field(path, "closed", eff)
        set_field(path, "closed_note", "%s gave notice on %s that it would close this plant on %s%s (Indiana WARN notice)."
                  % (n["company"], n["notice_date"], eff, ", with %d workers" % n["workers"] if n.get("workers") else ""))
        set_field(path, "closed_source", URL)
        closed_now.append(c["name"])
    if closed_now:
        print("marked closed from WARN closing notices: " + "; ".join(closed_now))
    cl = [n for n in notices if n["type"] == "CL"]
    print("%d manufacturing notices since %s in the region's Indiana cities (%d closings); %d matched to a company file, %d closings matched"
          % (len(notices), SINCE, len(cl), sum(1 for n in notices if n["match"]), sum(1 for n in cl if n["match"])))

if __name__ == "__main__":
    main()
