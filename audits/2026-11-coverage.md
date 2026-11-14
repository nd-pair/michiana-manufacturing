# Coverage of the map against Census County Business Patterns, November 2026

**Question.** How much of the region's manufacturing is on the map?

**Answer.** About 4 in 5 plants with 20 or more employees, and about 2 in 5 of all manufacturing
establishments. The missing ones are mostly small shops: no free public source names them.

The comparison uses the Census Bureau's County Business Patterns 2023 county file (public, no key),
counting manufacturing establishments (NAICS 31–33) in the region's 13 counties. It is run by
`scripts/check_coverage.py`; the numbers are in [`coverage-check.csv`](coverage-check.csv).

## By county

| County | Census establishments | On the map | Coverage | Census, 20+ employees | On the map, 20+ | Coverage |
|---|---:|---:|---:|---:|---:|---:|
| Elkhart, IN | 841 | 417 | 50% | 449 | 354 | 79% |
| St. Joseph, IN | 313 | 159 | 51% | 139 | 140 | 101% |
| Berrien, MI | 275 | 107 | 39% | 105 | 95 | 90% |
| LaGrange, IN | 188 | 39 | 21% | 56 | 32 | 57% |
| Kosciusko, IN | 184 | 81 | 44% | 80 | 67 | 84% |
| LaPorte, IN | 155 | 72 | 46% | 74 | 62 | 84% |
| Marshall, IN | 133 | 56 | 42% | 62 | 50 | 81% |
| Noble, IN | 116 | 39 | 34% | 57 | 37 | 65% |
| Van Buren, MI | 91 | 23 | 25% | 35 | 21 | 60% |
| Whitley, IN | 73 | 18 | 25% | 32 | 17 | 53% |
| Cass, MI | 69 | 24 | 35% | 27 | 24 | 89% |
| Fulton, IN | 38 | 12 | 32% | 17 | 12 | 71% |
| Starke, IN | 19 | 10 | 53% | 12 | 7 | 58% |
| **Region** | **2495** | **1057** | **42%** | **1145** | **918** | **80%** |

## By industry

| NAICS | Industry | Census establishments | On the map | Coverage |
|---|---|---:|---:|---:|
| 332 | Fabricated metal | 538 | 185 | 34% |
| 336 | Transportation equipment | 306 | 180 | 59% |
| 333 | Machinery | 225 | 96 | 43% |
| 321 | Wood products | 205 | 55 | 27% |
| 337 | Furniture | 200 | 50 | 25% |
| 326 | Plastics and rubber | 191 | 106 | 55% |
| 311 | Food | 139 | 47 | 34% |
| 339 | Miscellaneous (incl. medical devices) | 122 | 48 | 39% |
| 325 | Chemicals | 93 | 42 | 45% |
| 327 | Nonmetallic minerals | 77 | 41 | 53% |
| 323 | Printing | 74 | 23 | 31% |
| 331 | Primary metals | 62 | 55 | 89% |
| 312 | Beverages | 50 | 3 | 6% |
| 334 | Computers and electronics | 33 | 28 | 85% |
| 335 | Electrical equipment | 30 | 18 | 60% |
| 322 | Paper | 25 | 28 | 112% |
| 314 | Textile products | 20 | 11 | 55% |
| 313 | Textile mills | 4 | 6 | 150% |
| 315 | Apparel | 3 | 0 | 0% |
| 316 | Leather | 3 | 1 | 33% |
| 324 | Petroleum and coal | 3 | 1 | 33% |

## Reading it

- **Coverage is weakest where shops are small.** Beverages (mostly breweries and wineries), furniture
  and wood products are in the 6–25% range. These are mostly small Amish and family shops in
  LaGrange, Elkhart and Kosciusko counties, and among the least covered.
- **Whitley, Starke, LaGrange and Van Buren counties** are the thinnest for plants with 20 or more
  employees (53–60%). Those plants should file with OSHA, so the spring 2027 OSHA import is the
  next chance to fill them. Filings under a ZIP code that lies mostly in a neighboring county
  are not the gap: the import skips them, but none of the 83 such 2025 manufacturing filings is
  clearly inside a region county (checked November 14 with the Census geocoder and Indiana's
  address points; the one near miss, Southern Michigan Rubber on M-60 near Jones, sits on the
  Cass/St. Joseph line and Michigan's own records name both counties).
- **St. Joseph County is now level with Census (140 plants with 20+ employees against 139; it
  read 115% before the November 14 fixes).** Two of the excess were stale HIFLD records next to the
  plant's current OSHA filer: Copper & Brass Sales at 1015 St Jerome St (the import read 'Saint
  Jerome' and 'St Jerome' as different streets, now fixed) and Eagle Pack, 40 m from United
  Petfood's plant. A re-check of the region's unconfirmed records then took off Parker Hannifin's
  Mishawaka plant (closed 2018), South Bend Controls (now listed in Arizona), Mann+Hummel's North
  Bendix Drive site and several smaller shops with no trace since 2023. Of the remaining 140, 56 rest on
  HIFLD's 2022 modeled headcounts and 74 have an OSHA filing.
- **Comparisons are rough.** Census counts employer establishments; a map site can be one or
  several of them, and a few map sites are offices or research units without their own
  establishment code.

## What would raise coverage

1. ~~Import OSHA filings by county rather than by ZIP code.~~ Checked November 14: for the 2025
   filings it adds no plant (see above), so the ZIP filter stays.
2. Ask the county economic development offices and the Purdue and Michigan MEPs to review each
   county's list. They know the small shops that no public dataset names.
3. Add a 'suggest a company' link next to the 'report a correction' idea in the data-quality list.
