#!/usr/bin/env python3
"""Official titles of the manufacturing NAICS codes (31-33), for company files whose OSHA filing gives
no usable industry text. Run once; the result is committed.

    python3 scripts/make_naics_titles.py [2-6 digit_2022_Codes.xlsx]   # default: download it

Reads the Census Bureau's 2022 NAICS code list (census.gov, public, no key) with the standard
library (an .xlsx file is a zip of XML) and writes code -> title for codes starting 31, 32 or 33
to data/naics_titles.json. OSHA filers type their own industry text; when it says only
"Manufacturing", "Retail" or the code itself, scripts/import_osha.py uses the official title instead.
"""
import io, json, re, sys, urllib.request, zipfile
import xml.etree.ElementTree as ET
from common import P

URL = "https://www.census.gov/naics/2022NAICS/2-6%20digit_2022_Codes.xlsx"
UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def rows(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    for row in sheet.iter("{%s}row" % NS["m"]):
        out = {}
        for cell in row.findall("m:c", NS):
            col = re.match(r"[A-Z]+", cell.get("r"))[0]
            v = cell.find("m:v", NS)
            if v is None:
                t = cell.find("m:is/m:t", NS)
                out[col] = t.text if t is not None else ""
            else:
                out[col] = shared[int(v.text)] if cell.get("t") == "s" else v.text
        yield out

def main():
    data = open(sys.argv[1], "rb").read() if len(sys.argv) > 1 else urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=120).read()
    titles = {}
    for r in rows(data):
        code, title = str(r.get("B", "")).strip().split(".")[0], (r.get("C") or "").strip()
        if re.fullmatch(r"3[1-3]\d{1,4}", code) and title:
            titles[code] = re.sub(r"T$", "", title).strip()   # the list marks some titles with a trailing T
    json.dump({"source": "U.S. Census Bureau, 2022 NAICS codes (%s)" % URL, "titles": dict(sorted(titles.items()))},
              open(P("data", "naics_titles.json"), "w"), indent=0)
    print("wrote data/naics_titles.json: %d manufacturing codes" % len(titles))

if __name__ == "__main__":
    main()
