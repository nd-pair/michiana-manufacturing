# Curation rules

These are the rules the map's data follows. People editing company files follow them, and the
monthly automated news review (`scripts/review_llm.py`) reads this file as its instructions. The
review applies its findings without a human approving them, so it is held to the strictest
reading of every rule: when in doubt, it records nothing.

## Scope and sources

- The map covers manufacturers, and the investors, research groups and startups around them, in
  these counties: St. Joseph, Elkhart, Marshall, LaPorte, Kosciusko, Starke, Fulton, LaGrange,
  Noble and Whitley in Indiana; Berrien, Cass and Van Buren in Michigan.
- Only public information goes in. Never confidential or internal documents.
- The automated review uses only the trusted sources in `data/news_sources.toml`, and every fact
  it records cites the article it came from.
- Do not record private individuals. Name companies, not people.

## Closures

- Never delete a company file: the monthly HIFLD import would add the facility again. Mark it
  closed with `closed` (the date, `YYYY-MM-DD`, `YYYY-MM` or `YYYY`), `closed_note` (one factual
  sentence) and `closed_source` (the article). The build then leaves it off the map.
- A closure needs a dated source that says this facility, in this region, has closed, shut down,
  ceased operations or was liquidated. A dead website, a missing listing or a directory entry is
  not enough.
- Imported records (HIFLD, OSHA, SBIR) are held to a stricter standard, because listing a plant
  that does not exist is worse than missing one. When a verification check finds an imported record
  closed without a dated source, or finds no current trace of it at its address (no OSHA filing, no
  working website, no listing or news since 2023), mark it `presumed_closed` (the date of the check)
  with `presumed_closed_reason` (one sentence: what was checked and found). The build leaves it off
  the map. A same-name OSHA filing or a dated source that it operates brings it back: delete both
  fields. The automated news review does not set `presumed_closed`; it is for verification checks.
- An EPA report (Toxics Release Inventory or RCRA Biennial Report) at the address of a presumed-closed or
  closed plant, often under another name, is a lead, not proof. `scripts/pull_waste.py` lists these each
  month in `audits/epa-unmatched.csv`. With a dated 2024-2026 source, a rename restores the file (new
  `name`, old one in `formerly`), and a different business at the address gets its own file.
- When a check finds that the company operates in the region but cannot confirm a plant at the listed
  address, mark it `unconfirmed` (the date of the check) with `unconfirmed_reason`. It stays on the map
  as a dim column with a note on its card. A dated source or OSHA filing for the address removes the
  flag (delete both fields); a source that the plant is elsewhere or gone moves or closes it.
  `verified` means the address was confirmed. A check whose own note calls the evidence weak or says
  the address was not confirmed sets `unconfirmed` instead (`scripts/apply_checks.py`, `WEAK`).
- One plant, one file, one OSHA ID. When a duplicate is removed, its OSHA ID goes to the file that
  stays; `scripts/check_consistency.py` flags an OSHA ID on two files.
- A WARN closing notice for a plant is a dated source. `scripts/pull_warn.py` marks an imported plant
  closed once the notice's closing date has passed, unless the plant filed with OSHA for a later year;
  notices for hand-written files go to the closure review.
- Layoffs, temporary shutdowns, shift cuts and announced closures with a future date are not
  closures. An announced future closure may go in `status_note`.
- A plant that keeps running under a new owner or name is a rename, not a closure.

## Removing entries

- An entry that should never have been on the map (a duplicate, a site outside the region, an
  office or warehouse that makes nothing, a business that does not exist) is marked `removed` with a
  `removed_reason`, not deleted. A company that existed and shut down is marked closed instead.
- Recyclers are not removed as non-manufacturers: scrap yards, auto recyclers that dismantle and
  scrap vehicles, secondary metal processors and plastics, paper, tire and e-waste recyclers go in
  the sector `Recycling & recovery` with a `recovers` list. They are shown as resource providers and
  left out of the manufacturer counts. Trash haulers, transfer stations and landfills are not
  recyclers. A recycler needs a dated 2024-2026 source at its address, like any other new entry.
- Companies are not removed for lack of news. Imported records that a verification check cannot
  confirm are presumed closed instead (see Closures).

## Open items

- Missing or doubtful facts (no street address, a dead website, an unconfirmed status note) are
  open items with a time to live of three review attempts. A fix needs a trusted source, like any
  other fact. When the attempts run out, the doubtful fact is removed rather than kept unverified.

## Renames, acquisitions and moves

- When a plant keeps running under a new name or owner, set `name` to the current name, keep the
  old one in `formerly`, and explain in `status_note` (one sentence, with the year).
- When a company moves within the region, update `address`, remove `lat`/`lon` so the geocoder
  places it again, and note the move in `status_note`.

## New companies

- Add a manufacturing facility, a robotics or physical-AI company, or a manufacturing-related
  investor or research unit that opens in the region, with its address when the source gives one.
  A plant under construction may be added with a `status_note` that says so.
- Not retail, restaurants, warehouses or distribution-only sites, and not companies outside the
  counties above.
- Sectors must be one of those in `data/sectors.toml`.

## Physical AI and the humanoid supply chain

- The goal is a regional hub for manufacturing physical AI, from motors and sensors to full
  humanoids. Humanoids are framed as making manufacturers more competitive and taking on hard,
  repetitive and hazardous work, never as replacing workers.
- A company's humanoid parts are inferred from its products unless its file says otherwise. When
  a trusted source reports that a local company makes a humanoid or robot component (motors,
  gear reducers, actuators, bearings, encoders, drivers, boards, harnesses, batteries, cameras,
  sensors, hands, castings, machined, sheet-metal, plastic or composite parts, integration), add
  the component to `humanoid` with `humanoid_evidence = "self-reported"` and the source in
  `humanoid_note`. Only a conversation with the company makes it `"confirmed"`.
- Build-to-print parts (machined, cast, stamped and molded parts, harnesses, board assembly)
  count any capable contract shop; engineered parts count only a confirmed maker.
- Milestones toward the goal (first local production of a robot component, a robot or humanoid
  pilot in a local plant, a robotics company opening, a Notre Dame physical-AI partnership with
  industry) go in `data/milestones.toml` with a date, a one-line title and the source.

## Style

- Factual, plain sentences; no promotion, no speculation, no superlatives from press releases.
- The timeline has no "announcement" or "WARN" categories; news changes the data, it is not
  listed as news.

## Variety and end markets

These fields describe how a manufacturer presents its own production today: how much of it is
custom, short-run or many-variant, and which markets it sells into. They come only from the
company's own website, never from directories, news or inference from the NAICS code, and they
describe the firm now, not in any earlier year. Leave a field out when the site does not say; when
in doubt, record nothing. `scripts/variety_summary.py` summarizes them by county in
`data/variety.json`. The map does not show them.

- `made_to_order`: `"yes"` when the site says the company builds to the customer's order, print or
  specification (custom, engineered-to-order, build-to-print, or only contract work); `"no"` when it
  offers a catalog of standard products or models (options listed on a model still count as
  standard) and says nothing of custom work; `"mixed"` when it offers both.
- `job_shop`: `true` when the site advertises contract manufacturing, job-shop, build-to-print,
  short-run or prototype work for other firms; `false` only when the site describes the business
  fully and offers nothing but its own products.
- `product_lines`: an approximate whole number of distinct product lines or families the site offers
  (families, not models or SKUs; for a brand house, its brands). Left out for a pure job shop or when
  the site's range is unclear.
- `end_markets`: the markets the site names as served, or shows customers in, using only the names in
  `data/end_markets.toml` (add a name there first, with a one-line definition). Not inferred from
  the products.
- `variety_scope = "company"` when the website is that of a larger parent and describes the whole
  company rather than this plant; without it the fields describe the business at this site.
- `variety_source`: the page or pages the fields were read from (a list of URLs);
  `variety_checked`: the date of the reading (`YYYY-MM-DD`).
- A company without a `website` gets these fields only when its own website is found with
  confidence (same name and an address in the region); the site then goes in `variety_source`.
- A website that no longer belongs to the company (parked, for sale, another business) gives no
  fields; it is a lead for the closure checks, not a closure.
- Fetch politely: one page at a time per site, robots.txt respected, a generic user agent, no
  personal details; a site that refuses automated access is skipped, not worked around.
