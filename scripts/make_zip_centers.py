#!/usr/bin/env python3
"""Centers of the region's ZIP code areas, for placing a plant that no geocoder can find in a town with
no other mapped plant. Run once; the result is committed.

    python3 scripts/make_zip_centers.py [2023_Gaz_zcta_national.zip]   # default: download it

Reads the Census Bureau's ZCTA gazetteer (www2.census.gov, public, no key; the internal point of each
ZIP Code Tabulation Area) and writes the region's ZIP codes (data/region_zips.json) that it has, with
their land area, to data/zip_centers.json. scripts/import_osha.py city_center() uses it as a last
resort, and marks such plants as placed at city level.
"""
import io, json, sys, urllib.request, zipfile
from common import P

URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_zcta_national.zip"
UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}

def main():
    data = open(sys.argv[1], "rb").read() if len(sys.argv) > 1 else urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=300).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    lines = z.read(z.namelist()[0]).decode("utf-8").splitlines()
    head = [h.strip() for h in lines[0].split("\t")]
    want = set(json.load(open(P("data", "region_zips.json")))["zips"])
    out = {}
    for line in lines[1:]:
        r = dict(zip(head, (v.strip() for v in line.split("\t"))))
        if r["GEOID"] in want:
            out[r["GEOID"]] = [round(float(r["INTPTLAT"]), 5), round(float(r["INTPTLONG"]), 5), round(int(r["ALAND"]) / 1e6, 2)]
    json.dump({"source": "U.S. Census Bureau 2023 ZCTA gazetteer (%s): ZIP -> [lat, lon, land area km2]" % URL,
               "zips": dict(sorted(out.items()))}, open(P("data", "zip_centers.json"), "w"), indent=0)
    print("wrote data/zip_centers.json: %d of %d region ZIP codes (the rest are PO-box ZIP codes without an area)" % (len(out), len(want)))

if __name__ == "__main__":
    main()
