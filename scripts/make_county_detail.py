#!/usr/bin/env python3
"""Detailed county outlines for telling which county a plant is in. Run once; the result is committed.

    python3 scripts/make_county_detail.py [cb_2023_us_county_500k.zip]   # default: download it

data/region_counties.json holds simplified outlines (a dozen points per county) for drawing the map.
They are too coarse to place a plant near a county line: Whitley County's eastern edge is one diagonal
that put C&A Tool (4100 US 33, Churubusco) in Allen County. This script reads the Census Bureau's
1:500,000 cartographic boundary file (www2.census.gov, public, no key) and writes the same counties'
detailed outlines, rounded to 5 decimals (about 1 m), to data/region_counties_detail.json.
scripts/import_osha.py county_of() uses that file when it exists.
"""
import io, json, re, sys, urllib.request, zipfile
from common import P

URL = "https://www2.census.gov/geo/tiger/GENZ2023/kml/cb_2023_us_county_500k.zip"
UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}

def main():
    data = open(sys.argv[1], "rb").read() if len(sys.argv) > 1 else urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=300).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    kml = z.read(next(n for n in z.namelist() if n.endswith(".kml"))).decode("utf-8")
    want = {c["id"]: c for c in json.load(open(P("data", "region_counties.json")))}
    out = []
    for pm in re.findall(r"<Placemark[^>]*>(.*?)</Placemark>", kml, re.S):
        geoid = re.search(r"<th>GEOID</th>\s*<td>(\d{5})</td>", pm)
        if not geoid or geoid[1] not in want:
            continue
        rings = []
        for outer in re.findall(r"<outerBoundaryIs>(.*?)</outerBoundaryIs>", pm, re.S):
            pts = re.search(r"<coordinates>(.*?)</coordinates>", outer, re.S)[1].split()
            rings.append([[round(float(p.split(",")[0]), 5), round(float(p.split(",")[1]), 5)] for p in pts])
        c = want[geoid[1]]
        out.append({"id": c["id"], "name": c["name"], "state": c["state"], "core": c["core"], "rings": rings})
    missing = sorted(set(want) - {c["id"] for c in out})
    if missing:
        sys.exit("counties not found in the Census file: %s" % ", ".join(missing))
    out.sort(key=lambda c: c["id"])
    json.dump(out, open(P("data", "region_counties_detail.json"), "w"), separators=(",", ":"))
    print("wrote data/region_counties_detail.json: %d counties, %d points (source %s)" % (len(out), sum(len(r) for c in out for r in c["rings"]), URL))

if __name__ == "__main__":
    main()
