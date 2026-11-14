#!/usr/bin/env python3
"""List companies that may have closed, for a person to review.

    python3 scripts/check_closed.py [out.csv]      # default: data/.closure-review.csv (not committed)

HIFLD lags closures by years, and no open registry says which facilities have shut down, so this
script only collects evidence; it never edits a company file. For every company with a website it
checks whether the domain still resolves, whether the home page answers, and whether it redirects
to another company's domain or to a domain-sale page. Each row gets a strength:

- strong: the domain no longer exists, or it is parked or for sale;
- medium: the site redirects to an unrelated domain (often an acquirer), or the server refuses;
- weak:   the site errors or times out (often a temporary outage).

Two more signals join the website checks, for every company file whether or not it has a website:
- strong: a WARN notice of a closing matched to the plant (data/warn.json, scripts/pull_warn.py) whose
  closing date has passed (weak when the plant still filed with OSHA for a later year);
- medium: another company filed OSHA's Form 300A at the plant's address (`osha_occupant`, set by
  scripts/import_osha.py): the plant may have been sold, renamed or replaced by a new tenant;
- medium: the plant filed OSHA's Form 300A in an earlier year but not in the latest one imported
  (data/osha.json, scripts/import_osha.py); plants under 20 employees need not file, so a drop below
  that size also shows up here.

Confirm a closure from a dated source (news, a WARN notice, a state filing) before marking it:
add closed = YYYY-MM-DD and closed_note = "..." to the company file. Do not delete the file, or the
monthly HIFLD import will add the facility again.
"""
import concurrent.futures, csv, datetime, json, os, socket, ssl, sys, urllib.error, urllib.parse, urllib.request
from common import P, companies

PARKED = ("domain is for sale", "buy this domain", "this domain may be for sale", "hugedomains", "sedo.com",
          "dan.com", "afternic", "godaddy.com/domainsearch", "parkingcrew", "bodis.com", "domain has expired",
          "this domain has been registered", "is parked free")
UA = {"User-Agent": "Mozilla/5.0 (compatible; michiana-manufacturing link check)"}

def host(url):
    h = urllib.parse.urlparse(url if "//" in url else "https://" + url).hostname or ""
    return h.lower().removeprefix("www.")

def base(h):
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h

def check(c):
    url = c["website"] if "//" in c["website"] else "https://" + c["website"]
    h = host(url)
    try:
        socket.getaddrinfo(h, 443)
    except socket.gaierror:
        try:
            socket.getaddrinfo("www." + h, 443)
        except socket.gaierror:
            return "strong", "domain does not resolve", ""
    # certificates are checked: an expired or mismatched certificate is itself a sign of an abandoned site,
    # and an unverified connection could land anywhere. Plain http is still tried after it.
    ctx = ssl.create_default_context()
    last, bad_cert = None, False
    for u in (url, url.replace("https://", "http://", 1)):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15, context=ctx) as r:
                final, body = r.geturl(), r.read(200000).decode("utf-8", "ignore").lower()
            fh = host(final)
            if any(p in body for p in PARKED):
                return "strong", "parked or for sale", final
            if base(fh) != base(h):
                return "medium", "redirects to another domain", final
            if bad_cert:
                return "weak", "secure connection failed; the site answers over plain http", final
            return "", "ok", final
        except urllib.error.HTTPError as e:
            last = ("medium" if e.code in (404, 410) else "weak", "HTTP %d" % e.code, u)
            if e.code in (403, 429):            # bot protection; the site is up
                return "", "ok (HTTP %d)" % e.code, u
        except Exception as e:
            if isinstance(getattr(e, "reason", e), ssl.SSLError) or isinstance(e, ssl.SSLError):
                bad_cert = True
                last = ("weak", "secure connection failed: " + str(getattr(e, "reason", e))[:70], u)
            else:
                last = ("weak", type(e).__name__ + ": " + str(e)[:80], u)
    return last

def record_signals(cs):
    """Closure evidence from public records: WARN closing notices and OSHA filings that stopped."""
    by_id, out, today = {c["_id"]: c for c in cs}, [], datetime.date.today().isoformat()
    row = lambda c, strength, why: {"strength": strength, "reason": why, "company": c["name"], "city": c["city"], "website": c.get("website", ""),
                                    "lands_on": "", "file": "companies/" + c["_file"], "employees": c.get("employees", ""), "source": c.get("source", "")[:40]}
    filed = {}   # company file -> latest year it filed with OSHA
    if os.path.exists(P("data", "osha.json")):
        for y, est in json.load(open(P("data", "osha.json"))).get("years", {}).items():
            for v in est.values():
                filed[v["company"]] = max(filed.get(v["company"], ""), y)
    if os.path.exists(P("data", "warn.json")):
        for n in json.load(open(P("data", "warn.json")))["notices"]:
            c = by_id.get(n.get("match"))
            eff = n.get("effective") or n["notice_date"]
            if c and n["type"] == "CL" and eff <= today:
                later = filed.get(c["_id"], "") > eff[:4]   # still filing with OSHA after the closing date: likely a partial closing
                out.append(row(c, "weak" if later else "strong", "WARN closing notice %s, effective %s, %s workers%s" % (n["notice_date"], eff, n.get("workers") or "?",
                               "; but filed with OSHA for %s" % filed[c["_id"]] if later else "")))
    for c in cs:
        if c.get("osha_occupant"):
            out.append(row(c, "medium", "another name filed with OSHA at this address: %s; a successor, rename or new tenant" % c["osha_occupant"]))
    if os.path.exists(P("data", "osha.json")):
        years = json.load(open(P("data", "osha.json"))).get("years", {})
        ys = sorted(years)
        if len(ys) >= 2:
            latest = {v["company"] for v in years[ys[-1]].values()}
            earlier = {}
            for y in ys[:-1]:
                for v in years[y].values():
                    earlier[v["company"]] = (y, v.get("employees"))
            for cid, (y, emp) in earlier.items():
                if cid not in latest and cid in by_id:
                    out.append(row(by_id[cid], "medium", "filed OSHA Form 300A for %s (%s employees) but not for %s" % (y, emp or "?", ys[-1])))
    return out

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else P("data", ".closure-review.csv")
    cs = [c for c in companies() if c.get("website") and not c.get("closed") and not c.get("removed")]
    rows = []
    with concurrent.futures.ThreadPoolExecutor(32) as ex:
        for c, (strength, why, final) in zip(cs, ex.map(check, cs)):
            if strength:
                rows.append({"strength": strength, "reason": why, "company": c["name"], "city": c["city"],
                             "website": c["website"], "lands_on": final, "file": "companies/" + c["_file"],
                             "employees": c.get("employees", ""), "source": c.get("source", "")[:40]})
    rows += record_signals([c for c in companies() if not c.get("closed") and not c.get("removed")])
    order = {"strong": 0, "medium": 1, "weak": 2}
    rows.sort(key=lambda r: (order[r["strength"]], r["company"]))
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["strength"]); w.writeheader(); w.writerows(rows)
    n = {k: sum(1 for r in rows if r["strength"] == k) for k in order}
    print("checked %d websites: %d strong, %d medium, %d weak; wrote %s" % (len(cs), n["strong"], n["medium"], n["weak"], out))

if __name__ == "__main__":
    main()
