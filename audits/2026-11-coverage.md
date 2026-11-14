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
| Elkhart, IN | 841 | 406 | 48% | 449 | 339 | 76% |
| St. Joseph, IN | 313 | 184 | 59% | 139 | 160 | 115% |
| Berrien, MI | 275 | 111 | 40% | 105 | 98 | 93% |
| LaGrange, IN | 188 | 38 | 20% | 56 | 31 | 55% |
| Kosciusko, IN | 184 | 86 | 47% | 80 | 72 | 90% |
| LaPorte, IN | 155 | 77 | 50% | 74 | 67 | 91% |
| Marshall, IN | 133 | 55 | 41% | 62 | 51 | 82% |
| Noble, IN | 116 | 40 | 34% | 57 | 38 | 67% |
| Van Buren, MI | 91 | 22 | 24% | 35 | 20 | 57% |
| Whitley, IN | 73 | 17 | 23% | 32 | 16 | 50% |
| Cass, MI | 69 | 26 | 38% | 27 | 26 | 96% |
| Fulton, IN | 38 | 12 | 32% | 17 | 12 | 71% |
| Starke, IN | 19 | 9 | 47% | 12 | 6 | 50% |
| **Region** | **2495** | **1083** | **43%** | **1145** | **936** | **82%** |

## By industry

| NAICS | Industry | Census establishments | On the map | Coverage |
|---|---|---:|---:|---:|
| 332 | Fabricated metal | 538 | 192 | 36% |
| 336 | Transportation equipment | 306 | 174 | 57% |
| 333 | Machinery | 225 | 105 | 47% |
| 321 | Wood products | 205 | 52 | 25% |
| 337 | Furniture | 200 | 49 | 24% |
| 326 | Plastics and rubber | 191 | 111 | 58% |
| 311 | Food | 139 | 47 | 34% |
| 339 | Miscellaneous (incl. medical devices) | 122 | 49 | 40% |
| 325 | Chemicals | 93 | 43 | 46% |
| 327 | Nonmetallic minerals | 77 | 42 | 55% |
| 323 | Printing | 74 | 26 | 35% |
| 331 | Primary metals | 62 | 61 | 98% |
| 312 | Beverages | 50 | 3 | 6% |
| 334 | Computers and electronics | 33 | 29 | 88% |
| 335 | Electrical equipment | 30 | 19 | 63% |
| 322 | Paper | 25 | 28 | 112% |
| 314 | Textile products | 20 | 12 | 60% |
| 313 | Textile mills | 4 | 6 | 150% |
| 315 | Apparel | 3 | 0 | 0% |
| 316 | Leather | 3 | 1 | 33% |
| 324 | Petroleum and coal | 3 | 1 | 33% |

## Reading it

- **Coverage is weakest where shops are small.** Beverages (mostly breweries and wineries), furniture
  and wood products are in the 6–25% range. These are mostly small Amish and family shops in
  LaGrange, Elkhart and Kosciusko counties, and among the least covered.
- **Whitley, Starke, LaGrange and Van Buren counties** are the thinnest for plants with 20 or more
  employees (50–57%). Those plants should file with OSHA, so the spring 2027 OSHA import is the
  next chance to fill them. Some may have filed under a ZIP code that lies mostly in a neighboring
  county outside the region, which the import skips.
- **St. Joseph County shows more plants with 20+ employees than Census (115%).** Of the map's 160
  there, 75 rest on HIFLD's modeled headcounts, which put some small shops above 20. Only 74
  have an OSHA filing, close to Census's 139 minus the plants that do not file.
- **Comparisons are rough.** Census counts employer establishments; a map site can be one or
  several of them, and a few map sites are offices or research units without their own
  establishment code.

## What would raise coverage

1. Import OSHA filings by county rather than by ZIP code. That needs the county from the Census
   geocoder for every regional ZIP, including ZIPs that lie mostly outside the region.
2. Ask the county economic development offices and the Purdue and Michigan MEPs to review each
   county's list. They know the small shops that no public dataset names.
3. Add a 'suggest a company' link next to the 'report a correction' idea in the data-quality list.
