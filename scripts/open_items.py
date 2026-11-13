"""Open items: facts on the map that are missing or doubtful, each with a time to live.

Each news review (scripts/review_llm.py) refreshes the list in data/open_items.json from checks in
code, tries to fix every open item once, and counts the attempt. An item that is still open after
`ttl` attempts (data/news_sources.toml, default 3, so about three months) loses the doubtful fact:

- address: missing or without a street number: the review searches the trusted sources for the
  street address; on expiry a vague address is removed and the company stays at its city's center
  (location_precision = "city"), and a company with no address simply stays there. A full address
  that could not be geocoded is retried with the geocoders; on expiry it is kept, unplaced.
- website: the domain no longer exists or is parked (the website scan, scripts/check_closed.py).
  Each review's scan is the attempt; on expiry the link is removed, since a dead link is worse than none.
- status: a status note marked unconfirmed, disputed or conflicting. The review searches the trusted
  sources for confirmation; on expiry the note is removed.

An item disappears from the list as soon as the check no longer finds the problem (the fact was
fixed by the review, by hand or by an import). Companies are never removed automatically.
"""
import csv, datetime, json, os, re
from common import P, companies

DOUBT = re.compile(r"unconfirm|not confirmed|was not confirmed|disputed|uncertain|reports differ|differ on", re.I)

def detect(scan_csv=None):
    """Current problems, keyed "file:field"."""
    found = {}
    cs = [c for c in companies() if not c.get("closed") and not c.get("removed")]
    for c in cs:
        f = c["_file"]
        if c.get("kind", "company") == "company":
            a = (c.get("address") or "").strip()
            if not a:
                found[f + ":address"] = {"file": f, "company": c["name"], "field": "address", "problem": "no street address"}
            elif not re.match(r"^\s*\d", a):
                found[f + ":address"] = {"file": f, "company": c["name"], "field": "address", "problem": "address without a street number", "value": a}
            elif c.get("location_precision") == "city":
                found[f + ":address"] = {"file": f, "company": c["name"], "field": "address", "problem": "address could not be geocoded", "value": a}
        if DOUBT.search(c.get("status_note", "")):
            found[f + ":status"] = {"file": f, "company": c["name"], "field": "status", "problem": "status not confirmed", "value": c["status_note"]}
    if scan_csv and os.path.exists(scan_csv):
        by_file = {c["_file"]: c for c in cs}
        for r in csv.DictReader(open(scan_csv)):
            f = r["file"].split("/")[-1]
            if r["strength"] == "strong" and f in by_file and by_file[f].get("website"):
                found[f + ":website"] = {"file": f, "company": by_file[f]["name"], "field": "website", "problem": r["reason"], "value": by_file[f]["website"]}
    return found

def load():
    try:
        return json.load(open(P("data", "open_items.json")))
    except (FileNotFoundError, ValueError):
        return {"items": {}, "expired": {}, "log": []}

def save(reg):
    reg["items"] = dict(sorted(reg["items"].items()))
    reg["log"] = reg["log"][-500:]
    json.dump(reg, open(P("data", "open_items.json"), "w"), indent=1, ensure_ascii=False)

def refresh(reg, current, today, scan_ran):
    """Add new problems, close the ones that are gone. Website items close only when a scan ran. A
    problem whose fact already expired is not reopened (the company stays as it is) until it goes away."""
    expired = reg.setdefault("expired", {})
    for k in list(expired):
        if k not in current:
            del expired[k]
    for k, v in current.items():
        if k in expired:
            continue
        if k not in reg["items"]:
            reg["items"][k] = dict(v, opened=today, attempts=0, last_attempt="")
        else:
            reg["items"][k].update({x: v[x] for x in ("company", "problem", "value") if x in v})
    for k in list(reg["items"]):
        it = reg["items"][k]
        if k not in current and (it["field"] != "website" or scan_ran):
            reg["log"].append({"date": today, "file": it["file"], "field": it["field"], "result": "resolved", "attempts": it["attempts"]})
            del reg["items"][k]

def attempted(reg, key, today):
    it = reg["items"].get(key)
    if it and it.get("last_attempt") != today:
        it["attempts"] += 1; it["last_attempt"] = today

def drop_line(path, key):
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"(?m)^%s = .*\n" % re.escape(key), "", text)
    open(path, "w", encoding="utf-8").write(text)

def expire(reg, ttl, today, dry=False):
    """Remove the doubtful fact of every item that has used up its attempts; returns what was removed."""
    from common import set_field
    removed = []
    for k in list(reg["items"]):
        it = reg["items"][k]
        if it["attempts"] < ttl:
            continue
        path = P("companies", it["file"])
        action = "kept at its city's center"
        if os.path.exists(path) and not dry:
            text = open(path, encoding="utf-8").read()
            if it["field"] == "website" and re.search(r"(?m)^website = ", text):
                drop_line(path, "website"); action = "website link removed"
            elif it["field"] == "status" and re.search(r"(?m)^status_note = ", text):
                drop_line(path, "status_note"); action = "unconfirmed status note removed"
            elif it["field"] == "address" and it["problem"] == "address could not be geocoded":
                action = "address kept; it could not be placed, so the company stays at its city's center"
            elif it["field"] == "address" and it.get("value") and re.search(r"(?m)^address = ", text):
                drop_line(path, "address"); set_field(path, "location_precision", "city"); action = "vague address removed; placed at the city center"
            set_field(path, "updated", today)
        removed.append({"date": today, "file": it["file"], "company": it["company"], "field": it["field"], "result": "expired", "action": action,
                        "problem": it["problem"], "attempts": it["attempts"]})
        reg["log"].append(removed[-1])
        reg.setdefault("expired", {})[k] = today
        del reg["items"][k]
    return removed

def to_attempt(reg, field, n):
    """Open items of one field that the review should try this run: fewest attempts first, then oldest."""
    items = [(k, v) for k, v in reg["items"].items() if v["field"] == field]
    items.sort(key=lambda kv: (kv[1]["attempts"], kv[1]["opened"], kv[0]))
    return items[:n]
