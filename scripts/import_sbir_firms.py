#!/usr/bin/env python3
"""Add company files for SBIR/STTR firms in the region that are not on the map yet.

    python3 scripts/pull_sbir.py          # first: refreshes data/sbir.json
    python3 scripts/import_sbir_firms.py  # then: writes companies/<firm>.toml for new firms

Only public facts from SBIR.gov's award data go into the files: company name, the address on its
latest award, website, the headcount it reported on that award, its UEI, and a summary of its
awards. The address is geocoded with OpenStreetMap; when that fails, the firm is placed at its city's
center (`location_precision = "city"`). Firms whose last award is older than 2012 are skipped as
likely inactive. Existing files are never overwritten.
"""
import datetime, json, os, re, time, urllib.parse, urllib.request
from common import P, companies, norm
from geocode import geocode

SINCE = "2012"
UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
SECTOR_RULES = [   # stems matched at word starts in the firm name and award titles; the sector with the most hits wins
    ("Medical devices & other", r"\b(medic|clinic|patient|surgic|implant|ortho|brace|prosthe|therap|diagnos|cancer|disease|health|drug|vaccin|biomed|bioprint|cell|tissue|wound|pain|neuro|cardi|dental|infant|incubat|hospital|addict|rehab|veterin|pharma|antibod|biocred|gene|genom)"),
    ("Electronics", r"\b(sensor|electron|circuit|rf\b|radio|antenna|laser|optic|photon|semiconduct|detector|radar|imag|camera|battery|microwave|wireless|signal|spectro|lidar|light)"),
    ("Materials & composites", r"\b(material|composit|polymer|coating|ceramic|alloy|nano|fiber|film|membrane|catalys|chemic|resin|graphene|chrome|corrosi|adhesive|foam|metal)"),
    ("Mechatronics & automation", r"\b(robot|autonom|vehicle|drone|uav|engine|actuator|motor|manufactur|machin|propulsion|turbine|tire|inspect|variation|assembl|weld|aircraft)"),
    ("Software & services", r"\b(software|data\b|machine learning|artificial intell|generative|\bai\b|cyber|blockchain|cloud|analytic|platform|app\b|education|training|simulat|algorithm|predict)"),
    ("Food & consumer goods", r"\b(food|agricult|crop|soil|feed|dairy|nutri|clean|textile|apparel)"),
]

def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")

def titlecase(s):
    words = []
    for w in s.split():
        u = w.upper().strip(".,")
        if u in {"LLC", "L.L.C", "INC", "CORP", "CO", "LTD", "USA", "LP"}:
            words.append({"LLC": "LLC", "L.L.C": "LLC", "INC": "Inc.", "CORP": "Corp.", "CO": "Co.", "LTD": "Ltd.", "USA": "USA", "LP": "LP"}[u] + ("," if w.endswith(",") else ""))
        elif w.isupper() and len(w) <= 4 and not any(ch in w for ch in ".,&"):
            words.append(w)                      # short acronyms such as GSI, IRIS
        else:
            words.append(w[:1].upper() + w[1:].lower() if w.isupper() or w.islower() else w)
    return " ".join(words)

def sector_for(firm, titles):
    text = (firm + " " + " ".join(titles)).lower()
    scores = [(len(re.findall(rx, text)), i, name) for i, (name, rx) in enumerate(SECTOR_RULES)]
    best = max(scores, key=lambda t: (t[0], -t[1]))
    return best[2] if best[0] else "Software & services"

def city_coords(city, state, cache):
    key = "%s, %s" % (city, state)
    if key in cache:
        return cache[key]
    q = urllib.parse.urlencode({"city": city, "state": {"IN": "Indiana", "MI": "Michigan"}[state], "country": "USA", "format": "json", "limit": 1})
    with urllib.request.urlopen(urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q, headers=UA), timeout=30) as r:
        hit = json.load(r)
    time.sleep(1.1)
    cache[key] = [round(float(hit[0]["lat"]), 5), round(float(hit[0]["lon"]), 5)] if hit else None
    return cache[key]

def q(s):
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')

def main():
    data = json.load(open(P("data", "sbir.json")))
    cs = companies(); names = {norm(c["name"]) for c in cs}; ueis = {c.get("uei") for c in cs if c.get("uei")}
    cache_path = P("data", "city_coords.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    written = skipped = 0
    for f in data.get("firms_not_in_map", []):
        if str(f.get("last_year") or "") < SINCE or norm(f["firm"]) in names or (f.get("uei") and f["uei"] in ueis):
            skipped += 1; continue
        name = titlecase(f["firm"]); fname = "%s.toml" % slug(name)
        if os.path.exists(P("companies", fname)):
            skipped += 1; continue
        ll, prec = None, "city"
        if f.get("address"):
            try:
                ll = geocode(f["address"]); time.sleep(1.1)
            except Exception:
                ll = None
            if ll:
                ll, prec = [round(ll[0], 5), round(ll[1], 5)], "address"
        if not ll:
            ll = city_coords(f["city"], f["state"], cache)
        if not ll:
            print("no coordinates for", f["city"], f["state"]); continue
        sector = sector_for(f["firm"], f.get("titles", []))
        agencies = ", ".join(f.get("agencies", [])[:3])
        years = "%s" % f["first_year"] if f["first_year"] == f["last_year"] else "%s to %s" % (f["first_year"], f["last_year"])
        desc = "SBIR/STTR awardee: %d award%s from %s, %s. Most recent: %s." % (f["count"], "" if f["count"] == 1 else "s", agencies, years, (f.get("titles") or [""])[0].rstrip("."))
        site = f.get("website") or ""
        if site and not site.startswith("http"):
            site = "https://" + site.lower().lstrip("/")
        lines = ["# %s" % name, "# Imported from SBIR.gov award data (public); the address is the one on the firm's latest award.", "",
                 "name = %s" % q(name), 'kind = "company"', "city = %s" % q(f["city"]), "state = %s" % q(f["state"])]
        if f.get("address"):
            lines.append("address = %s" % q(f["address"]))
        lines += ["lat = %.5f" % ll[0], "lon = %.5f" % ll[1]]
        if prec == "city":
            lines.append('location_precision = "city"')
        if site:
            lines.append("website = %s" % q(site))
        if f.get("uei"):
            lines.append("uei = %s" % q(f["uei"]))
        lines += ["", "sector = %s" % q(sector), 'products = ["SBIR/STTR research and development"]', ""]
        if f.get("staff"):
            lines += ["employees = %d" % f["staff"], 'employees_scope = "company"', "employees_year = %s" % f["staff_year"], 'employees_quality = "reported"',
                      "employees_note = %s" % q("reported by the firm on its %s SBIR/STTR award" % f["staff_year"])]
        lines += ["", "description = %s" % q(desc), "", 'source = "SBIR.gov award data"', "updated = %s" % q(datetime.date.today().isoformat()), ""]
        with open(P("companies", fname), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        names.add(norm(f["firm"])); written += 1
    json.dump(cache, open(cache_path, "w"), indent=0, sort_keys=True)
    print("wrote %d SBIR firms; skipped %d (inactive since before %s, or already on the map)" % (written, skipped, SINCE))

if __name__ == "__main__":
    main()
