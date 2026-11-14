#!/usr/bin/env python3
"""Compare each company file's address with the addresses on the company's own website.

    python3 scripts/check_sites.py [out.csv]      # default: audits/site-address-check.csv

For every company on the map with a website, the script fetches the home page and the usual
contact, location and about pages, and reads the street addresses they give: schema.org
PostalAddress data first, then addresses written out in the text (number, street, city, IN or MI,
ZIP). It then compares them with the file's address by street number and street name, so
"2600 Ada Dr" and "2600 Ada Drive" match. Every row is one company file:

- match:       the site gives this address;
- elsewhere:   the site gives one or more addresses in Indiana or Michigan, none of them this one;
- no_address:  the site loads but gives no readable address;
- unreachable: the site does not load.

Nothing is changed. A mismatch is a lead for a person: a company often lists only its office, and
multi-plant companies list some plants and not others. Treat "elsewhere" as strong only for a
single-site company whose site gives a single address.
"""
import concurrent.futures, csv, html, re, sys, urllib.request
from common import P, companies

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
PAGES = ("", "/contact", "/contact-us", "/locations", "/about", "/about-us")
SUFFIX = r"(?:St|Street|Rd|Road|Dr|Drive|Ave|Avenue|Blvd|Boulevard|Hwy|Highway|Pkwy|Parkway|Ct|Court|Ln|Lane|Way|Pl|Place|Trail|Cir|Circle)"
ADDR = re.compile(r"\b(\d{1,6})\s+((?:[NSEW]\.?\s+)?(?:[A-Z0-9][\w.'-]*\s+){0,4}?(?:" + SUFFIX + r"|US\s?\d+|SR\s?\d+|State Road \d+|County Road \d+\w*|CR \d+\w*)\b\.?(?:\s+[NSEW]\b\.?)?)"
                  r"[\s,]+(?:(?:Suite|Ste|Unit)\.?\s*#?\w+[\s,]+)?([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){0,2}),?\s+(IN|MI|Indiana|Michigan)\.?,?\s+(\d{5})")
STOP = {"n", "s", "e", "w", "north", "south", "east", "west", "st", "street", "rd", "road", "dr", "drive", "ave", "avenue", "blvd", "boulevard",
        "hwy", "highway", "pkwy", "parkway", "ct", "court", "ln", "lane", "way", "pl", "place", "the"}

def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return r.read(1_500_000).decode("utf-8", "replace")
    except Exception:
        return None

def found_addresses(page):
    text = html.unescape(page)
    out = set()
    for m in re.finditer(r'"streetAddress"\s*:\s*"([^"]+)"[^}]*?"addressLocality"\s*:\s*"([^"]+)"[^}]*?"postalCode"\s*:\s*"(\d{5})', text):
        out.add("%s, %s %s" % (m[1].strip(), m[2].strip(), m[3]))
    flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))
    for m in ADDR.finditer(flat):
        out.add("%s %s, %s %s" % (m[1], m[2].strip(), m[3], m[5]))
    return out

def key(address):
    """(street number, first meaningful street word) of the first line of an address."""
    first = address.split(",")[0].lower()
    num = re.match(r"\s*(\d+)", first)
    words = [w for w in re.findall(r"[a-z0-9]+", first)[1:] if w not in STOP]
    return (num[1] if num else "", words[0] if words else "")

def check(c):
    url = c["website"] if "//" in c["website"] else "https://" + c["website"]
    base = re.match(r"https?://[^/]+", url)[0]
    loaded, found = False, set()
    for path in PAGES:
        page = get(base + path)
        if page:
            loaded = True
            found |= found_addresses(page)
    mine = key(c.get("address", ""))
    match = [a for a in found if key(a) == mine and mine[0]]
    status = "unreachable" if not loaded else "match" if match else "elsewhere" if found else "no_address"
    return c, status, sorted(found)

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else P("audits", "site-address-check.csv")
    cs = [c for c in companies() if c.get("website") and not any(c.get(k) for k in ("closed", "removed", "presumed_closed"))]
    groups = {}
    for c in cs:
        d = re.sub(r"^www\.", "", re.sub(r"^https?://", "", c["website"].lower()).split("/")[0])
        groups.setdefault(d, []).append(c)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(16) as ex:
        for c, status, found in ex.map(check, cs):
            d = re.sub(r"^www\.", "", re.sub(r"^https?://", "", c["website"].lower()).split("/")[0])
            rows.append({"file": "companies/" + c["_file"], "name": c["name"], "address": c.get("address", ""), "website": c["website"],
                         "status": status, "sites_with_this_website": len(groups[d]), "site_addresses": "; ".join(found),
                         "map_status": "unconfirmed" if c.get("unconfirmed") else "verified" if c.get("verified") else "osha" if c.get("osha_id") else ""})
    rows.sort(key=lambda r: ({"elsewhere": 0, "match": 2, "no_address": 1, "unreachable": 3}[r["status"]], r["name"]))
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    n = {s: sum(1 for r in rows if r["status"] == s) for s in ("match", "elsewhere", "no_address", "unreachable")}
    print("%d companies with a website: %s; wrote %s" % (len(rows), ", ".join("%s %d" % kv for kv in n.items()), out))

if __name__ == "__main__":
    main()
