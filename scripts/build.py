#!/usr/bin/env python3
"""Build docs/ (the published site) from companies/*.toml, data/ and site/.

    python3 scripts/build.py

Reads every company file, checks it, and writes docs/index.html (the map), docs/about.html (sources
and methods), docs/brief.html (printable sector briefs), all framed in the Notre Dame web theme from
site/partials/, plus docs/data.js (everything the pages need) and the scripts and stylesheet from
site/. The GitHub Action runs the same command on every push.
Needs Python 3.11 or newer (for tomllib); nothing else.
"""
import datetime, json, os, sys, tomllib, shutil, re, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
BASE = "https://nd-pair.github.io/michiana-manufacturing/"
NAV = [("index.html", "Map"), ("about.html", "About the data"), ("https://nd-pair.github.io/web/", "PAIR")]
GENERIC_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "aol.com", "outlook.com", "facebook.com", "linkedin.com", "comcast.net", "att.net", "sbcglobal.net", "msn.com", "google.com", "sites.google.com"}

def read(*a):
    with open(P(*a), encoding="utf-8") as fh:
        return fh.read()

def load_toml(path):
    with open(path, "rb") as fh:
        return tomllib.load(fh)

def nav_html(current, mobile=False, fixed=False):
    out = []
    for i, (href, label) in enumerate(NAV):
        active = href == current
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
    if c.get("employees_quality") not in (None, "reported", "estimate"):
        problems.append("employees_quality must be \"reported\" or \"estimate\"")
    if c.get("location_precision") not in (None, "address", "city"):
        problems.append("location_precision must be \"address\" or \"city\"")
    if problems:
        sys.exit("%s: %s" % (os.path.relpath(path, ROOT), "; ".join(problems)))

def headcount_year(note):
    years = re.findall(r"\b(19[89]\d|20[0-3]\d)\b", note or "")
    return max(years) if years else ""

def headcount_quality(c):
    if not c.get("employees"):
        return ""
    note = (c.get("employees_note") or "").lower()
    return "estimate" if re.search(r"estimate|aggregator|range|approx|about|planned", note) else "reported"

def domain(u):
    u = (u or "").lower().strip()
    for pfx in ("https://", "http://", "www."):
        if u.startswith(pfx):
            u = u[len(pfx):]
    return u.split("/")[0]

LEGAL_PART = re.compile(r"^(inc|incorporated|llc|l\.?l\.?c|corp|corporation|co|company|ltd|lp|llp)\.?$", re.I)
LEGAL = re.compile(r"[,\s]+(inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|lp|llp)\.?$", re.I)

def base_name(name):
    """The company name without plant, division or site qualifiers: 'Skyline Corp., Bristol Div.' -> 'Skyline Corp.',
    'Lippert Components, Inc., Plt. 37' -> 'Lippert Components, Inc.', 'Damon Corp. (HQ)' -> 'Damon Corp.'."""
    name = re.sub(r"\s*\(hq\)\s*", " ", name, flags=re.I).strip()
    parts = [p.strip() for p in name.split(",") if p.strip()]
    keep = parts[:1]
    for p in parts[1:]:
        if not LEGAL_PART.match(p):
            break
        keep.append(p)
    return ", ".join(keep) if keep else name

def group_key(name):
    b = LEGAL.sub("", LEGAL.sub("", base_name(name))).lower()
    return re.sub(r"[^a-z0-9]+", " ", b).strip()

def assign_groups(companies):
    """Plants of one company share a group: explicit `parent` first, then a shared website domain, then the same base name."""
    from collections import defaultdict
    by_parent, by_dom, by_base = defaultdict(list), defaultdict(list), defaultdict(list)
    for o in companies:
        if o["parent_field"]:
            by_parent[o["parent_field"]].append(o)
        d = domain(o["website"])
        if d and d not in GENERIC_DOMAINS and not o["standalone"]:
            by_dom[d].append(o)
        by_base[group_key(o["name"])].append(o)
    for o in companies:
        o["group"], o["parent"] = o["id"], ""
    from collections import Counter
    def label_for(ms):
        hq = [o for o in ms if re.search(r"\(hq\)", o["name"], re.I)]
        if hq:
            return base_name(hq[0]["name"])
        common = Counter(base_name(o["name"]) for o in ms).most_common()
        return common[0][0] if common[0][1] > 1 else min((base_name(o["name"]) for o in ms), key=len)
    def tie(members, label):
        gid = "g-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        for o in members:
            if o["group"] == o["id"]:
                o["group"], o["parent"] = gid, label
    for label, ms in by_parent.items():
        tie(ms, label)
    for d, ms in by_dom.items():
        if len(ms) > 1:
            tie(ms, label_for(ms))
    for k, ms in by_base.items():
        ms = [o for o in ms if not o["standalone"]]
        if k and len(ms) > 1:
            tie(ms, label_for(ms))
    for o in companies:          # a group of one is not a group
        pass
    from collections import Counter
    sizes = Counter(o["group"] for o in companies)
    for o in companies:
        if sizes[o["group"]] == 1:
            o["group"], o["parent"] = o["id"], ""
        o.pop("parent_field", None); o.pop("standalone", None)

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
            lat, lon, prec = float(c["lat"]), float(c["lon"]), c.get("location_precision", "address")
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
            "blurb": c.get("description", ""), "naics": str(c.get("naics", "")), "certs": list(c.get("certifications", [])),
            "source": c.get("source", "company website, filings, press and directories"), "updated": str(c.get("updated", "")),
            "uei": c.get("uei", ""), "parent_field": c.get("parent", ""), "standalone": bool(c.get("standalone")),
            "emp_year": str(c.get("employees_year") or headcount_year(c.get("employees_note", ""))),
            "emp_quality": c.get("employees_quality") or headcount_quality(c),
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

    assign_groups(companies)
    # sidecar datasets produced by the pull scripts (optional; the build works without them)
    def sidecar(name):
        try:
            return json.load(open(P("data", name)))
        except FileNotFoundError:
            return {"companies": {}}
    federal, fda, qcew, sbir, patents = sidecar("federal.json"), sidecar("fda.json"), sidecar("qcew.json"), sidecar("sbir.json"), sidecar("patents.json")
    for o in companies:
        f = federal["companies"].get(o["id"]); o["federal"] = {"contracts": f["contracts"], "grants": f["grants"], "total": f["total"]} if f else None
        sb = sbir["companies"].get(o["id"]); o["sbir"] = {"count": sb["count"], "amount": sb["amount"], "agencies": sb.get("agencies", [])} if sb else None
        pt = patents["companies"].get(o["id"]); o["patents"] = {"count": pt["count"], "latest": pt.get("latest", [])} if pt else None
        d = fda["companies"].get(o["id"])
        if d:
            o["certs"] = o["certs"] + ["FDA registered device establishment"]
            o["fda"] = {"fei": d.get("fei"), "types": d.get("establishment_types", []), "devices": d.get("device_names", [])}
    # process capabilities from NAICS prefixes and product keywords
    caps = load_toml(P("data", "capabilities.toml"))["capability"]
    for o in companies:
        text = " ".join(o["tags"] + [o["blurb"]]).lower()
        o["caps"] = [k["name"] for k in caps if any(o["naics"].startswith(pfx) for pfx in k["naics"]) or any(kw in text for kw in k["keywords"])]
    try:
        events = json.load(open(P("data", "events_auto.json")))["events"]
    except FileNotFoundError:
        events = []
    events += patents.get("events", [])
    ids_now = {o["id"] for o in companies}
    events = sorted((e for e in events if not e.get("company") or e["company"] in ids_now), key=lambda e: e["date"], reverse=True)
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
        "capabilities": [k["name"] for k in caps],
        "events": events,
        "federalAgencies": federal.get("agencies", []), "federalSource": federal.get("source", ""), "federalPulled": federal.get("pulled", ""),
        "fdaSource": fda.get("source", ""), "qcew": qcew.get("counties", {}), "qcewSource": qcew.get("source", ""),
        "qcewSectors": qcew.get("sectors", {}), "qcewPulled": qcew.get("pulled", ""),
        "sbirPulled": sbir.get("pulled", ""), "fdaPulled": fda.get("pulled", ""), "patentsPulled": patents.get("pulled", ""),
    }
    # a content hash in the asset URLs, so browsers and the Pages CDN never serve a stale script with a new page
    stamp = hashlib.sha1((json.dumps(data, sort_keys=True) + "".join(read("site", f) for f in ("app.js", "app.css", "brief.js"))).encode()).hexdigest()[:10]
    os.makedirs(P("docs"), exist_ok=True)
    with open(P("docs", "data.js"), "w", encoding="utf-8") as fh:
        fh.write("window.MM_DATA=" + json.dumps(data, separators=(",", ":")) + ";\n")
    for f in ("app.js", "app.css", "brief.js"):
        shutil.copy(P("site", f), P("docs", f))

    def page(fname, title, desc, body, scripts):
        html = (read("site", "partials", "head.html").replace("{{TITLE}}", title).replace("{{DESCRIPTION}}", desc)
                .replace("{{CANONICAL}}", BASE + ("" if fname == "index.html" else fname)).replace("{{BUILD}}", stamp)
                + read("site", "partials", "sprite.svg").strip() + "\n"
                + read("site", "partials", "skiplinks.html").strip() + "\n"
                + '<div class="wrapper page--full-width nav-top--false" id="wrapper">\n'
                + read("site", "partials", "header.html").replace("{{NAV}}", nav_html(fname)).replace("{{NAVFIXED}}", nav_html(fname, fixed=True)) + "\n"
                + body.strip() + "\n"
                + read("site", "partials", "footer.html").replace("{{YEAR}}", str(datetime.date.today().year)) + "\n"
                + "</div><!-- .wrapper -->\n"
                + read("site", "partials", "globalmenu.html").replace("{{MOBILENAV}}", nav_html(fname, mobile=True)) + "\n"
                + read("site", "partials", "tail.html").replace("{{SCRIPTS}}", scripts).replace("{{BUILD}}", stamp))
        with open(P("docs", fname), "w", encoding="utf-8") as fh:
            fh.write(html)

    n_groups = len({o["group"] for o in companies})
    title = "Michiana Manufacturing"
    desc = ("The manufacturing and technology companies of the South Bend–Elkhart region on one map: "
            "%d companies at %d sites, by sector, product and headcount." % (n_groups, len(companies)))
    three = '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n'
    page("index.html", title, desc, read("site", "page.html"), three + '<script src="data.js?v={{BUILD}}"></script>\n<script src="app.js?v={{BUILD}}"></script>')
    src_counts = {"hifld": sum(1 for o in companies if o["source"].startswith("HIFLD")), "sbir": sum(1 for o in companies if o["source"].startswith("SBIR"))}
    src_counts["hand"] = len(companies) - src_counts["hifld"] - src_counts["sbir"]
    qyears = sorted({y for d in qcew.get("counties", {}).values() for y in d.get("years", {})})
    fill = {"{{SITES}}": "{:,}".format(len(companies)), "{{COMPANIES}}": "{:,}".format(n_groups), "{{HIFLD}}": "{:,}".format(src_counts["hifld"]),
            "{{SBIRFIRMS}}": str(src_counts["sbir"]), "{{HAND}}": str(src_counts["hand"]), "{{BUILT}}": data["built"],
            "{{UEI}}": str(sum(1 for o in companies if o["uei"])), "{{FEDN}}": str(sum(1 for o in companies if o.get("federal"))),
            "{{FEDPULLED}}": federal.get("pulled", "not yet pulled"), "{{SBIRN}}": str(sum(1 for o in companies if o.get("sbir"))),
            "{{SBIRPULLED}}": sbir.get("pulled", "not yet pulled"), "{{FDAN}}": str(sum(1 for o in companies if o.get("fda"))),
            "{{FDAPULLED}}": fda.get("pulled", "not yet pulled"), "{{QCEWYEARS}}": ("%s–%s" % (qyears[0], qyears[-1])) if qyears else "none",
            "{{QCEWPULLED}}": qcew.get("pulled", "not yet pulled"), "{{EVENTS}}": "{:,}".format(len(events)),
            "{{PATENTS}}": ("%d companies, pulled %s" % (sum(1 for o in companies if o.get("patents")), patents.get("pulled"))) if patents.get("pulled") else "not yet available (needs a PatentsView API key)",
            "{{CITYLEVEL}}": str(sum(1 for o in companies if o["prec"] == "city")), "{{GROUPED}}": str(sum(1 for o in companies if o["parent"])),
            "{{PARENTS}}": str(len({o["group"] for o in companies if o["parent"]}))}
    about = read("site", "about.html")
    for k, v in fill.items():
        about = about.replace(k, v)
    page("about.html", "About the data", "Sources, methods and known gaps behind the Michiana Manufacturing map.", about, "")
    page("brief.html", "Sector brief", "Printable one-page summaries of each manufacturing sector in the South Bend–Elkhart region.",
         read("site", "brief.html"), '<script src="data.js?v={{BUILD}}"></script>\n<script src="brief.js?v={{BUILD}}"></script>')
    open(P("docs", ".nojekyll"), "w").close()
    print("built docs/ with %d sites of %d companies (%d at street-address precision, %d with a headcount, %d with a UEI, %d with federal awards, %d with SBIR, %d FDA-registered, %d in multi-site groups, %d events)"
          % (len(companies), n_groups, sum(1 for c in companies if c["prec"] == "address"), sum(1 for c in companies if c["emp"]), sum(1 for c in companies if c["uei"]),
             sum(1 for c in companies if c.get("federal")), sum(1 for c in companies if c.get("sbir")), sum(1 for c in companies if c.get("fda")),
             sum(1 for c in companies if c["parent"]), len(events)))

if __name__ == "__main__":
    main()
