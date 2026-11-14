# Michiana Manufacturing

An interactive map of the manufacturing and technology companies of the South Bend–Elkhart region,
by the [Correll Lab](https://correlllab.nd.edu) at the University of
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

HIFLD's base year is 2022, so plants with 20 or more employees are also imported from **OSHA's
establishment-specific injury and illness data** (Form 300A, which manufacturers of that size must
file every year, with the annual average number of employees). OSHA's site turns away scripts, so
download the latest "300A Summary Data" file by hand from
<https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data> once a year (filings are due
March 2) and run `python3 scripts/import_osha.py <file.csv or .zip>`. It keeps NAICS 31–33
establishments whose ZIP code lies mostly in a region county (`data/region_zips.json`), matches them
to existing files by OSHA ID, street address or name in the same city, replaces estimated headcounts
with OSHA's reported figure, and writes new files for the rest after checking the county with the
Census geocoder; departments a company files separately at one address become one plant.
`data/osha.json` keeps every year's establishments, so a plant that stops filing is flagged for review.
Rules worth knowing when reading its output:

- Town names are written one way (`canon_city`: "LaPorte" and "La Porte" are one town), and county
  grid roads match however they are written ("1350N" = "1350 North").
- A filing at another house number on a file's street is its own plant once that file stands for
  another one (Keystone's numbered plants on Hackberry Drive). House numbers of different lengths
  stay together, since Elkhart County has two numbering systems.
- A file moves to its own filing's street address. A PO box or a repeated town name is stripped
  first; a filing that lists two addresses is not used.
- A new tenant at a closed plant's address gets its own file, so the closure stays on record.
- A plant that files under another industry code (a modular builder as construction, some makers as
  wholesalers) keeps a current headcount: a second pass refreshes the count of a file at the same
  address with a shared name word. It never adds or renames files, and farm filings are left out.
- One headcount filed for several addresses counts as company-wide only when the hours worked match
  too. A file's own single-establishment figure is corrected from its filing.
- Filed industry text that says only "Manufacturing", "Retail" or the code is replaced by the official
  title (`data/naics_titles.json`, made once by `scripts/make_naics_titles.py`).
- A plant no geocoder can place goes to its town: `data/places.toml`, else the median of the plants
  mapped there, else the center of a small ZIP code area (`data/zip_centers.json`, made once by
  `scripts/make_zip_centers.py`). It is marked `location_precision = "city"`.

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
| `manufacturer` | no | `false` leaves the company out of every count (on the map still); `true` counts it. Without it, NAICS 31–33 and hand-written companies count, and software firms, SBIR research firms with no production, investors and universities do not |
| `presumed_closed`, `presumed_closed_reason` | no | Date of a verification check that found an imported record closed without a dated source, or with no current trace; the entry is left off the map until a same-name OSHA filing or a dated source shows it operating (see CURATION.md) |
| `unconfirmed`, `unconfirmed_reason` | no | The company operates in the region, but no current source confirms a plant at this address; shown as a dim column and a note on the card (see CURATION.md) |
| `verified`, `verified_note` | no | Date and finding of a verification check that found the plant operating at this address (`scripts/apply_checks.py`); later checks can skip it |
| `osha_occupant` | no | Set by `scripts/import_osha.py` when another name filed with OSHA at this file's address: a successor, rename or new tenant to review. Shown on the card |
| `uei` | no | Unique Entity ID; federal and SBIR awards then match exactly. Filled in automatically once a unique name match is found |
| `location_precision` | no | `"city"` when lat/lon is a city center rather than the address (used for SBIR firms) |
| `humanoid`, `humanoid_not`, `humanoid_evidence`, `humanoid_note` | no | Humanoid parts the company supplies (ids from [`data/humanoid.toml`](data/humanoid.toml)), inferred ones it does not, `"confirmed"` or `"self-reported"` once that is established, and a note on what was confirmed |
| `formerly`, `status_note` | no | A former name (still found by search) and a one-line note on ownership or status, both shown in the detail panel |
| `removed`, `removed_reason` | no | Takes an entry off the map that should not be on it (duplicate, outside the region, not a manufacturer), keeping the file; set with `scripts/remove_company.py` |
| `closed`, `closed_note`, `closed_source` | no | Date the site closed (`closed = 2009-11-04`, or `"2015"` when only the year is known), how we know, and a link. The entry is then left off the map |

**Closed companies.** Do not delete the file of a company that has shut down: the monthly HIFLD
import would add the facility again, since HIFLD lags closures by years. Add `closed` with the date
and a `closed_note` with the source instead. The build leaves the entry off the map and the
importers keep skipping it. To find candidates, run `python3 scripts/check_closed.py`: it checks every
company website (domain gone, parked, redirected to another company) and writes a review list to
`data/.closure-review.csv`, which is not committed. It adds two public-record signals: Indiana WARN
closing notices matched to a plant whose closing date has passed (`scripts/pull_warn.py`, monthly; a
notice filed under a new owner's name is matched by hand in `data/warn_matches.toml`,
`data/warn.json`; Michigan publishes no table), and plants that filed with OSHA one year but not the
next. A dead website is a lead, not proof; confirm each
closure from a dated source before marking it. `scripts/check_coverage.py` compares the map with the Census Bureau's County Business Patterns
(manufacturing establishments by county, size and industry; `audits/coverage-check.csv`).
`scripts/check_consistency.py` checks the files against each other: coordinates outside the region's
counties, two files at one address (also under two town names), with one name within 300 m, or with
related names next door on one street, site headcounts above 5,000,
sectors that disagree with NAICS, and city-level placements (`audits/consistency-check.csv`).
It places plants in counties with the Census Bureau's detailed county outlines,
`data/region_counties_detail.json`, made once by `scripts/make_county_detail.py`. The map's own
outlines in `data/region_counties.json` are simplified and are off by up to 2 km near county lines.
`scripts/check_sites.py` (monthly) reads the addresses on each company's own website and compares them
with the file's: `audits/site-address-check.csv` lists matches, the same street under another number
(Elkhart County's two numbering systems), other addresses in the region, and sites without one. It
changes nothing; a person moves a plant when the company's own site shows it elsewhere. Sample audits of the imported records, with every finding and its source, are in
[`audits/`](audits/) (November 2026: 100 HIFLD records, then the rest in batches). `scripts/apply_checks.py`
applies a batch of per-record web findings under CURATION.md and logs each action to a CSV.

**Positions.** If you give an address but no `lat`/`lon`, run `python3 scripts/geocode.py` and it
looks the address up on OpenStreetMap and writes the coordinates into the file. Check the result
on the map.

**Sectors and labels.** Sectors and their colors live in `data/sectors.toml`; cities, reference
metros, state labels and the campus landmark in `data/places.toml`.

## Layers and panels

The page has four tabs, each with its own link (`#tab=occupations`, `#tab=outlook`,
`#tab=humanoid`): **Companies** (the map, sectors, products, roster, federal footprint, capabilities
and timeline), **Occupations** (workforce, manufacturing employment and the occupations humanoids
could help), **Physical AI outlook** (the Humanoid Deployment Benefit Index and the region comparison) and
**Humanoid supply chain**. Filters carry across tabs, and a company named on another tab opens on the map.
Without WebGL the map shows a notice and everything else still works. The page carries:

- **Federal footprint.** Procurement contracts and grants since FY2016 performed in the region (place of
  performance, not the recipient's address) for every company, from USAspending.gov, matched by UEI or
  recipient name, plus the region-wide totals by awarding agency.
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
  contract or grant of $250,000 or more performed in the region (start date, agency, description, amount) from USAspending.
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
- **Humanoid supply chain.** The goal is to make Michiana a hub for manufacturing physical AI,
  from motors and sensors to full humanoids. [`data/humanoid.toml`](data/humanoid.toml) lists the
  20 components of a full-size humanoid, each with a body region, a rough share of its cost and
  rules that match local companies by industry code or product description. The Humanoid supply chain tab
  draws a humanoid with each region shaded by the depth of local supply, counting either
  every company with a related capability (the potential) or what is available now: for
  build-to-print parts (machined, cast, stamped and molded parts, harnesses, board assembly) any
  capable contract shop, for the rest only companies confirmed to make the part. Tiles give the share of a humanoid's cost with two or more local
  suppliers in each view, the number of companies, robotics-related federal and SBIR awards by year,
  and the monthly trend: every build saves the current month's figures to `data/progress.json`.
  Clicking a region or component filters the map and roster. To confirm a supplier, add
  `humanoid = [...]` and `humanoid_evidence = "confirmed"` with a `humanoid_note` to its file.
  Milestones (first local actuator line, first assembled humanoid) go in
  [`data/milestones.toml`](data/milestones.toml) and appear on the timeline.
- **Humanoid Deployment Benefit Index.** The Physical AI outlook tab scores where humanoid robots
  could benefit local manufacturers most. Five of its six pillars compare the region with the
  U.S. (= 100); *local supply* has no U.S. benchmark and is scored against a fixed target (half of a
  humanoid's cost available locally = 100). The pillars: *task fit* (local jobs weighted by how much of
  the work is handling parts, repetitive motion, awkward postures and hazards, from O*NET),
  *high-mix potential* (jobs in custom and short-run industries; smaller establishments),
  *labor pressure* (unemployment, workers aged 55+, turnover), *adoption readiness* (mechanics,
  electricians, technicians and engineers per 1,000 jobs), *local supply* (from the humanoid panel)
  and *jobs and pay* (manufacturing job and pay growth over five years, value added per job).
  The index is the weighted geometric mean of the pillars, so gains in one can offset losses in
  another. It does not show that workers gain or keep their jobs: the jobs-and-pay pillar can fall
  while the index rises, so read that pillar on its own. An occupation table lists local jobs, task fit, the work a humanoid could take on and
  pay. Weights, traits, industry and occupation lists are in
  [`data/opportunity.toml`](data/opportunity.toml); `scripts/pull_workforce.py` pulls O*NET,
  the Census Bureau's Quarterly Workforce Indicators (bulk files, no key) and BEA county GDP; the
  index is saved monthly with the humanoid figures in `data/progress.json`.
- **Region comparison.** `scripts/compare_regions.py` scores the same index,
  with the same method and U.S. benchmarks, for the regions in [`data/regions.toml`](data/regions.toml)
  (ten metros of similar size with a well-known university, plus Michiana) and keeps the ranking, the
  pillars and a monthly history in `data/comparison.json`, shown as a table at the bottom of the
  Physical AI outlook tab. It runs in the monthly refresh after the
  other pulls; inputs that change yearly or quarterly (occupations, Census QWI) are fetched again only
  when a new release is out. The BLS API key (`BLS_API_KEY` secret) keeps it within the BLS limits.
- **Notre Dame research.** `scripts/pull_nd_research.py` reads every federal grant, cooperative
  agreement and contract to the University of Notre Dame since FY2016, and its subawards on other
  institutions' awards, from USAspending.gov (all agencies), and keeps those about physical AI:
  robots, autonomy and drones, prosthetics and exoskeletons, haptics, legged or humanoid systems,
  robotic manufacturing (in the title, or three times in the description). NSF awards get their
  investigators from the NSF Award Search API. The index panel shows totals, active awards,
  agencies, years and a table; the awards also appear on the timeline as "Notre Dame research".
  Industry, foundation and state funding are not in this data.
- **Roster size.** The roster shows the first 20 companies in the current sort, with buttons for
  100 or all.
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
demand from the Actions tab): it imports new HIFLD facilities, re-pulls Indiana WARN notices, USAspending, SBIR.gov, openFDA, the timeline
streams, QCEW and the BLS workforce series, geocodes any file with an address but no coordinates, rebuilds and commits. Each source is
optional, so an outage at one does not block the others. Hand-written files are never touched.

## Automated news review

Once a month, after the data pulls, `scripts/review_llm.py` has Claude read the region's news and
apply what it finds, without a person approving each change. It is held to these limits:

- **Trusted sources only.** Claude's web search and page reading are restricted, by the API's own
  domain filter, to the outlets and government sites in [`data/news_sources.toml`](data/news_sources.toml).
- **Rules.** [`CURATION.md`](CURATION.md) is sent as its instructions: what counts as a closure,
  rename, move or new company, how to record humanoid capabilities and milestones, and what never
  goes in.
- **Checked in code.** A finding changes the data only if its source is on a trusted domain and was
  actually retrieved in that run, it is marked high confidence, its date is real and not in the
  future, and it matches exactly one company (or, for a new company, a known city, a valid sector,
  and an address or city that geocodes). Only a fixed set of fields can change, and files are never
  deleted.
- **Budget.** Each run stops starting new tasks before it could pass `LLM_BUDGET_USD` (set to 20 in
  the workflow); a typical month costs a few dollars. It searches last month's news three times
  (closures; new plants, acquisitions and renames; robotics and physical AI) and checks up to 15
  closure candidates from the website scan, in rotation.
- **Logged.** Every applied change, with its source, and each run's cost are in
  `data/news_review.json`; any change can be reverted from the git history.

**Open items and time to live.** Each review also lists the facts that are missing or doubtful in
`data/open_items.json`: a company without a street address, an address the geocoders cannot place, a
website whose domain no longer exists or is parked, and a status note marked unconfirmed or
disputed. It tries to fix each one once per run (a search of the trusted sources for addresses and
status notes, a new website scan, another geocoder try) and counts the attempt. After three
attempts (`ttl` in `data/news_sources.toml`) the doubtful fact is removed: the dead website link or
the unconfirmed note goes, and an address without a street number is dropped so the company stays
at its city's center; a full address that cannot be placed is kept. An item closes as soon as the
fact is fixed; every resolution and expiry is logged in the same file.

**Removing a company.** For entries that should not be on the map at all (duplicates, sites outside
the region, offices that make nothing, businesses that do not exist), run
`python3 scripts/remove_company.py <file or exact name> "<reason>"`. It sets `removed` and
`removed_reason`; the build leaves the entry off and the file stays, so the monthly imports do not
add it again (`--undo` restores it). A company that shut down is marked closed instead. Companies are
never removed automatically.

It needs an Anthropic API key in the repository secret `ANTHROPIC_API_KEY` (best a key from a
Console workspace with its own monthly spend limit); without it the step is skipped. Try it locally
with `python3 scripts/review_llm.py --dry-run`, which shows the plan without calling the API.

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
data/           sectors, places, capabilities (edit these); county boundaries (Census; simplified for the map, detailed for placing plants), ZIP code centers and NAICS titles (Census), shorelines (Natural Earth); pulled datasets (federal, fda, qcew, bls, sbir, osha, warn)
site/           the pages: Notre Dame Web Theme chrome (partials/), page.html + app.js (map), about.html, brief.html + brief.js, app.css
scripts/        review_llm.py (monthly news review), build.py, humanoid.py, opportunity.py, geocode.py, import_hifld.py, import_osha.py, import_sbir_firms.py, pull_warn.py, pull_federal.py, pull_sbir.py, pull_fda.py, pull_qcew.py, pull_bls.py, pull_workforce.py, pull_nd_research.py, pull_events.py, pull_patents.py, check_consistency.py, check_coverage.py, check_sites.py, check_closed.py, apply_checks.py, make_county_detail.py, make_zip_centers.py, make_naics_titles.py, common.py
docs/           the built site (generated; do not edit by hand)
```

The page uses the University's web theme (NDT4) for its frame, as the PAIR site does, and
[three.js](https://threejs.org/) for the map.

## Sources and credits

Company descriptions, products and headcounts: the HIFLD General Manufacturing Facilities
dataset (U.S. DHS, public domain) for most entries, OSHA's Form 300A establishment data (U.S.
Department of Labor) for plants with 20 or more employees, and the companies' own websites, public
filings, press and business directories for the rest; headcounts are approximate and dated.
Layoff and closing notices: Indiana Department of Workforce Development (WARN). Federal awards: USAspending.gov. SBIR/STTR: SBIR.gov. Device registrations: openFDA. Employment, pay, occupations and unemployment: BLS (QCEW, OEWS, CES, LAUS). Task traits: O*NET 31.0 (CC BY 4.0). Workforce age and turnover: Census LEHD QWI. Value added: BEA. County boundaries: U.S.
Census Bureau cartographic boundary files. Shorelines: Natural Earth. Code: MIT license (see
LICENSE); company data is factual public information.
