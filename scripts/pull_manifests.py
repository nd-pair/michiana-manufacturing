#!/usr/bin/env python3
"""Liquid waste shipped from the region on EPA's uniform hazardous waste manifests (e-Manifest; no key). Writes
data/manifests.json, shown in the Materials & recovery tab (Aqueous) and on company cards.

    python3 scripts/pull_manifests.py
    python3 scripts/pull_manifests.py --rematch   # only match the saved generators to company files again

Unlike the Biennial Report, which only large-quantity generators file every other year, a manifest goes with
every shipment of hazardous waste from any generator, and many shippers also manifest non-hazardous liquids.
EPA publishes them weekly as national bulk files (RCRAInfo public export, about 2 GB zipped); this script
streams the manifest and waste-line files to a temporary folder, keeps the latest full year's shipments from
generators at a ZIP code in the region (data/region_zips.json), and deletes the files.

A waste line counts as aqueous when its description names water (rinse, wash or mop water, coolant,
wastewater, aqueous parts-washer solution, leachate, emulsion; not water-reactive) or, for a liquid or
solution, an acid, caustic, plating, etching or passivation bath. Tons are EPA's own conversion of each
line's quantity. Generators are matched to company files like the EPA plants (scripts/pull_waste.py), by
their EPA ID first (hand matches in data/waste_matches.toml).
"""
import csv, datetime, io, json, os, re, shutil, sys, tempfile, urllib.request, zipfile
from common import P
from pull_waste import UA, company_index

INDEX = "https://rcrapublic.epa.gov/rcra-hwip/api/export/summaries"
WATER = re.compile(r"(?i)aqueous|rinse|coolant|wastewater|waste water|wash ?water|\bwater\b|leachate|emulsion|soluble oil|parts washer|floor scrubber")
NOT_WATER = re.compile(r"(?i)water[- ]reactive|dangerous when wet|in contact with water")
ACID = re.compile(r"(?i)\bacid|caustic|corrosive liquid|alkaline|hydroxide|pickl|plating|etch|passivat|anodiz")
LIQUID = re.compile(r"(?i)liquid|solution|bath|\bacid\b")
SOLID = re.compile(r"(?i)\bsolids?\b|debris|sludge|filter cake")

def kind(desc):
    """'water' (water-based), 'acid' (acids, caustics, plating and etching liquids) or None."""
    if WATER.search(desc) and not NOT_WATER.search(desc):
        return "water"
    if ACID.search(desc) and LIQUID.search(desc) and not SOLID.search(desc):
        return "acid"
    return None

def download(url, folder):
    path = os.path.join(folder, url.rsplit("/", 1)[1])
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(path, "wb") as fh:
        shutil.copyfileobj(r, fh, 1 << 22)
    return path

def rows(path):
    z = zipfile.ZipFile(path)
    for info in z.infolist():
        with z.open(info) as fh:
            yield from csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1"))

def pull(find):
    url = next(x["url"] for x in json.loads(urllib.request.urlopen(urllib.request.Request(INDEX, headers=UA), timeout=120).read())
               if x["fileName"] == "EM_MANIFEST.zip")
    zips = set(json.load(open(P("data", "region_zips.json")))["zips"])
    year = str(datetime.date.today().year - 1)
    num = lambda v: float(v) if v not in ("", None) else 0.0
    tmp = tempfile.mkdtemp()
    try:
        man = {}
        for r in rows(download(url, tmp)):
            if r["SHIPPED DATE"][:4] == year and r["GENERATOR LOCATION STATE"] in ("IN", "MI") and r["GENERATOR LOCATION ZIP"][:5] in zips:
                man[r["MANIFEST TRACKING NUMBER"]] = r
        os.remove(os.path.join(tmp, "EM_MANIFEST.zip"))
        gens = {}
        for r in rows(download(url.replace("EM_MANIFEST", "EM_WASTE_LINE"), tmp)):
            m = man.get(r["MANIFEST TRACKING NUMBER"])
            if not m:
                continue
            desc = " ".join(x for x in (r["DOT PRINTED INFORMATION"], r["NON HAZ WASTE DESCRIPTION"], r["DOT ID NUMBER DESCRIPTION"]) if x).strip()
            k = kind(desc)
            if not k:
                continue
            gid = m["GENERATOR ID"]
            g = gens.setdefault(gid, {"id": gid, "name": m["GENERATOR NAME"].strip(), "street": " ".join(x for x in (m["GENERATOR LOCATION STREET NO"], m["GENERATOR LOCATION STREET1"]) if x).strip(),
                                      "city": m["GENERATOR LOCATION CITY"].title(), "state": m["GENERATOR LOCATION STATE"], "zip": m["GENERATOR LOCATION ZIP"][:5],
                                      "water": 0.0, "acid": 0.0, "nonhaz": 0.0, "manifests": set(), "streams": {}, "to": {}})
            t = num(r["QUANTITY TONS"])
            g[k] += t
            if r["EPA WASTE"] == "N":
                g["nonhaz"] += t
            g["manifests"].add(r["MANIFEST TRACKING NUMBER"])
            s = g["streams"].setdefault(re.sub(r"\s+", " ", desc)[:120], [k, 0.0, r["EPA WASTE"] == "N"])
            s[1] += t
            rk = "%s, %s" % (m["DES FACILITY NAME"].strip().title(), m["DES FAC LOCATION STATE"])
            g["to"][rk] = g["to"].get(rk, 0) + t
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = []
    for g in gens.values():
        g.update(water=round(g["water"], 2), acid=round(g["acid"], 2), nonhaz=round(g["nonhaz"], 2), manifests=len(g["manifests"]),
                 streams=[[d, k, round(t, 2), nh] for d, (k, t, nh) in sorted(g["streams"].items(), key=lambda kv: -kv[1][1])[:4]],
                 to=[[n, round(t, 2)] for n, t in sorted(g["to"].items(), key=lambda kv: -kv[1])[:3]])
        g["company"] = find(g["name"], g["street"], g["city"], epa_id=g["id"])
        out.append(g)
    out.sort(key=lambda g: -(g["water"] + g["acid"]))
    return {"year": int(year), "generators": out}

def main():
    path = P("data", "manifests.json")
    find = company_index()
    if "--rematch" in sys.argv:
        out = json.load(open(path))
        for g in out["generators"]:
            g["company"] = find(g["name"], g["street"], g["city"], epa_id=g["id"])
    else:
        out = pull(find)
        out.update(pulled=datetime.date.today().isoformat(), units="tons shipped in the year (EPA's conversion of each waste line)",
                   source="U.S. EPA e-Manifest, RCRAInfo public export (EM_MANIFEST, EM_WASTE_LINE)")
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    G = out["generators"]
    print("wrote data/manifests.json: %d generators shipped aqueous waste in %d (%.0f t water-based, %.0f t acids and caustics); %d matched to a company file"
          % (len(G), out["year"], sum(g["water"] for g in G), sum(g["acid"] for g in G), sum(1 for g in G if g["company"])))

if __name__ == "__main__":
    main()
