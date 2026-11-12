#!/usr/bin/env python3
"""Build docs/ (the published site) from companies/*.toml, data/ and site/.

    python3 scripts/build.py

Reads every company file, checks it, and writes docs/index.html (the page, with the Notre
Dame theme chrome from site/partials/), docs/data.js (everything the map needs) and copies
site/app.js and site/app.css. The GitHub Action runs the same command on every push.
Needs Python 3.11 or newer (for tomllib); nothing else.
"""
import datetime, json, os, sys, tomllib, shutil, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
BASE = "https://nd-pair.github.io/michiana-manufacturing/"
NAV = [("index.html", "Map"), ("https://github.com/nd-pair/michiana-manufacturing#adding-a-company", "Add a company"),
       ("https://nd-pair.github.io/web/", "PAIR")]

def read(*a):
    with open(P(*a), encoding="utf-8") as fh:
        return fh.read()

def load_toml(path):
    with open(path, "rb") as fh:
        return tomllib.load(fh)

def nav_html(mobile=False, fixed=False):
    out = []
    for i, (href, label) in enumerate(NAV):
        active = href == "index.html"
        a = '<a href="%s"%s>%s</a>' % (href, ' aria-current="page"' if active else "", label)
        if fixed:
            out.append('            <li id="primary_fixed_%d"%s>%s</li>' % (i, ' class="active"' if active else "", a))
        elif mobile:
            cls = (["first"] if i == 0 else []) + (["last"] if i == len(NAV) - 1 else []) + (["active"] if active else [])
            out.append('        <li%s>%s</li>' % (' class="%s"' % " ".join(cls) if cls else "", a))
        else:
            out.append('              <li%s>%s</li>' % (' class="active"' if active else "", a))
    return "\n".join(out)

def check(c, path, sectors):
    problems = []
    for k in ("name", "city", "state", "sector", "products"):
        if not c.get(k):
            problems.append("missing %s" % k)
    if c.get("sector") and c["sector"] not in sectors:
        problems.append("sector %r is not in data/sectors.toml (%s)" % (c["sector"], ", ".join(sectors)))
    if ("lat" in c) != ("lon" in c):
        problems.append("lat and lon must both be given, or neither")
    if c.get("employees") is not None and not isinstance(c["employees"], int):
        problems.append("employees must be a whole number")
    if c.get("employees_scope") not in (None, "site", "company"):
        problems.append("employees_scope must be \"site\" or \"company\"")
    if problems:
        sys.exit("%s: %s" % (os.path.relpath(path, ROOT), "; ".join(problems)))

def main():
    sectors_t = load_toml(P("data", "sectors.toml"))["sector"]
    sectors = [s["name"] for s in sectors_t]
    places = load_toml(P("data", "places.toml"))
    cities = {c["name"]: (c["lat"], c["lon"]) for c in places["city"]}

    companies = []
    for name in sorted(os.listdir(P("companies"))):
        if not name.endswith(".toml"):
            continue
        path = P("companies", name)
        c = load_toml(path)
        check(c, path, sectors)
        cid = re.sub(r"[^a-z0-9]+", "-", name[:-5].lower()).strip("-")
        if "lat" in c:
            lat, lon, prec = float(c["lat"]), float(c["lon"]), "address"
        else:
            if c["city"] not in cities:
                sys.exit("%s: no lat/lon, and city %r is not in data/places.toml; add lat/lon (scripts/geocode.py) or the city"
                         % (name, c["city"]))
            lat, lon = cities[c["city"]]; prec = "city"
        companies.append({
            "id": cid, "name": c["name"], "kind": c.get("kind", "company"), "city": c["city"], "state": c["state"],
            "addr": c.get("address", ""), "website": c.get("website", ""), "lat": lat, "lon": lon, "prec": prec,
            "sector": c["sector"], "tags": list(c["products"]), "emp": c.get("employees") or None,
            "emp_scope": c.get("employees_scope", "site"), "emp_note": c.get("employees_note", ""),
            "blurb": c.get("description", ""),
        })
    # spread companies that share one address in a small ring (in degrees)
    import math
    from collections import defaultdict
    grp = defaultdict(list)
    for o in companies:
        grp[(round(o["lat"], 4), round(o["lon"], 4))].append(o)
    for k, os_ in grp.items():
        if len(os_) > 1:
            for i, o in enumerate(os_):
                a = 2 * math.pi * i / len(os_)
                o["lat"] = round(o["lat"] + 0.0045 * math.sin(a), 5); o["lon"] = round(o["lon"] + 0.006 * math.cos(a), 5)

    counties = json.load(open(P("data", "region_counties.json")))
    lakes = [o["ring"] for o in json.load(open(P("data", "great_lakes.json"))) if len(o["ring"]) >= 80 and "Cabonga" not in o["name"]]
    data = {
        "companies": companies,
        "sectors": sectors, "sectorColors": {s["name"]: s["color"] for s in sectors_t},
        "counties": [{"name": c["name"], "state": c["state"], "core": c["core"],
                      "rings": [[[p[1], p[0]] for p in ring] for ring in c["rings"]]} for c in counties],
        "lakes": lakes,
        "cities": cities,
        "metros": {m["name"]: [m["lat"], m["lon"], bool(m.get("major"))] for m in places["metro"]},
        "states": {s["name"]: [s["lat"], s["lon"]] for s in places["state"]},
        "center": [places["view"]["center_lat"], places["view"]["center_lon"]],
        "landmark": {"name": places["view"]["landmark_name"], "lat": places["view"]["landmark_lat"], "lon": places["view"]["landmark_lon"]},
        "built": datetime.date.today().isoformat(),
    }
    os.makedirs(P("docs"), exist_ok=True)
    with open(P("docs", "data.js"), "w", encoding="utf-8") as fh:
        fh.write("window.MM_DATA=" + json.dumps(data, separators=(",", ":")) + ";\n")
    shutil.copy(P("site", "app.js"), P("docs", "app.js"))
    shutil.copy(P("site", "app.css"), P("docs", "app.css"))

    title = "Michiana Manufacturing"
    desc = ("The manufacturing and technology companies of the South Bend–Elkhart region on one map: "
            "%d companies, by sector, product and headcount." % len(companies))
    page = (read("site", "partials", "head.html").replace("{{TITLE}}", title).replace("{{DESCRIPTION}}", desc).replace("{{CANONICAL}}", BASE)
            + read("site", "partials", "sprite.svg").strip() + "\n"
            + read("site", "partials", "skiplinks.html").strip() + "\n"
            + '<div class="wrapper page--full-width nav-top--false" id="wrapper">\n'
            + read("site", "partials", "header.html").replace("{{NAV}}", nav_html()).replace("{{NAVFIXED}}", nav_html(fixed=True)) + "\n"
            + read("site", "page.html").strip() + "\n"
            + read("site", "partials", "footer.html").replace("{{YEAR}}", str(datetime.date.today().year)) + "\n"
            + "</div><!-- .wrapper -->\n"
            + read("site", "partials", "globalmenu.html").replace("{{MOBILENAV}}", nav_html(mobile=True)) + "\n"
            + read("site", "partials", "tail.html"))
    with open(P("docs", "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    open(P("docs", ".nojekyll"), "w").close()
    print("built docs/ with %d companies (%d at street-address precision, %d with a headcount)"
          % (len(companies), sum(1 for c in companies if c["prec"] == "address"), sum(1 for c in companies if c["emp"])))

if __name__ == "__main__":
    main()
