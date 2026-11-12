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
| `employees_year`, `employees_quality` | no | Year of the headcount and `"reported"` or `"estimate"`; shown with every figure |
| `parent` | no | Groups the plants of one company under this name (otherwise grouped by shared website or base name) |
| `standalone` | no | `true` keeps an entry out of automatic grouping, e.g. a fund whose page lives on another organization's site |
| `uei` | no | Unique Entity ID; federal and SBIR awards then match exactly. Filled in automatically once a unique name match is found |
| `location_precision` | no | `"city"` when lat/lon is a city center rather than the address (used for SBIR firms) |
| `formerly`, `status_note` | no | A former name (still found by search) and a one-line note on ownership or status, both shown in the detail panel |
| `closed`, `closed_note`, `closed_source` | no | Date the site closed (`closed = 2009-11-04`, or `"2015"` when only the year is known), how we know, and a link. The entry is then left off the map |

**Closed companies.** Do not delete the file of a company that has shut down: the monthly HIFLD
import would add the facility again, since HIFLD lags closures by years. Add `closed` with the date
and a `closed_note` with the source instead. The build leaves the entry off the map and the
importers keep skipping it. To find candidates, run `python3 scripts/check_closed.py`: it checks every
company website (domain gone, parked, redirected to another company) and writes a review list to
`data/.closure-review.csv`, which is not committed. A dead website is a lead, not proof; confirm each
closure from a dated source before marking it.

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
- **SBIR/STTR awards.** `scripts/pull_sbir.py` downloads SBIR.gov's public bulk award file
  (every award, refreshed monthly, about 65 MB), keeps awards to companies in the region's cities,
  matches them by website domain and then by name, and writes `data/sbir.json`; awards appear in
  the detail panel and the CSV export. Local SBIR firms that are not yet in the map are listed in
  that file for review. The script also accepts a CSV exported by hand from sbir.gov/awards.
- **Capabilities.** `data/capabilities.toml` maps NAICS prefixes and product keywords to process
  capabilities (casting, machining, molding, circuit boards, ...). The panel counts companies per
  capability, names the largest site, flags capabilities with one or no company as a gap, and
  filters the map; with a sector or product filter active it becomes a gap analysis for that slice.
- **Manufacturing employment by county.** Annual private manufacturing employment from the BLS
  Quarterly Census of Employment and Wages (`scripts/pull_qcew.py` → `data/qcew.json`).
- **Timeline.** Two event streams, pulled by `scripts/pull_events.py` into `data/events_auto.json`:
  every SBIR/STTR award to a company on the map (phase, agency, title, amount) and every federal
  contract or grant of $250,000 or more (start date, agency, description, amount) from USAspending.
  The panel follows the map filters, has a chip per stream, a year strip to narrow by year, and
  sorts by date or by amount; clicking an event selects the company and flies to it.
- **Sorting.** Every panel with numeric columns sorts by any of them from its header (companies,
  staff, dollars, date), as does the roster (company, sector, employees, federal dollars).
- **Distance rings.** 25, 50 and 100 km from the campus, straight-line distance.
- **Provenance.** Every company carries `source` and `updated`; imported files say which dataset
  they came from. The detail panel shows both.
- **Sharing.** The URL hash holds the filters, layers and selection ("Copy link to this view"), and
  the roster downloads as CSV with every field.
- **Search, groups, rings.** Find a company by name above the map; plants of one company
  collapse under its name in the roster and the detail panel lists its other sites; distance rings
  and the "within" filter center on the selected company, or the campus when none is selected.
- **Sector employment.** The employment chart switches between counties and sectors (3-digit NAICS
  from the QCEW area files, folded into the map's sectors) and between head counts and an index.
- **Workforce.** A panel with three views, all from the Bureau of Labor Statistics and sortable by
  any column. *Specialization* lists every 3-digit manufacturing industry for the latest QCEW year
  with jobs, establishments, average pay against the U.S., the region's location quotient (its
  share of private jobs over the U.S. share) and the most concentrated county (`pull_qcew.py`).
  *Occupations* gives jobs, jobs per 1,000 and median pay for production, engineering and
  technician occupations in the four metro areas against the U.S. (OEWS). *Latest month* shows
  monthly manufacturing jobs per metro area (CES) and county unemployment rates (LAUS). The last
  two come from the BLS public API via `scripts/pull_bls.py` → `data/bls.json`; it works without a
  key (25 requests a day; one run uses about ten), and a free key stored as the repository secret
  `BLS_API_KEY` raises the limit.
- **Patents.** `scripts/pull_patents.py` reads USPTO PatentsView. It needs a free API key
  (https://patentsview.org/apis/keyrequest) stored as the repository secret `PATENTSVIEW_API_KEY`;
  without it the step is skipped and the site shows no patent figures.
- **SBIR firms.** `scripts/import_sbir_firms.py` adds a company file for every SBIR/STTR firm in the
  region with an award since 2012 that is not on the map yet, placed at its city's center because
  small firms often list a home address; sectors come from the words in the award titles.
- **About the data and sector briefs.** `about.html` lists every source with match method, date and
  known gaps, with live counts; `brief.html` prints a one-page summary per sector (key figures,
  employment trend, largest companies, capability gaps, largest recent awards).
- **Theme.** Dark by default; the page's Light/Dark switch changes the map and panels with it and is
  remembered in the visitor's browser.

## Keeping the data current

[`refresh-data.yml`](.github/workflows/refresh-data.yml) runs on the 2nd of every month (and on
demand from the Actions tab): it imports new HIFLD facilities, re-pulls USAspending, SBIR.gov, openFDA, the timeline
streams, QCEW and the BLS workforce series, geocodes any file with an address but no coordinates, rebuilds and commits. Each source is
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
data/           sectors, places, capabilities (edit these); county boundaries (Census), shorelines (Natural Earth); pulled datasets (federal, fda, qcew, bls, sbir)
site/           the pages: Notre Dame Web Theme chrome (partials/), page.html + app.js (map), about.html, brief.html + brief.js, app.css
scripts/        build.py, geocode.py, import_hifld.py, import_sbir_firms.py, pull_federal.py, pull_sbir.py, pull_fda.py, pull_qcew.py, pull_bls.py, pull_events.py, pull_patents.py, common.py
docs/           the built site (generated; do not edit by hand)
```

The page uses the University's web theme (NDT4) for its frame, as the PAIR site does, and
[three.js](https://threejs.org/) for the map.

## Sources and credits

Company descriptions, products and headcounts: the HIFLD General Manufacturing Facilities
dataset (U.S. DHS, public domain) for most entries, and the companies' own websites, public
filings, press and business directories for the rest; headcounts are approximate and dated.
Federal awards: USAspending.gov. SBIR/STTR: SBIR.gov. Device registrations: openFDA. Employment, pay, occupations and unemployment: BLS (QCEW, OEWS, CES, LAUS). County boundaries: U.S.
Census Bureau cartographic boundary files. Shorelines: Natural Earth. Code: MIT license (see
LICENSE); company data is factual public information.
