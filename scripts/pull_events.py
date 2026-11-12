#!/usr/bin/env python3
"""Build the timeline from public event streams, for companies in the map.

    python3 scripts/pull_events.py          # writes data/events_auto.json

Sources, each optional:
- SBIR/STTR awards, from SBIR.gov's public bulk file: one event per award to a company in the map
  (phase, agency, title, amount, year).
- Federal contracts and grants of $250,000 or more, from USAspending.gov, for recipients in the
  Michiana counties that match a company in the map (start date, agency, description, amount).
- Indiana WARN notices (plant closings and mass layoffs) from the Department of Workforce
  Development's notice pages, matched to companies by name.
Hand-written events stay in data/events.toml; the build merges both.
"""
import csv, datetime, html, io, json, re, sys, time, urllib.request
from common import P, COUNTIES, companies, matcher
sys.path.insert(0, P("scripts"))
import pull_sbir

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
USA = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
WARN_PAGES = ["https://www.in.gov/dwd/warn-notices/current-warn-notices/"]

def sbir_events(cs, match, by_domain):
    out = []
    for row in pull_sbir.rows_from(None):
        allowed = pull_sbir.CITY_SETS.get((row.get("State") or "").strip())
        if not allowed or (row.get("City") or "").strip().lower() not in allowed:
            continue
        cid = by_domain.get(pull_sbir.domain(row.get("Company Website"))) or match(row.get("Company") or "", row.get("City") or "")
        if not cid:
            continue
        try:
            amt = float(row.get("Award Amount") or 0)
        except ValueError:
            amt = 0
        date = (row.get("Proposal Award Date") or "")[:10] or (row.get("Award Year") or "")
        out.append({"date": date, "company": cid, "kind": "sbir", "amount": round(amt),
                    "title": "%s %s from %s: %s" % (row.get("Program") or "SBIR", row.get("Phase") or "", (row.get("Agency") or "").replace("Department of War", "Department of Defense"), (row.get("Award Title") or "").strip()),
                    "source": "https://www.sbir.gov/awards"})
    return out

def federal_events(cs, match):
    out = []
    locs = [{"country": "USA", "state": "IN" if k.startswith("18") else "MI", "county": k[2:]} for k in COUNTIES]
    for label, codes in (("contract", ["A", "B", "C", "D"]), ("grant", ["02", "03", "04", "05"])):
        page = 1
        while True:
            body = {"filters": {"time_period": [{"start_date": "2015-10-01", "end_date": datetime.date.today().isoformat()}], "award_type_codes": codes,
                                "recipient_locations": locs, "award_amounts": [{"lower_bound": 250000}]},
                    "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "Awarding Agency", "Awarding Sub Agency", "Description"], "limit": 100, "page": page,
                    "sort": "Award Amount", "order": "desc"}
            req = urllib.request.Request(USA, data=json.dumps(body).encode(), headers={**UA, "Content-Type": "application/json"})
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(req, timeout=120) as r:
                        d = json.load(r)
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(3)
            for a in d.get("results", []):
                cid = match(a.get("Recipient Name") or "")
                if not cid or not a.get("Start Date"):
                    continue
                desc = (a.get("Description") or "").strip().capitalize()
                out.append({"date": a["Start Date"][:10], "company": cid, "kind": "federal", "amount": round(a.get("Award Amount") or 0),
                            "title": "%s from %s%s: %s" % ("Federal contract" if label == "contract" else "Federal grant", a.get("Awarding Agency") or "",
                                                           (" (%s)" % a["Awarding Sub Agency"]) if a.get("Awarding Sub Agency") else "", desc[:160] or a.get("Award ID", "")),
                            "source": "https://www.usaspending.gov/award/%s" % a.get("generated_internal_id", "")})
            if not d.get("page_metadata", {}).get("hasNext") or page >= 60:
                break
            page += 1
    return out

def warn_events(cs, match):
    out = []
    for url in WARN_PAGES:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                text = r.read().decode("utf-8", "replace")
        except Exception as e:
            print("WARN page skipped:", url, e); continue
        headers = [html.unescape(re.sub(r"<[^>]+>", " ", h)).strip().lower() for h in re.findall(r"<th[^>]*>(.*?)</th>", text, flags=re.S)]
        col = lambda name: next((i for i, h in enumerate(headers) if name in h), None)
        iname, icity, inum, idate, itype = col("company"), col("city"), col("affected"), col("notice date"), col("notice type")
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S):
            cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
            if len(cells) < 4:
                continue
            get = lambda i, d="": cells[i] if i is not None and i < len(cells) else d
            name, city, num, date, ntype = get(iname, cells[0]), get(icity), get(inum), get(idate), get(itype)
            cid = match(name, city)
            if not cid:
                continue
            m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", date)
            if not m:
                continue
            iso = "%s-%02d-%02d" % (m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3), int(m.group(1)), int(m.group(2)))
            what = {"CL": "plant closing", "LO": "layoff"}.get(ntype.strip().upper(), "notice")
            out.append({"date": iso, "company": cid, "kind": "warn", "amount": int(num) if num.isdigit() else None,
                        "title": "WARN %s at %s, %s%s" % (what, name, city, (": %s workers affected" % num) if num.isdigit() else ""), "source": url})
    return out

def main():
    cs = companies(); match = matcher(cs); by_domain = {pull_sbir.domain(c["website"]): c["_id"] for c in cs if c.get("website")}
    events = []
    for fn, args in ((sbir_events, (cs, match, by_domain)), (federal_events, (cs, match)), (warn_events, (cs, match))):
        try:
            got = fn(*args); print("%s: %d events" % (fn.__name__, len(got))); events += got
        except Exception as e:
            print("%s failed: %s" % (fn.__name__, e))
    seen, uniq = set(), []
    for e in events:
        k = (e["date"], e["company"], e["title"][:80])
        if k not in seen:
            seen.add(k); uniq.append(e)
    uniq.sort(key=lambda e: e["date"], reverse=True)
    json.dump({"pulled": datetime.date.today().isoformat(), "events": uniq}, open(P("data", "events_auto.json"), "w"), indent=0)
    print("wrote %d events" % len(uniq))

if __name__ == "__main__":
    main()
