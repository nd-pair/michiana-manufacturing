#!/usr/bin/env python3
"""Compare each company file's address with the addresses on the company's own website.

    python3 scripts/check_sites.py [out.csv]      # default: audits/site-address-check.csv

For every company on the map with a website, the script fetches the home page and the usual
contact, location and about pages, and reads the street addresses they give: schema.org
PostalAddress data first, then addresses written out in the text (number, street, city, IN or MI,
ZIP). It then compares them with the file's address by street number and street name, so
"2600 Ada Dr" and "2600 Ada Drive" match. Every row is one company file:

- match:         the site gives this address;
- same_street:   the site gives this street with another number (often Elkhart County's two numbering
                 systems, 53212 vs 2600 Ada Dr) or a different spelling;
- elsewhere:     the site gives other addresses in the region, none on this street;
- out_of_region: the site gives only addresses outside the region (often a corporate head office);
- no_address:  the site loads but gives no readable address;
- unreachable: the site does not load.

Nothing is changed. A mismatch is a lead for a person: a company often lists only its office, and
multi-plant companies list some plants and not others. Treat "elsewhere" as strong only for a
single-site company whose site gives a single address.
"""
import concurrent.futures, csv, html, json, re, socket, sys, urllib.request
from common import P, companies

ZIPS = json.load(open(P("data", "region_zips.json")))["zips"]

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
PAGES = ("", "/contact", "/contact-us", "/locations", "/about", "/about-us")
SUFFIX = r"(?:St|Street|Rd|Road|Dr|Drive|Ave|Avenue|Blvd|Boulevard|Hwy|Highway|Pkwy|Parkway|Ct|Court|Ln|Lane|Way|Pl|Place|Trail|Cir|Circle)"
ADDR = re.compile(r"\b(\d{1,6})\s+((?:[NSEW]\.?\s+)?(?:[A-Z0-9][\w.'-]*\s+){0,4}?(?:" + SUFFIX + r"|US\s?\d+|SR\s?\d+|State Road \d+|County Road \d+\w*|CR \d+\w*)\b\.?(?:\s+[NSEW]\b\.?)?)"
                  r"[\s,]+(?:(?:Suite|Ste|Unit)\.?\s*#?\w+[\s,]+)?([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){0,2}),?\s+(IN|MI|Indiana|Michigan)\.?,?\s+(\d{5})")
STOP = {"n", "s", "e", "w", "north", "south", "east", "west", "st", "street", "rd", "road", "dr", "drive", "ave", "avenue", "blvd", "boulevard",
        "hwy", "highway", "pkwy", "parkway", "ct", "court", "ln", "lane", "way", "pl", "place", "the",
        "ste", "suite", "unit", "bldg", "building", "a", "b", "d"}

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

FILLER = {"address", "visit", "phone", "tel", "fax", "call", "copyright", "c", "hours"}
WORDS = {"cr": "county", "co": "county", "sr": "state", "third": "3rd", "first": "1st", "second": "2nd", "fourth": "4th",
         "mt": "mount", "one": "1", "two": "2", "hwy": "highway", "us": "us"}

def key(address):
    """(street number, street words) of the first line of an address, normalized: the number is the
    last one before the street name (a year or phone fragment in front is dropped), CR = County Road,
    Third = 3rd, One = 1, leading zeros removed."""
    first = address.split(",")[0].lower().replace("-", " ")
    toks = [WORDS.get(t, t) for t in re.findall(r"[a-z0-9]+", first)]
    nums = [i for i, t in enumerate(toks) if t.isdigit()]
    # the house number: the first number followed by a street word, skipping filler such as a year or a
    # phone fragment followed by "address", "phone" or "call"
    lead = [j for j in nums if j + 1 < len(toks) and not toks[j + 1].isdigit() and toks[j + 1] not in FILLER]
    j = lead[0] if lead else (nums[0] if nums else -1)
    num = toks[j].lstrip("0") if j >= 0 else ""
    street = tuple(t for t in toks[j + 1:] if t not in STOP and t not in ("county", "state", "road", "address", "visit", "us"))[:1]
    return (num, street)

def classify(listed, found, zips):
    """match, same_street (same street, other number: often Elkhart County's two numbering systems),
    elsewhere (another address in the region), out_of_region (only addresses outside the region)."""
    regional = [a for a in found if (re.search(r"(\d{5})\s*$", a) or [None, ""])[1] in zips]
    if not found:
        return "no_address", []
    if not regional:
        return "out_of_region", []
    mine = key(listed)
    if any(key(a) == mine for a in regional) and mine[0]:
        return "match", regional
    if any(key(a)[1] and key(a)[1] == mine[1] for a in regional):
        return "same_street", regional
    return "elsewhere", regional

def check(c):
    url = c["website"] if "//" in c["website"] else "https://" + c["website"]
    base = re.match(r"https?://[^/]+", url)[0]
    h = re.sub(r"^https?://", "", base)
    try:
        socket.getaddrinfo(h, 443)
    except socket.gaierror:
        if not h.startswith("www."):
            base = base.replace("://", "://www.", 1)   # only www. resolves (atcomp.com, glavalbus.com)
    loaded, found = False, set()
    for path in PAGES:
        page = get(base + path)
        if page:
            loaded = True
            found |= found_addresses(page)
    if not loaded:
        return c, "unreachable", sorted(found)
    status, regional = classify(c.get("address", ""), found, ZIPS)
    return c, status, sorted(found)

def reclassify(path):
    """Sort an earlier run's rows again with the current matching rules, without fetching."""
    rows = list(csv.DictReader(open(path)))
    current = {"companies/" + c["_file"]: c for c in companies()}
    rows = [r for r in rows if r["file"] in current and not any(current[r["file"]].get(k) for k in ("closed", "removed", "presumed_closed"))]
    for r in rows:
        r["address"] = current[r["file"]].get("address", "")   # the file's address now, after any fixes
        if r["status"] != "unreachable":
            r["status"], _ = classify(r["address"], [a for a in r["site_addresses"].split("; ") if a], ZIPS)
    return rows

def main():
    out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else P("audits", "site-address-check.csv")
    if "--reclassify" in sys.argv:
        rows = reclassify(out)
        rows.sort(key=lambda r: ({"elsewhere": 0, "same_street": 1, "match": 3, "out_of_region": 2, "no_address": 2, "unreachable": 4}[r["status"]], r["name"]))
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        n = {s: sum(1 for r in rows if r["status"] == s) for s in ("match", "same_street", "elsewhere", "out_of_region", "no_address", "unreachable")}
        print("reclassified %d rows: %s" % (len(rows), ", ".join("%s %d" % kv for kv in n.items())))
        return
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
    rows.sort(key=lambda r: ({"elsewhere": 0, "same_street": 1, "match": 3, "out_of_region": 2, "no_address": 2, "unreachable": 4}[r["status"]], r["name"]))
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    n = {s: sum(1 for r in rows if r["status"] == s) for s in ("match", "same_street", "elsewhere", "out_of_region", "no_address", "unreachable")}
    print("%d companies with a website: %s; wrote %s" % (len(rows), ", ".join("%s %d" % kv for kv in n.items()), out))

if __name__ == "__main__":
    main()
