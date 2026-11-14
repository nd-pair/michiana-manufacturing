#!/usr/bin/env python3
"""Fill in lat/lon for company files that have an address but no coordinates.

    python3 scripts/geocode.py            # all files missing lat/lon
    python3 scripts/geocode.py companies/acme.toml

Uses OpenStreetMap's Nominatim (one request per second, as its usage policy asks), falling back to the
U.S. Census Bureau's geocoder and, in Indiana, the state's address points, and writes the two lines into the file. Check the result on the map; if a street address is unknown to
OpenStreetMap, look it up elsewhere and type lat/lon in by hand.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def street_only(address):
    """Drop suite, unit, apartment and door numbers, which OpenStreetMap does not know."""
    # whole words only: without \b, "rm" inside "Herman" and "ste" inside "Western" were cut ("930 He Street")
    a = re.sub(r"(?i),?\s*\b(?:ste|suite|unit|apt|room|rm|service door|bldg|building)\b\.?\s*[#\w-]+|\s*#\s*\w+", "", address)
    return re.sub(r"\s*,\s*,", ",", a).strip(" ,")

def geocode(address):
    address = street_only(address)
    q = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1, "countrycodes": "us"})
    req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q,
                                 headers={"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"})
    r = json.load(urllib.request.urlopen(req, timeout=30))
    if r:
        return (float(r[0]["lat"]), float(r[0]["lon"]))
    return census(address) or (indiana_point(address) if re.search(r",\s*IN\b", address) else None)

IN_POINTS = "https://gisdata.in.gov/server/rest/services/Hosted/Address_Points_of_Indiana_Current/FeatureServer/0/query"
IN_COUNTIES = ("Elkhart", "Fulton", "Kosciusko", "LaGrange", "LaPorte", "Marshall", "Noble", "St. Joseph", "Starke", "Whitley")
ST_TYPES = {"st": "street", "ave": "avenue", "av": "avenue", "dr": "drive", "rd": "road", "ln": "lane", "ct": "court", "blvd": "boulevard",
            "pkwy": "parkway", "trl": "trail", "hwy": "highway", "pl": "place", "cir": "circle", "way": "way", "pike": "pike"}
DIRS = {"n": "north", "s": "south", "e": "east", "w": "west"}

def indiana_point(address):
    """(lat, lon) from Indiana's statewide address points (Indiana Geographic Information Office, IndianaMap; public,
    no key), for an Indiana address the Census geocoder and OpenStreetMap do not know. The counties' 911 offices keep
    these points, so they include private and new industrial streets (Brinkley Way in Goshen, Lakota Lane in Bristol,
    Decio Drive in Elkhart). A point counts only with the same house number and street name, in a region county, in
    the address's town or ZIP code; when the address gives a street type or direction that some points share, only
    those count, and a direction no point shares is no match. Several points at one number (the buildings of one
    plant) give their center, if they lie within about 500 m of each other."""
    m = re.match(r"\s*(\d+)\s+(.+?),\s*([^,]+),\s*IN\b\s*(\d{5})?", address, re.I)
    if not m:
        return None
    num, street, town, zip_ = int(m[1]), m[2], re.sub(r"[^a-z]", "", m[3].lower()), m[4]
    w = [x.strip(".").lower() for x in street.split()]
    pre = DIRS.get(w[0], w[0]) if w and DIRS.get(w[0], w[0]) in DIRS.values() and len(w) > 1 else None
    if pre:
        w = w[1:]
    post = DIRS.get(w[-1], w[-1]) if len(w) > 1 and DIRS.get(w[-1], w[-1]) in DIRS.values() else None
    if post:
        w = w[:-1]
    sr = re.match(r"(?:state road|sr|us highway|us hwy|us|county road|cr)\s+(\d+)", " ".join(w))
    name = sr[1] if sr else w[0]
    typ = ST_TYPES.get(w[-1], w[-1]) if not sr and len(w) > 1 else None
    where = "add_number=%d AND UPPER(st_name)='%s' AND county IN (%s)" % (
        num, name.upper().replace("'", "''"), ",".join("'%s County'" % c for c in IN_COUNTIES))
    q = urllib.parse.urlencode({"where": where, "f": "json", "returnGeometry": "false",
                                "outFields": "st_predir,st_postyp,st_posdir,inc_muni,post_comm,post_code,latitude,longitude"})
    try:
        req = urllib.request.Request(IN_POINTS + "?" + q, headers={"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"})
        pts = [f["attributes"] for f in json.load(urllib.request.urlopen(req, timeout=60)).get("features", [])]
    except Exception:
        return None
    low = lambda v: re.sub(r"[^a-z]", "", (v or "").lower())
    pts = [p for p in pts if town in (low(p["inc_muni"]), low(p["post_comm"])) or (zip_ and p["post_code"] == zip_)]
    if typ and any(low(p["st_postyp"]) == typ for p in pts):
        pts = [p for p in pts if low(p["st_postyp"]) == typ]
    d = pre or post
    if d and any(p["st_predir"] or p["st_posdir"] for p in pts):
        pts = [p for p in pts if d in (low(p["st_predir"]), low(p["st_posdir"]))]
    if not pts:
        return None
    lats, lons = [p["latitude"] for p in pts], [p["longitude"] for p in pts]
    if max(lats) - min(lats) > 0.0045 or max(lons) - min(lons) > 0.006:
        return None
    return (sum(lats) / len(lats), sum(lons) / len(lons))

def census(address):
    """Fallback: the U.S. Census Bureau's geocoder, which interpolates along streets OpenStreetMap lacks numbers for."""
    q = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "format": "json"})
    for attempt in range(3):   # the service times out now and then: an error is retried, only "no match" is final
        try:
            r = json.load(urllib.request.urlopen("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + q, timeout=30))
        except Exception:
            time.sleep(3)
            continue
        m = r.get("result", {}).get("addressMatches") or []
        return (float(m[0]["coordinates"]["y"]), float(m[0]["coordinates"]["x"])) if m else None
    return None

def census_zip(address, near):
    """The ZIP code of an address that lacks one, from the Census geocoder's matched address, when the
    match has the same house number and lies within 0.5 km of `near` (lat, lon); else None."""
    if re.search(r"\b\d{5}(-\d{4})?\s*$", address) or not re.match(r"\s*\d", address):
        return None
    q = urllib.parse.urlencode({"address": street_only(address), "benchmark": "Public_AR_Current", "format": "json"})
    try:
        m = (json.load(urllib.request.urlopen("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + q, timeout=30))
             .get("result", {}).get("addressMatches") or [])
    except Exception:
        return None
    if not m or m[0]["matchedAddress"].split()[0] != address.split()[0]:
        return None
    lat, lon = float(m[0]["coordinates"]["y"]), float(m[0]["coordinates"]["x"])
    if abs(lat - near[0]) > 0.0045 or abs(lon - near[1]) > 0.006:   # about 0.5 km
        return None
    z = re.search(r"(\d{5})\s*$", m[0]["matchedAddress"])
    return z[1] if z else None

def main(paths):
    if not paths:
        paths = [os.path.join(ROOT, "companies", n) for n in sorted(os.listdir(os.path.join(ROOT, "companies"))) if n.endswith(".toml")]
    for path in paths:
        with open(path, "rb") as fh:
            c = tomllib.load(fh)
        if "lat" in c or not c.get("address"):
            continue
        hit = geocode(c["address"])
        if not hit:
            print("%s: not found: %s" % (os.path.basename(path), c["address"]))
            time.sleep(1.1); continue
        text = open(path, encoding="utf-8").read()
        z = census_zip(c["address"], hit)   # an address from a verification move often comes without its ZIP
        if z:
            text = re.sub(r'^(address\s*=\s*".*?)"\s*$', lambda mm: '%s %s"' % (mm[1].rstrip(), z), text, count=1, flags=re.M)
        line = re.search(r"^address\s*=.*$", text, re.M)
        ins = "\nlat = %.5f\nlon = %.5f" % hit
        text = text[:line.end()] + ins + text[line.end():]
        open(path, "w", encoding="utf-8").write(text)
        print("%s: %.5f, %.5f" % (os.path.basename(path), *hit))
        time.sleep(1.1)

if __name__ == "__main__":
    main(sys.argv[1:])
