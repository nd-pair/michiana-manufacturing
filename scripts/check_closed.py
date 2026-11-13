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

Confirm a closure from a dated source (news, a WARN notice, a state filing) before marking it:
add closed = YYYY-MM-DD and closed_note = "..." to the company file. Do not delete the file, or the
monthly HIFLD import will add the facility again.
"""
import concurrent.futures, csv, os, socket, ssl, sys, urllib.error, urllib.parse, urllib.request
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
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    last = None
    for u in (url, url.replace("https://", "http://", 1)):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15, context=ctx) as r:
                final, body = r.geturl(), r.read(200000).decode("utf-8", "ignore").lower()
            fh = host(final)
            if any(p in body for p in PARKED):
                return "strong", "parked or for sale", final
            if base(fh) != base(h):
                return "medium", "redirects to another domain", final
            return "", "ok", final
        except urllib.error.HTTPError as e:
            last = ("medium" if e.code in (404, 410) else "weak", "HTTP %d" % e.code, u)
            if e.code in (403, 429):            # bot protection; the site is up
                return "", "ok (HTTP %d)" % e.code, u
        except Exception as e:
            last = ("weak", type(e).__name__ + ": " + str(e)[:80], u)
    return last

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
    order = {"strong": 0, "medium": 1, "weak": 2}
    rows.sort(key=lambda r: (order[r["strength"]], r["company"]))
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["strength"]); w.writeheader(); w.writerows(rows)
    n = {k: sum(1 for r in rows if r["strength"] == k) for k in order}
    print("checked %d websites: %d strong, %d medium, %d weak; wrote %s" % (len(cs), n["strong"], n["medium"], n["weak"], out))

if __name__ == "__main__":
    main()
