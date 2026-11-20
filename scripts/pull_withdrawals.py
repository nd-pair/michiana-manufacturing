#!/usr/bin/env python3
"""Industrial water withdrawals in the region's Indiana counties, from the Indiana DNR's Significant Water
Withdrawal Facility data (facilities able to withdraw 100,000 gallons a day or more; no key). Writes
data/withdrawals.json, shown in the Materials & recovery tab (Aqueous) and on company cards.

    python3 scripts/pull_withdrawals.py
    python3 scripts/pull_withdrawals.py --rematch   # only match the saved facilities to company files again

The statewide file holds two tables: Fac (every registered well and surface intake, with its capacity and
UTM location) and WU (the yearly and monthly volume each one reported, in thousands of gallons, for the
last three years). Only facilities whose primary use is industry (MWU code IN) are kept. Withdrawals are
water taken in, not wastewater, but for a plant without a discharge permit most of it leaves through the
sewer. Michigan publishes the same kind of data, but its site refuses automated requests.

Each facility is matched to the nearest company file on the map within 3 km whose name shares a
distinctive word (the facility list has no street address), or by hand in data/waste_matches.toml
(epa_id "INDNR-<county number>-<registration number>").
"""
import datetime, io, json, math, sys, tomllib, urllib.parse, urllib.request, zipfile
import xlrd
from common import P, companies, norm
from pull_waste import UA, GENERIC

URL = "https://www.in.gov/dnr/static/water/swwf/IN-SWWF.zip"
# the same facilities on IndianaMap, with points in WGS84 (the spreadsheet's UTM coordinates sit about 200 m south
# of these, as NAD27 would; they are used only for a facility missing here)
LAYER = "https://gisdata.in.gov/server/rest/services/Hosted/SWWF/FeatureServer/1/query"
# DNR county numbers (alphabetical) -> FIPS, for the region's Indiana counties
COUNTY = {20: "18039", 25: "18049", 43: "18085", 44: "18087", 46: "18091", 50: "18099", 57: "18113", 71: "18141", 75: "18149", 92: "18183"}

def utm16_to_latlon(e, n):
    """UTM zone 16N (NAD83/WGS84) to latitude and longitude, by the standard series (well under a meter here)."""
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    e2 = f * (2 - f); ep2 = e2 / (1 - e2)
    x, y = e - 500000.0, n
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
         + (151 * e1 ** 3 / 96) * math.sin(6 * mu))
    c1, t1 = ep2 * math.cos(p) ** 2, math.tan(p) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(p) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(p) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = p - (n1 * math.tan(p) / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                         + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(p)
    return round(math.degrees(lat), 6), round(-87 + math.degrees(lon), 6)

def sheet(z, name):
    sh = xlrd.open_workbook(file_contents=z.read(next(n for n in z.namelist() if n.lower().endswith(name.lower())))).sheet_by_index(0)
    head = [str(x).strip() for x in sh.row_values(0)]
    return [dict(zip(head, sh.row_values(i))) for i in range(1, sh.nrows)]

def pull():
    z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=300).read()))
    fac = {}
    for r in sheet(z, "Fac.xls"):
        cn = int(r["County"] or 0)
        if cn not in COUNTY or r["MWU Code"] != "IN":
            continue
        k = "%d-%s" % (cn, r["RegNo"])
        f = fac.setdefault(k, {"id": k, "name": r["Facility"].strip(), "county": COUNTY[cn], "pts": [], "gpm": 0.0, "wells": 0, "intakes": 0, "water": set()})
        if r["UTM East"] and r["UTM North"]:
            f["pts"].append(utm16_to_latlon(float(r["UTM East"]), float(r["UTM North"])))
        f["gpm"] += float(r["Capacity (GPM)"] or 0)
        if r["Source Code"] == "WELL":
            f["wells"] += 1
        else:
            f["intakes"] += 1
            if r["Water Body"]:
                f["water"].add(r["Water Body"].strip().title())
    for r in sheet(z, "WU.xls"):
        k = "%d-%s" % (int(r["County"] or 0), r["RegNo"])
        if k in fac and r["Units"] == "TG":   # thousands of gallons
            y = fac[k].setdefault("years", {})
            y[str(r["Year"])] = y.get(str(r["Year"]), 0) + float(r["Annual"] or 0) * 1000
    try:
        q = urllib.parse.urlencode({"where": "mwucode='IN' AND county IN (%s)" % ",".join(str(c) for c in COUNTY), "outFields": "county,regno",
                                    "outSR": "4326", "f": "json"})
        pts = {"%d-%s" % (x["attributes"]["county"], x["attributes"]["regno"]): (round(x["geometry"]["y"], 6), round(x["geometry"]["x"], 6))
               for x in json.loads(urllib.request.urlopen(urllib.request.Request(LAYER + "?" + q, headers=UA), timeout=120).read())["features"]}
    except Exception:
        pts = {}
    out = []
    for f in fac.values():
        if f["id"] in pts:
            f["lat"], f["lon"] = pts[f["id"]]
        elif f["pts"]:
            f["lat"], f["lon"] = round(sum(p[0] for p in f["pts"]) / len(f["pts"]), 6), round(sum(p[1] for p in f["pts"]) / len(f["pts"]), 6)
        f.pop("pts")
        f["water"] = sorted(f["water"])
        f["gpm"] = round(f["gpm"])
        f["years"] = {y: round(v) for y, v in sorted(f.get("years", {}).items())}
        out.append(f)
    return out

def index():
    """match(facility) -> company id: a hand match, else the nearest open company file within 3 km whose name shares
    a distinctive word."""
    try:
        hand = {m["epa_id"]: m["file"] for m in tomllib.load(open(P("data", "waste_matches.toml"), "rb")).get("match", [])}
    except FileNotFoundError:
        hand = {}
    words = lambda s: {w for w in norm(s).split() if len(w) > 2} - GENERIC - {"inc", "incorporated", "llc", "corp", "corporation", "company", "the", "and", "plant"}
    pts = [(c["lat"], c["lon"], c["_id"], words(c["name"])) for c in companies()
           if "lat" in c and not any(c.get(x) for x in ("closed", "removed", "presumed_closed"))]
    def match(f):
        hk = "INDNR-" + f["id"]
        if hk in hand:
            return hand[hk] or None
        if "lat" not in f:
            return None
        w, best = words(f["name"]), None
        for la, lo, cid, cw in pts:
            d = math.hypot((la - f["lat"]) * 111000, (lo - f["lon"]) * 83000)
            if d < 3000 and w & cw and (best is None or d < best[0]):
                best = (d, cid)
        return best and best[1]
    return match

def main():
    path = P("data", "withdrawals.json")
    match = index()
    if "--rematch" in sys.argv:
        out = json.load(open(path))
        for f in out["facilities"]:
            f["company"] = match(f)
    else:
        fs = pull()
        for f in fs:
            f["company"] = match(f)
        fs.sort(key=lambda f: -max(f["years"].values() or [0]))
        out = {"facilities": fs, "pulled": datetime.date.today().isoformat(), "units": "gallons a year; capacity in gallons a minute",
               "source": "Indiana DNR Division of Water, Significant Water Withdrawal Facility data (IN-SWWF.zip)"}
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    fs = out["facilities"]
    print("wrote data/withdrawals.json: %d industrial facilities, %d matched to a company file, years %s"
          % (len(fs), sum(1 for f in fs if f["company"]), sorted({y for f in fs for y in f["years"]})))

if __name__ == "__main__":
    main()
