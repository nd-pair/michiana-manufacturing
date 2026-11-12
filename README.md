# Michiana Manufacturing

An interactive map of the manufacturing and technology companies of the South Bend–Elkhart region,
by the [Physical AI and Robotics Initiative](https://nd-pair.github.io/web/) at the University of
Notre Dame.

**Live:** https://nd-pair.github.io/michiana-manufacturing/

Each company stands as a column at its street address on a true-scale globe. Column height is
headcount (log scale), color is the sector. Pan and zoom from the Chicago–Cleveland span down to
the Notre Dame campus; filter by sector or by what companies make; sort the side panels by number
of companies or by staff.

Only **public information** belongs in this repository: what a company says about itself on its
website, in filings, press and business directories, and public government datasets.

Most of the roughly 1,200 companies were imported from the U.S. Department of Homeland Security's
**HIFLD General Manufacturing Facilities** dataset (every NAICS 31–33 facility, with address,
product line, website and an employee estimate), as served by the Department of Energy's NETL
ArcGIS service. `python3 scripts/import_hifld.py` fetches the Michiana counties and writes one
file per facility; it never overwrites a file that exists, and a hand-written file for the same
company (same website domain or name) always wins. Imported files are ordinary files: edit them,
rename them, or delete them.

## Adding a company

A company is one short text file in [`companies/`](companies/). Copy the template below into a
new file named after the company (lowercase, hyphens, `.toml`), fill it in, and open a pull
request. The map rebuilds itself when the change is merged. You can do all of this in the
browser: open `companies/`, press **Add file → Create new file**.

```toml
name = "Acme Gear Works"
kind = "company"                 # or "university" for a university unit
city = "Elkhart"
state = "IN"
address = "123 Industrial Pkwy, Elkhart, IN 46516"
lat = 41.68570                   # optional; see "Positions" below
lon = -85.93470
website = "https://www.example.com"

sector = "Metal"                 # one of the names in data/sectors.toml
products = ["Gears & splines", "Precision machining"]

employees = 48                   # optional, whole number
employees_scope = "site"         # "site" = this location; "company" = company-wide
employees_note = "company website, 2026"

description = "One or two sentences on what the company makes, from its own public material."
```

Field by field:

| Field | Required | Notes |
| --- | --- | --- |
| `name`, `city`, `state` | yes | |
| `address` | no | Street address; used for the position and shown in the detail panel |
| `lat`, `lon` | no | Decimal degrees. Without them the column sits at the city center (the city must be in `data/places.toml`) |
| `website` | no | Public website |
| `sector` | yes | One of the ten sectors in [`data/sectors.toml`](data/sectors.toml); imported files get one from the facility's 3-digit NAICS code |
| `products` | yes | Free text, one or more. Reuse existing names where they fit so the product filter stays useful |
| `employees`, `employees_scope`, `employees_note` | no | Approximate is fine; say where the number comes from and whether it is this site or the whole company |
| `description` | no | Plain language, from public sources |

**Positions.** If you give an address but no `lat`/`lon`, run `python3 scripts/geocode.py` and it
looks the address up on OpenStreetMap and writes the coordinates into the file. Check the result
on the map.

**Sectors and labels.** Sectors and their colors live in `data/sectors.toml`; cities, reference
metros, state labels and the campus landmark in `data/places.toml`.

## Layers and panels

Beyond the map, the page carries:

- **Federal footprint.** Procurement contracts and grants since FY2016 for every company, from
  USAspending.gov, matched by recipient name, plus the region-wide totals by awarding agency.
  A filter shows only companies with federal awards. `scripts/pull_federal.py` → `data/federal.json`.
- **Certifications.** FDA medical-device establishment registrations from openFDA
  (`scripts/pull_fda.py` → `data/fda.json`), shown as a badge and a filter. Other certifications
  (AS9100, ISO 9001, Nadcap, CMMC) go in a company file as `certifications = ["AS9100", ...]`
  from the company's own public statements; the registries themselves are not open for bulk use.
- **SBIR/STTR awards.** SBIR.gov's API rejects scripts, so `scripts/pull_sbir.py` reads a CSV
  exported by hand from https://www.sbir.gov/awards (State = Indiana, then Michigan) and writes
  `data/sbir.json`; awards appear in the detail panel once that file exists.
- **Notre Dame network.** `data/collaborations.toml` lists public relationships (co-founded,
  investment, university unit, program) between the campus and companies, or between companies,
  each with its announcement as the source. The map draws them as arcs when the layer is on.
- **Capabilities.** `data/capabilities.toml` maps NAICS prefixes and product keywords to process
  capabilities (casting, machining, molding, circuit boards, ...). The panel counts companies per
  capability, names the largest site, flags capabilities with one or no company as a gap, and
  filters the map; with a sector or product filter active it becomes a gap analysis for that slice.
- **Manufacturing employment by county.** Annual private manufacturing employment from the BLS
  Quarterly Census of Employment and Wages (`scripts/pull_qcew.py` → `data/qcew.json`).
- **Timeline.** `data/events.toml`: openings, expansions, closures and funding events with a source;
  clicking one selects the company and flies to it.
- **Distance rings.** 25, 50 and 100 km from the campus, straight-line distance.
- **Provenance.** Every company carries `source` and `updated`; imported files say which dataset
  they came from. The detail panel shows both.
- **Sharing.** The URL hash holds the filters, layers and selection ("Copy link to this view"), and
  the roster downloads as CSV with every field.

## Keeping the data current

[`refresh-data.yml`](.github/workflows/refresh-data.yml) runs on the 2nd of every month (and on
demand from the Actions tab): it imports new HIFLD facilities, re-pulls USAspending, openFDA and
QCEW, geocodes any file with an address but no coordinates, rebuilds and commits. Each source is
optional, so an outage at one does not block the others. Hand-written files are never touched.

## Building locally

```bash
python3 scripts/build.py        # companies/ + data/ + site/ -> docs/
python3 -m http.server -d docs  # then open http://localhost:8000
```

Python 3.11 or newer, no other dependencies. GitHub Pages serves `docs/` on `main`; the
[workflow](.github/workflows/build.yml) rebuilds `docs/` on every push and commits the result,
so commit only your source changes (`companies/`, `data/`, `site/`, `scripts/`) and leave
`docs/` to the workflow; after it runs, `git pull --rebase` picks up its commit.

## Layout

```
companies/      one TOML file per company (edit these)
data/           sectors, places, capabilities, collaborations, events (edit these); county boundaries (Census), shorelines (Natural Earth); pulled datasets (federal, fda, qcew, sbir)
site/           the page: Notre Dame Web Theme chrome (partials/), page.html, app.js, app.css
scripts/        build.py, geocode.py, import_hifld.py, pull_federal.py, pull_fda.py, pull_qcew.py, pull_sbir.py, common.py
docs/           the built site (generated; do not edit by hand)
```

The page uses the University's web theme (NDT4) for its frame, as the PAIR site does, and
[three.js](https://threejs.org/) for the map.

## Sources and credits

Company descriptions, products and headcounts: the HIFLD General Manufacturing Facilities
dataset (U.S. DHS, public domain) for most entries, and the companies' own websites, public
filings, press and business directories for the rest; headcounts are approximate and dated.
Federal awards: USAspending.gov. Device registrations: openFDA. Employment: BLS QCEW. County boundaries: U.S.
Census Bureau cartographic boundary files. Shorelines: Natural Earth. Code: MIT license (see
LICENSE); company data is factual public information.
