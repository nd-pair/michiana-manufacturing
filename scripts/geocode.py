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
    a = re.sub(r"(?i)(,?\s*(ste\.?|suite|unit|apt\.?|room|rm\.?|service door|bldg\.?|building)\s*[#\w-]+)|(\s*#\s*\w+)", "", address)
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
    try:
        r = json.load(urllib.request.urlopen("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + q, timeout=30))
    except Exception:
        return None
    m = r.get("result", {}).get("addressMatches") or []
    return (float(m[0]["coordinates"]["y"]), float(m[0]["coordinates"]["x"])) if m else None

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
        line = re.search(r"^address\s*=.*$", text, re.M)
        ins = "\nlat = %.5f\nlon = %.5f" % hit
        text = text[:line.end()] + ins + text[line.end():]
        open(path, "w", encoding="utf-8").write(text)
        print("%s: %.5f, %.5f" % (os.path.basename(path), *hit))
        time.sleep(1.1)

if __name__ == "__main__":
    main(sys.argv[1:])
