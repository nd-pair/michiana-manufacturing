#!/usr/bin/env python3
"""Monthly automated news review with Claude, limited to trusted sources and a dollar budget.

    ANTHROPIC_API_KEY=... python3 scripts/review_llm.py           # search, check, apply, log
    python3 scripts/review_llm.py --dry-run                       # show the plan, no API calls
    LLM_BUDGET_USD=20 (default) caps one run; LLM_MODEL overrides claude-opus-5-5

What it does:
1. News: three searches of last month's news (closures and layoffs; new plants, expansions,
   acquisitions and renames; robotics and physical AI), with Claude's web search and page reading
   restricted to the domains in data/news_sources.toml.
2. Closure checks: up to CLOSURE_CHECKS companies from the website scan's strong candidates
   (data/.closure-review.csv, written by scripts/check_closed.py), taken in rotation so the list is
   worked through over the months, each searched in the same trusted sources.
3. Every finding is checked in code before it changes anything: its source must be on a trusted
   domain and must be a page Claude actually retrieved in this run; it must be marked high
   confidence; the company must match exactly one file (or, for a new company, a known city, a
   valid sector and no existing file). Only these fields can change: closed, closed_note,
   closed_source, name, formerly, status_note, address, website, humanoid, humanoid_evidence,
   humanoid_note; new company files and milestones can be added. Files are never deleted.
4. Applied changes are logged with their sources in data/news_review.json, so each can be
   reviewed or reverted; the run's cost is logged too.

Rules for what may be recorded: CURATION.md (sent to Claude as its instructions).
"""
import csv, datetime, json, os, re, sys, tomllib, urllib.parse
from common import P, COUNTIES, companies, norm, set_field

MODEL = os.environ.get("LLM_MODEL", "claude-opus-5-5")
BUDGET = float(os.environ.get("LLM_BUDGET_USD", "20"))
CLOSURE_CHECKS = int(os.environ.get("LLM_CLOSURE_CHECKS", "15"))
# Prices per million tokens and per search, set conservatively: a declined request may be re-run on a
# fallback model, so tokens are priced at the higher of Claude Opus 5.5 ($4/$20) and Claude Opus 4.8
# ($5/$25). Cache writes at 1.25x input, cache reads at 0.05x.
PRICE = {"in": 5.0, "out": 25.0, "cache_write": 6.25, "cache_read": 0.25, "search": 0.01}
# Worst-case cost of one task, checked before it starts so a run never passes the budget.
EST = {"news": 2.50, "closure": 0.80}
MAX_CONTINUATIONS = 5

TYPES = ["closure", "rename", "move", "new_company", "milestone", "humanoid_capability", "none"]
STATES = {"IN": "IN", "MI": "MI"}

def load_context():
    trusted = tomllib.load(open(P("data", "news_sources.toml"), "rb"))["domains"]
    sectors = [s["name"] for s in tomllib.load(open(P("data", "sectors.toml"), "rb"))["sector"]]
    comps = [c["id"] for c in tomllib.load(open(P("data", "humanoid.toml"), "rb"))["component"]]
    places = tomllib.load(open(P("data", "places.toml"), "rb"))
    cities = {c["name"] for c in places.get("city", [])}
    rules = open(P("CURATION.md"), encoding="utf-8").read()
    return trusted, sectors, comps, cities, rules

def schema(sectors, comps):
    s = lambda **kw: dict(type="string", **kw)
    item = {"type": "object", "additionalProperties": False,
            "required": ["type", "company_name", "city", "state", "date", "source_url", "source_title", "summary",
                         "new_name", "new_address", "website", "products", "sector", "components", "confidence"],
            "properties": {
                "type": s(enum=TYPES), "company_name": s(), "city": s(), "state": s(enum=["IN", "MI", ""]),
                "date": s(description="YYYY-MM-DD, YYYY-MM or YYYY of the event, not of the article"),
                "source_url": s(description="the article this finding rests on, exactly as retrieved"),
                "source_title": s(), "summary": s(description="one factual sentence"),
                "new_name": s(description="renames: the current name"), "new_address": s(description="moves and new companies: street address"),
                "website": s(), "products": {"type": "array", "items": s()}, "sector": s(enum=sectors + [""]),
                "components": {"type": "array", "items": s(enum=comps)}, "confidence": s(enum=["high", "medium", "low"])}}
    return {"type": "object", "additionalProperties": False, "required": ["findings"],
            "properties": {"findings": {"type": "array", "items": item}}}

class Ledger:
    def __init__(self, budget):
        self.budget, self.spent, self.calls, self.searches = budget, 0.0, 0, 0
    def add(self, usage):
        u = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage or {})
        searches = ((u.get("server_tool_use") or {}).get("web_search_requests") or 0)
        cost = ((u.get("input_tokens") or 0) * PRICE["in"] + (u.get("output_tokens") or 0) * PRICE["out"]
                + (u.get("cache_creation_input_tokens") or 0) * PRICE["cache_write"]
                + (u.get("cache_read_input_tokens") or 0) * PRICE["cache_read"]) / 1e6 + searches * PRICE["search"]
        self.spent += cost; self.calls += 1; self.searches += searches
        return cost
    def can(self, task):
        return self.spent + EST[task] <= self.budget

def domain_ok(url, trusted):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in trusted)

def canon(url):
    p = urllib.parse.urlparse(url.strip())
    return (p.hostname or "").lower().removeprefix("www.") + p.path.rstrip("/")

def retrieved_urls(content):
    """Every URL that came back from web search or web fetch in these response blocks."""
    out = set()
    def walk(x, inside):
        if isinstance(x, dict):
            t = x.get("type", "")
            here = inside or t in ("web_search_tool_result", "web_fetch_tool_result", "web_search_result", "web_fetch_result")
            if here and isinstance(x.get("url"), str):
                out.add(canon(x["url"]))
            for v in x.values():
                walk(v, here)
        elif isinstance(x, list):
            for v in x:
                walk(v, inside)
    for b in content:
        walk(b.model_dump() if hasattr(b, "model_dump") else b, False)
    return out

def ask(client, ledger, system, prompt, fmt, trusted, searches, fetches):
    """One task: a request with the trusted-only web tools, resumed after pause_turn; returns (findings, retrieved urls)."""
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": searches, "allowed_domains": trusted},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": fetches, "allowed_domains": trusted}]
    messages = [{"role": "user", "content": prompt}]
    seen, resp = set(), None
    for _ in range(MAX_CONTINUATIONS + 1):
        kw = dict(model=MODEL, max_tokens=16000, system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                  messages=messages, tools=tools, output_config={"effort": "medium", "format": {"type": "json_schema", "schema": fmt}})
        try:
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
        except TypeError:   # an SDK release without the fallbacks parameter
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"}, **kw)
        ledger.add(resp.usage)
        seen |= retrieved_urls(resp.content)
        if resp.stop_reason != "pause_turn":
            break
        messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": resp.content}]
    if resp is None or resp.stop_reason in ("refusal", "max_tokens") or resp.stop_reason == "pause_turn":
        print("  task ended with stop_reason=%s; nothing used" % (resp and resp.stop_reason)); return [], seen
    texts = [b.text for b in resp.content if getattr(b, "type", "") == "text" and b.text.strip()]
    text = texts[-1].strip() if texts else ""     # the JSON answer comes after any search commentary
    try:
        return json.loads(text[text.find("{"):]).get("findings", []), seen
    except (ValueError, AttributeError):
        print("  task returned no valid JSON; nothing used"); return [], seen

# ---------- applying findings, with every check in code ----------

def index(cs):
    by_name, by_city = {}, {}
    for c in cs:
        for n in {norm(c["name"]), norm(c.get("formerly", ""))} - {""}:
            by_name.setdefault(n, set()).add(c["_id"])
            by_city.setdefault((" ".join(n.split()[:3]), (c.get("city") or "").lower()), set()).add(c["_id"])
    return by_name, by_city

def find(by_name, by_city, cs_by_id, name, city):
    n = norm(name)
    ids = by_name.get(n, set()) or by_city.get((" ".join(n.split()[:3]), city.lower()), set())
    if len(ids) > 1 and city:
        ids = {i for i in ids if (cs_by_id[i].get("city") or "").lower() == city.lower()}
    return next(iter(ids)) if len(ids) == 1 else None

def valid_date(d, today):
    if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", d or ""):
        return False
    try:
        full = d + "-01" * (2 - d.count("-"))
        return datetime.date.fromisoformat(full) <= today
    except ValueError:
        return False

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def locate(address, city, state):
    """Coordinates for a new or moved company: the street address, else the city center; None if neither geocodes."""
    from geocode import geocode
    import time
    for query, prec in ((address, "address"), ("%s, %s" % (city, {"IN": "Indiana", "MI": "Michigan"}.get(state, state)), "city")):
        if query:
            try:
                ll = geocode(query); time.sleep(1.1)
            except Exception:
                ll = None
            if ll:
                return round(ll[0], 5), round(ll[1], 5), prec
    return None

def apply(findings, seen, ctx, today, dry=False):
    trusted, sectors, comps, cities, _ = ctx
    cs = [c for c in companies()]
    cities = set(cities) | {c.get("city", "") for c in cs}
    cs_by_id = {c["_id"]: c for c in cs}
    by_name, by_city = index(cs)
    applied, skipped = [], {}
    def skip(reason):
        skipped[reason] = skipped.get(reason, 0) + 1
    done = set()
    for f in findings:
        t, url = f.get("type"), (f.get("source_url") or "").strip()
        if t not in TYPES or t == "none":
            continue
        if f.get("confidence") != "high":
            skip("not high confidence"); continue
        if not url.startswith("https://") or not domain_ok(url, trusted):
            skip("source not on a trusted domain"); continue
        if canon(url) not in seen:
            skip("source not retrieved in this run"); continue
        if not valid_date(f.get("date"), today):
            skip("missing or future date"); continue
        summary = re.sub(r"\s+", " ", f.get("summary") or "").strip()[:400]
        if not summary:
            skip("no summary"); continue
        city = (f.get("city") or "").strip()
        key = (t, norm(f.get("company_name", "")), canon(url))
        if key in done:
            continue
        done.add(key)
        if t == "milestone":
            ms = tomllib.load(open(P("data", "milestones.toml"), "rb")).get("milestone", [])
            if any(canon(m.get("source", "")) == canon(url) for m in ms):
                skip("already recorded"); continue
            cid = find(by_name, by_city, cs_by_id, f.get("company_name", ""), city) or ""
            entry = '\n[[milestone]]\ndate = %s\ntitle = %s\n%ssource = %s\n' % (q(f["date"]), q(summary), ("company = %s\n" % q(cid)) if cid else "", q(url))
            if not dry:
                with open(P("data", "milestones.toml"), "a", encoding="utf-8") as fh:
                    fh.write(entry)
            applied.append({"type": t, "file": "data/milestones.toml", "summary": summary, "date": f["date"], "source": url}); continue
        if t == "new_company":
            name = (f.get("new_name") or f.get("company_name") or "").strip()
            if not name or city not in cities or f.get("state") not in STATES or f.get("sector") not in sectors:
                skip("new company outside the known cities or without a valid sector"); continue
            if find(by_name, by_city, cs_by_id, name, city):
                skip("company already on the map"); continue
            fname = "%s--%s.toml" % (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-"))
            if os.path.exists(P("companies", fname)):
                skip("company already on the map"); continue
            products = [p.strip()[:80] for p in f.get("products", []) if p.strip()][:5] or ["Manufacturing"]
            ll = None if dry else locate(f.get("new_address", "").strip(), city, f["state"])
            if not dry and not ll:
                skip("new company could not be geocoded"); continue
            lines = ["# %s" % name, "# Added by the automated news review from %s." % urllib.parse.urlparse(url).hostname, "",
                     "name = %s" % q(name), 'kind = "company"', "city = %s" % q(city), "state = %s" % q(f["state"])]
            if f.get("new_address"):
                lines.append("address = %s" % q(f["new_address"].strip()[:160]))
            if ll:
                lines += ["lat = %.5f" % ll[0], "lon = %.5f" % ll[1]] + (['location_precision = "city"'] if ll[2] == "city" else [])
            if (f.get("website") or "").startswith("https://"):
                lines.append("website = %s" % q(f["website"].strip()))
            lines += ["", "sector = %s" % q(f["sector"]), "products = [%s]" % ", ".join(q(p) for p in products), "",
                      "description = %s" % q(summary), "", "source = %s" % q(url), "updated = %s" % q(today.isoformat()), ""]
            if not dry:
                open(P("companies", fname), "w", encoding="utf-8").write("\n".join(lines))
            applied.append({"type": t, "file": "companies/" + fname, "summary": summary, "date": f["date"], "source": url}); continue
        cid = find(by_name, by_city, cs_by_id, f.get("company_name", ""), city)
        if not cid:
            skip("company not matched to exactly one file"); continue
        c = cs_by_id[cid]; path = P("companies", c["_file"]); fields = {}
        if t == "closure":
            if c.get("closed"):
                skip("already closed"); continue
            fields = {"closed": f["date"], "closed_note": summary + " (automated news review)", "closed_source": url}
        elif t == "rename":
            new = (f.get("new_name") or "").strip()
            if not new or norm(new) == norm(c["name"]):
                skip("rename without a new name"); continue
            fields = {"formerly": c.get("formerly") or c["name"], "name": new, "status_note": summary + " (%s)" % url}
            if (f.get("website") or "").startswith("https://"):
                fields["website"] = f["website"].strip()
        elif t == "move":
            addr = (f.get("new_address") or "").strip()
            if not addr or norm(addr) == norm(c.get("address", "")) or city not in cities:
                skip("move without a new address in the region"); continue
            ll = None if dry else locate(addr, c.get("city", ""), c.get("state", ""))
            if not dry and (not ll or ll[2] != "address"):
                skip("new address could not be geocoded"); continue
            fields = {"address": addr[:160], "status_note": summary + " (%s)" % url}
            if ll:
                fields.update({"lat": ll[0], "lon": ll[1]})
        elif t == "humanoid_capability":
            add = [k for k in f.get("components", []) if k in comps]
            if not add:
                skip("capability without a component"); continue
            have = list(c.get("humanoid", []))
            new = have + [k for k in add if k not in have]
            fields = {"humanoid": new, "humanoid_note": summary + " (%s)" % url}
            if c.get("humanoid_evidence") != "confirmed":
                fields["humanoid_evidence"] = "self-reported"
        if not dry:
            for k, v in fields.items():
                if isinstance(v, list):
                    text = open(path, encoding="utf-8").read()
                    line = "%s = [%s]" % (k, ", ".join(q(x) for x in v))
                    text = re.sub(r"(?m)^%s = .*$" % k, line, text) if re.search(r"(?m)^%s = " % k, text) else re.sub(r"(?m)^(sector = )", line + "\n" + r"\1", text, count=1)
                    open(path, "w", encoding="utf-8").write(text)
                else:
                    set_field(path, k, v)
            if t == "move":
                text = open(path, encoding="utf-8").read()
                text = re.sub(r"(?m)^location_precision = .*\n", "", text)
                open(path, "w", encoding="utf-8").write(text)
            set_field(path, "updated", today.isoformat())
            tomllib.load(open(path, "rb"))     # the file must still parse
        applied.append({"type": t, "file": "companies/" + c["_file"], "company": c["name"], "summary": summary, "date": f["date"], "source": url,
                        "fields": sorted(fields)})
    return applied, skipped

# ---------- the run ----------

def news_prompts(today):
    start = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    where = ", ".join(v for v in COUNTIES.values())
    base = ("Today is %s. Search the trusted news sources for articles published from %s to today about the region's "
            "manufacturers and physical-AI activity in these counties: %s. Read each article you rely on with web_fetch. "
            "Report only facts an article states outright, following the curation rules; report each event once, with the "
            "article's URL exactly as you retrieved it. If nothing qualifies, return an empty list.\n\nFocus: " % (today, start, where))
    return [("closures", base + "plant closures, companies ceasing operations, bankruptcies and liquidations (not layoffs or temporary shutdowns)."),
            ("changes", base + "new manufacturing plants, startups and investors opening in the region; expansions; acquisitions, mergers and "
                              "renames of local manufacturers; companies moving within the region."),
            ("physical-ai", base + "robots, humanoids, automation and physical AI: local companies making robot components (motors, gear "
                                  "reducers, actuators, sensors, batteries, electronics), robot or humanoid pilots in local plants, robotics "
                                  "companies, and Notre Dame physical-AI work with industry.")]

def closure_targets(today, n):
    path = P("data", ".closure-review.csv")
    if not os.path.exists(path):
        return []
    rows = [r for r in csv.DictReader(open(path)) if r["strength"] == "strong"]
    cs = {c["_file"]: c for c in companies()}
    rows = [dict(r, address=cs[f].get("address", ""), products=", ".join(cs[f].get("products", [])[:3]))
            for r in rows for f in [r["file"].split("/")[-1]] if f in cs and not cs[f].get("closed")]
    rows.sort(key=lambda r: r["file"])
    if not rows:
        return []
    k = ((today.year * 12 + today.month) * n) % len(rows)
    return (rows[k:] + rows[:k])[:n]

def main():
    dry = "--dry-run" in sys.argv
    today = datetime.date.today()
    ctx = load_context(); trusted, sectors, comps, cities, rules = ctx
    fmt = schema(sectors, comps)
    tasks = [("news", label, prompt, 8, 10) for label, prompt in news_prompts(today)]
    for r in closure_targets(today, CLOSURE_CHECKS):
        tasks.append(("closure", r["company"], (
            "Today is %s. Search the trusted news sources for whether this facility has closed, been renamed or acquired, or moved: "
            "%s, %s (%s), which makes %s. Report a closure only if an article states that this facility closed or ceased "
            "operations, with the date. If the sources say nothing about it, return an empty list."
            % (today, r["company"], r["city"], r.get("address") or "address not on file", r.get("products") or "products not on file")), 3, 3))
    system = ("You review regional news for a public map of manufacturing in the South Bend-Elkhart region. Follow these rules "
              "exactly. Your findings are applied without a person reviewing them, so mark a finding high confidence only when the "
              "article states the fact outright for this facility, and leave out anything uncertain.\n\n" + rules)
    if dry:
        print("model %s, budget $%.2f, %d trusted domains" % (MODEL, BUDGET, len(trusted)))
        for kind, label, prompt, s, f in tasks:
            print("- %s: %s (up to %d searches, %d page reads; worst case $%.2f)" % (kind, label, s, f, EST[kind]))
        print("worst case for all tasks: $%.2f; tasks beyond the budget wait for next month" % sum(EST[k] for k, *_ in tasks))
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; skipping the news review"); return
    import anthropic
    client = anthropic.Anthropic()
    ledger = Ledger(BUDGET)
    findings, seen, ran, deferred = [], set(), [], 0
    for kind, label, prompt, s, f in tasks:
        if not ledger.can(kind):
            deferred += 1; continue
        try:
            got, urls = ask(client, ledger, system, prompt, fmt, trusted, s, f)
        except anthropic.APIStatusError as e:
            print("  %s %s: API error %s" % (kind, label, e.status_code)); continue
        except anthropic.APIConnectionError:
            print("  %s %s: connection error" % (kind, label)); continue
        findings += got; seen |= urls; ran.append(label)
        print("  %s %s: %d findings, $%.2f spent so far" % (kind, label, len(got), ledger.spent))
    applied, skipped = apply(findings, seen, ctx, today)
    log_path = P("data", "news_review.json")
    log = json.load(open(log_path)) if os.path.exists(log_path) else {}
    log[today.isoformat()] = {"model": MODEL, "cost_usd": round(ledger.spent, 2), "budget_usd": BUDGET, "requests": ledger.calls,
                              "searches": ledger.searches, "tasks": len(ran), "tasks_deferred": deferred, "findings": len(findings),
                              "applied": applied, "skipped": skipped}
    json.dump(log, open(log_path, "w"), indent=1, ensure_ascii=False)
    print("news review: %d tasks, %d findings, %d applied, $%.2f of $%.2f; skipped: %s" % (len(ran), len(findings), len(applied), ledger.spent, BUDGET, skipped or "none"))
    for a in applied:
        print("  applied %s: %s (%s)" % (a["type"], a.get("company") or a["file"], a["source"]))

if __name__ == "__main__":
    main()
