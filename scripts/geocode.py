#!/usr/bin/env python3
"""Fill in lat/lon for company files that have an address but no coordinates.

    python3 scripts/geocode.py            # all files missing lat/lon
    python3 scripts/geocode.py companies/acme.toml

Uses OpenStreetMap's Nominatim (one request per second, as its usage policy asks), falling back to the
U.S. Census Bureau's geocoder, and writes the two lines into the file. Check the result on the map; if a street address is unknown to
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
    return census(address)

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
