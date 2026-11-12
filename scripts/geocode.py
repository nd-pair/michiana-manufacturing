#!/usr/bin/env python3
"""Fill in lat/lon for company files that have an address but no coordinates.

    python3 scripts/geocode.py            # all files missing lat/lon
    python3 scripts/geocode.py companies/acme.toml

Uses OpenStreetMap's Nominatim (one request per second, as its usage policy asks) and writes
the two lines into the file. Check the result on the map; if a street address is unknown to
OpenStreetMap, look it up elsewhere and type lat/lon in by hand.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def geocode(address):
    q = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1, "countrycodes": "us"})
    req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q,
                                 headers={"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"})
    r = json.load(urllib.request.urlopen(req, timeout=30))
    return (float(r[0]["lat"]), float(r[0]["lon"])) if r else None

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
