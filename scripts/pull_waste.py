#!/usr/bin/env python3
"""Metal-bearing waste streams in the region, from two public EPA datasets (no key). Writes
data/waste.json, shown in the Waste streams panel and on company cards.

    python3 scripts/pull_waste.py
    python3 scripts/pull_waste.py --rematch   # only match the saved plants to company files again

- Toxics Release Inventory (TRI), basic data files for Indiana and Michigan, the latest year
  published: for every plant in the region's counties that reports a metal, the pounds of
  production-related waste and how they were managed (recycled on or off site, treated, burned for
  energy, or disposed of and released). TRI covers plants with 10 or more employees in listed
  industries that handle a listed chemical above a threshold; it does not list rare earths,
  lithium, gallium, germanium, tungsten, tantalum or titanium metal.
- RCRA Biennial Report (Envirofacts table br_reporting), the latest cycle: hazardous waste streams
  of large-quantity generators in the region that carry metals (EPA waste codes for plating
  sludge, steel-mill dust, pickle liquor and toxic metals, or a description naming a metal,
  batteries or catalysts), in tons, with how they were managed.
Each plant is matched to a company file by street address and city, then by name and city. Each
dataset is independent; one that fails keeps its part of the previous file.
"""
import csv, datetime, io, json, math, re, sys, urllib.request
from collections import defaultdict
from common import P, COUNTIES, companies, matcher, norm
from import_osha import addr_key, county_of

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
TRI = "https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/%d_%s/csv"
BR = "https://data.epa.gov/efservice/br_reporting/county_code/%s/report_cycle/%d/JSON"
ABBR = {"18": "IN", "26": "MI"}
# EPA hazardous waste codes whose streams carry recoverable metals
METAL_CODES = {
    "F006": "electroplating wastewater sludge", "F007": "spent plating bath (cyanide)", "F008": "plating bath residue (cyanide)",
    "F009": "spent stripping and cleaning bath (cyanide)", "F019": "aluminum conversion coating sludge",
    "K061": "electric arc furnace dust", "K062": "spent pickle liquor", "K069": "lead smelting emission sludge",
    "D004": "arsenic", "D005": "barium", "D006": "cadmium", "D007": "chromium", "D008": "lead", "D009": "mercury",
    "D010": "selenium", "D011": "silver"}
METAL_WORDS = re.compile(r"(?i)nickel|cobalt|chrom|carbide|tungsten|batter|lithium|zinc|copper|silver|\blead\b|catalyst|plating|"
                         r"precious|platinum|palladium|rhodium|tantal|titan|magnet|rare earth|mercury|cadmium|e-?waste|electronic|"
                         r"circuit|solder|baghouse|furnace dust|grinding swarf|metal fines|metal hydroxide")
GENERIC = set("indiana michigan hoosier north south east west american america plant plants products product systems system "
              "technologies technology industries industrial services service solutions metal metals building dept department "
              "division facility mfg manufacturing engineered elkhart goshen warsaw".split())
num = lambda v: float(v) if v not in (None, "") else 0.0

def get(url, timeout=300):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()

def company_index():
    cs = companies()
    by_addr = {}
    for c in cs:
        k = addr_key((c.get("address") or "").split(",")[0], c.get("city"))
        if k and not any(c.get(x) for x in ("closed", "removed")):
            by_addr.setdefault(k, c["_id"])
    match = matcher(cs)
    pts = [(c["lat"], c["lon"], c["_id"], set(norm(c["name"]).split())) for c in cs if "lat" in c and not any(c.get(x) for x in ("closed", "removed"))]
    def near(name, lat, lon):
        """The closest company file within 300 m whose name shares a distinctive word with this one."""
        words, best = set(norm(name).split()) - GENERIC, None
        for la, lo, cid, w in pts:
            d = math.hypot((la - lat) * 111000, (lo - lon) * 83000)
            if d < 300 and words & w:
                if best is None or d < best[0]:
                    best = (d, cid)
        return best and best[1]
    return lambda name, street, city, lat=None, lon=None: (by_addr.get(addr_key(street, city)) or match(name, city.title())
                                                         or (near(name, lat, lon) if lat is not None else None))

def metal_name(chem):
    """'Chromium compounds(except chromite ore ...)' -> 'Chromium'; 'Aluminum (fume or dust)' -> 'Aluminum'."""
    return re.split(r"[\s(,]", chem.strip())[0].title()

def tri(find):
    year = datetime.date.today().year - 1
    for year in range(year, year - 4, -1):
        try:
            files = {st: get(TRI % (year, st)).decode("latin-1") for st in ("IN", "MI")}
            if all(len(t) > 100000 for t in files.values()):
                break
        except Exception:
            continue
    else:
        raise RuntimeError("no TRI basic data file found")
    plants = {}
    col = lambda r, n: next(v for k, v in r.items() if k.split(". ", 1)[-1] == n)   # headers are numbered: "37. CHEMICAL"
    for st, text in files.items():
        for r in csv.DictReader(io.StringIO(text)):
            if col(r, "METAL") != "YES" or not col(r, "UNIT OF MEASURE").startswith("P"):
                continue
            try:
                lat, lon = float(col(r, "LATITUDE")), float(col(r, "LONGITUDE"))
            except ValueError:
                continue
            fips = county_of(lat, lon)
            if fips not in COUNTIES:
                continue
            fid = col(r, "TRIFD")
            p = plants.setdefault(fid, {"trifd": fid, "frs": col(r, "FRS ID"), "name": col(r, "FACILITY NAME"), "street": col(r, "STREET ADDRESS"),
                                        "city": col(r, "CITY").title(), "state": st, "zip": col(r, "ZIP")[:5], "county": fips, "lat": lat, "lon": lon,
                                        "naics": col(r, "PRIMARY NAICS"), "parent": col(r, "STANDARD PARENT CO NAME") or col(r, "PARENT CO NAME"), "metals": {}})
            recycled = num(col(r, "8.4 - RECYCLING ON SITE")) + num(col(r, "8.5 - RECYCLING OFF SIT"))
            energy = num(col(r, "8.2 - ENERGY RECOVER ON")) + num(col(r, "8.3 - ENERGY RECOVER OF"))
            treated = num(col(r, "8.6 - TREATMENT ON SITE")) + num(col(r, "8.7 - TREATMENT OFF SITE"))
            disposed = sum(num(col(r, k)) for k in ("8.1A - ON-SITE CONTAINED", "8.1B - ON-SITE OTHER", "8.1C - OFF-SITE CONTAIN", "8.1D - OFF-SITE OTHER R"))
            m = p["metals"].setdefault(metal_name(col(r, "CHEMICAL")), [0, 0, 0, 0])   # recycled, treated or burned, disposed or released, total
            for i, v in enumerate((recycled, treated + energy, disposed, recycled + treated + energy + disposed)):
                m[i] += v
    out = []
    for p in plants.values():
        p["metals"] = {k: [round(x) for x in v] for k, v in sorted(p["metals"].items()) if v[3] > 0}
        if p["metals"]:
            p["company"] = find(p["name"], p["street"], p["city"], p["lat"], p["lon"])
            out.append(p)
    out.sort(key=lambda p: -sum(v[3] for v in p["metals"].values()))
    return {"year": year, "units": "pounds a year; per metal: recycled, treated or burned for energy, disposed of or released, total",
            "facilities": out}

def rcra(find):
    cycle = datetime.date.today().year - 1
    cycle -= cycle % 2 == 0   # cycles are odd years
    for cycle in range(cycle, cycle - 6, -2):
        rows = []
        for f in COUNTIES:
            rows += json.loads(get(BR % (ABBR[f[:2]] + f[2:], cycle)))
        if len(rows) > 200:
            break
    else:
        raise RuntimeError("no Biennial Report cycle found")
    handlers = {}
    for r in rows:
        if r.get("br_form") != "GM" or num(r.get("generation_tons")) <= 0:
            continue
        codes = [c for c in re.split(r"[\s,]+", (r.get("federal_waste_codes") or "") + " " + (r.get("waste_code_group") or "")) if c]
        metal = sorted({c for c in codes if c in METAL_CODES})
        desc = (r.get("description") or "").strip()
        if not metal and not METAL_WORDS.search(desc):
            continue
        hid = r["handler_id"]
        street = " ".join(x for x in (r.get("location_street_no"), r.get("location_street1")) if x)
        h = handlers.setdefault(hid, {"id": hid, "name": r["handler_name"], "street": street, "city": (r.get("location_city") or "").title(),
                                      "state": r.get("location_state"), "zip": (r.get("location_zip") or "")[:5], "naics": r.get("primary_naics"),
                                      "county": {"IN": "18", "MI": "26"}.get(r.get("location_state"), "") + (r.get("county_code") or "")[2:], "streams": {}})
        key = (desc.lower(), tuple(metal))
        s = h["streams"].setdefault(key, {"description": desc, "codes": metal, "tons": 0.0, "managed": set()})
        s["tons"] += num(r.get("generation_tons"))
        if r.get("management_category"):
            s["managed"].add(r["management_category"].lower())
    out = []
    for h in handlers.values():
        h["streams"] = sorted(({**s, "tons": round(s["tons"], 2), "managed": sorted(s["managed"])} for s in h["streams"].values()), key=lambda s: -s["tons"])
        h["tons"] = round(sum(s["tons"] for s in h["streams"]), 2)
        h["company"] = find(h["name"], h["street"], h["city"])
        out.append(h)
    out.sort(key=lambda h: -h["tons"])
    return {"cycle": cycle, "units": "tons generated in the year", "codes": METAL_CODES, "handlers": out}

def main():
    path = P("data", "waste.json")
    try:
        out = json.load(open(path))
    except FileNotFoundError:
        out = {}
    find = company_index()
    if "--rematch" in sys.argv:
        for f in (out.get("tri") or {}).get("facilities", []):
            f["company"] = find(f["name"], f["street"], f["city"], f["lat"], f["lon"])
        for h in (out.get("rcra") or {}).get("handlers", []):
            h["company"] = find(h["name"], h["street"], h["city"])
        json.dump(out, open(path, "w"), indent=1, sort_keys=True)
        print("rematched: TRI %d, RCRA %d plants with a company file" % (sum(1 for f in out["tri"]["facilities"] if f["company"]),
                                                                       sum(1 for h in out["rcra"]["handlers"] if h["company"])))
        return
    ok = 0
    for name, fn in (("tri", tri), ("rcra", rcra)):
        try:
            out[name] = fn(find)
            ok += 1
            items = out[name].get("facilities") or out[name].get("handlers")
            print("%s: %d plants, %d matched to a company file" % (name, len(items), sum(1 for x in items if x.get("company"))))
        except Exception as e:
            print("%s: failed (%s); keeping the previous data" % (name, e))
    if not ok:
        raise SystemExit("no EPA dataset could be pulled")
    out["source"] = "U.S. EPA Toxics Release Inventory basic data files; RCRA Biennial Report (Envirofacts)"
    out["pulled"] = datetime.date.today().isoformat()
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    print("wrote data/waste.json")

if __name__ == "__main__":
    main()
