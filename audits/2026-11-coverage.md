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
| Elkhart, IN | 841 | 424 | 50% | 449 | 360 | 80% |
| St. Joseph, IN | 313 | 170 | 54% | 139 | 148 | 106% |
| Berrien, MI | 275 | 108 | 39% | 105 | 95 | 90% |
| LaGrange, IN | 188 | 41 | 22% | 56 | 34 | 61% |
| Kosciusko, IN | 184 | 85 | 46% | 80 | 71 | 89% |
| LaPorte, IN | 155 | 76 | 49% | 74 | 66 | 89% |
| Marshall, IN | 133 | 56 | 42% | 62 | 51 | 82% |
| Noble, IN | 116 | 40 | 34% | 57 | 38 | 67% |
| Van Buren, MI | 91 | 23 | 25% | 35 | 21 | 60% |
| Whitley, IN | 73 | 18 | 25% | 32 | 17 | 53% |
| Cass, MI | 69 | 24 | 35% | 27 | 24 | 89% |
| Fulton, IN | 38 | 12 | 32% | 17 | 12 | 71% |
| Starke, IN | 19 | 10 | 53% | 12 | 7 | 58% |
| **Region** | **2495** | **1087** | **44%** | **1145** | **944** | **82%** |

## By industry

| NAICS | Industry | Census establishments | On the map | Coverage |
|---|---|---:|---:|---:|
| 332 | Fabricated metal | 538 | 189 | 35% |
| 336 | Transportation equipment | 306 | 184 | 60% |
| 333 | Machinery | 225 | 101 | 45% |
| 321 | Wood products | 205 | 56 | 27% |
| 337 | Furniture | 200 | 51 | 26% |
| 326 | Plastics and rubber | 191 | 110 | 58% |
| 311 | Food | 139 | 48 | 35% |
| 339 | Miscellaneous (incl. medical devices) | 122 | 50 | 41% |
| 325 | Chemicals | 93 | 43 | 46% |
| 327 | Nonmetallic minerals | 77 | 43 | 56% |
| 323 | Printing | 74 | 24 | 32% |
| 331 | Primary metals | 62 | 56 | 90% |
| 312 | Beverages | 50 | 3 | 6% |
| 334 | Computers and electronics | 33 | 30 | 91% |
| 335 | Electrical equipment | 30 | 18 | 60% |
| 322 | Paper | 25 | 29 | 116% |
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
  employees (53–61%). Those plants should file with OSHA, so the spring 2027 OSHA import is the
  next chance to fill them. Some may have filed under a ZIP code that lies mostly in a neighboring
  county outside the region, which the import skips.
- **St. Joseph County shows more plants with 20+ employees than Census (106%; 115% before the
  November 14 fixes).** Two of the excess were stale HIFLD records next to the plant's current OSHA
  filer: Copper & Brass Sales at 1015 St Jerome St (the import read 'Saint Jerome' and 'St Jerome'
  as different streets, now fixed) and Eagle Pack, 40 m from United Petfood's plant; both are now
  presumed closed. Of the remaining 148, 64 rest on HIFLD's 2022 modeled headcounts and 13 of those
  are unconfirmed; no OSHA filing backs them, so some are likely under 20 employees today. 74 have
  an OSHA filing, close to Census's 139 minus the plants that do not file.
- **Comparisons are rough.** Census counts employer establishments; a map site can be one or
  several of them, and a few map sites are offices or research units without their own
  establishment code.

## What would raise coverage

1. Import OSHA filings by county rather than by ZIP code. That needs the county from the Census
   geocoder for every regional ZIP, including ZIPs that lie mostly outside the region.
2. Ask the county economic development offices and the Purdue and Michigan MEPs to review each
   county's list. They know the small shops that no public dataset names.
3. Add a 'suggest a company' link next to the 'report a correction' idea in the data-quality list.
