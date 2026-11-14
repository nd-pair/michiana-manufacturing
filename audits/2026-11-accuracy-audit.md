# Accuracy audit of the cleaned HIFLD records, November 2026

**Question.** After the full verification of the HIFLD records, how often is each status wrong? In
particular, how many plants marked "presumed closed" are actually operating?

**Answer.**
- **Plants on the map are mostly right.** About 1 in 10 confirmed records is wrong.
- **The "address unconfirmed" group is the weak spot.** Four of the 10 that a second check could
  resolve were not plants at that address.
- **Presumed-closed plants are mostly gone.** A blind second check found 2 of 30 operating, about
  7%. That suggests roughly 25 to 40 of the 374 hidden records are real plants.
- **The web check misses real plants.** Even for plants that filed with OSHA for 2025, a web check
  found current evidence only 70% of the time. "No trace on the web" is weak evidence by itself.

The per-record findings with sources are in [`2026-11-accuracy-audit.csv`](2026-11-accuracy-audit.csv).

## Method

- **Sample.** Thirty records drawn at random (seed 20261114) from each of four statuses of the
  HIFLD-sourced company files, 120 in all.
- **Blinding.** The records were shuffled together. Each checker received only the name, address and
  website, never the map's status or the earlier finding.
- **The check.** Five independent checkers (AI agents with web search and fetch, 3 to 5 lookups per
  record) answered one question: is there an operating manufacturing plant of this company at this
  address today? Possible answers were yes, no (closed, moved, another business, not
  manufacturing), or unclear.
- **Comparison.** Answers were compared with the map's status. Intervals are 95% Wilson intervals.
- **Limits.**
  - The checkers are the same kind of tool as the original verification, so their errors may be
    correlated with it. A person, or a different source such as a phone call or a site visit,
    would be a stronger test.
  - Thirty per status gives wide intervals.

## Results

| Map status (files) | Checked | Checker: operating | Checker: not as listed | Unclear | Error rate among resolved |
|---|---:|---:|---:|---:|---|
| Confirmed by a same-name 2025 OSHA filing (221) | 30 | 21 | 1 | 8 | 1 of 22, 5% (1–22%) |
| Verified by the web check (351) | 30 | 21 | 2 | 7 | 2 of 23, 9% (2–27%) |
| On the map, address unconfirmed (51) | 30 | 6 | 4 | 20 | 4 of 10, 40% (17–69%) |
| Presumed closed, off the map (374) | 30 | **2** | 4 | 24 | 2 operating of 30, 7% (2–21%) |

**How well the web check sees.** Every plant in the OSHA stratum filed an injury summary for 2025,
so all of them were operating recently. Yet the blind checker confirmed only 21 of 30, 70% (52–83%),
and left 8 unclear. Applying that detection rate to the presumed-closed stratum, 2 found means about
3 of 30 operating. Across all 374 presumed-closed records, that is about 25 to 40 real plants hidden.
They lean toward small shops with little web presence, since a plant with 20 or more employees
should file with OSHA and would come back with the next import.

Weighting the error rates by the size of each group, about 10% of the HIFLD records left on the map
are wrong. The 47 address-unconfirmed records account for a third of those errors. The 301 plants
imported from OSHA's 2025 filings were not sampled. As fresh, self-reported filings, they are likely
the most accurate group, though Nello shows a filing can carry an office address.

## Errors found, and what was done (November 14, 2026)

| Record | Map status | Finding | Action |
|---|---|---|---|
| Delta Industrial Valves, Niles | verified | Weir closed the plant June 30, 2017 (Michigan WARN notice) | closed |
| Deluxe Sheet Metal | verified | a sheet metal installation contractor | removed |
| Ultra Seal, Inc. | address unconfirmed | the business at the address is a one-truck carrier | removed |
| Reub Williams & Sons | address unconfirmed | owner of the Warsaw Times-Union newspaper, a publisher | removed |
| Praxair Distribution | address unconfirmed | now a Linde gas distribution branch | removed |
| Bristol Tool & Die | address unconfirmed | operates at 689 Commerce Dr, not 17992 | address corrected |
| Nello Corp. | OSHA confirmed | the OSHA filing's address is the downtown office, not the tower plant | noted on the card |
| Mishler Packing, LaGrange | presumed closed | a USDA-inspected meat plant at the address, Mishler as a DBA | restored |
| State Wide Windows, Elkhart | presumed closed | listed with headquarters and manufacturing at the address | restored |

## Recommendations

1. **Address-unconfirmed records (47 left).** This is the least reliable group on the map. Either
   flag them on the map as unconfirmed or hide them as presumed closed. Under the policy that a
   missing plant is better than a wrong one, hiding them is consistent: about 40% of those that
   could be resolved were wrong.
2. **Presumed closed.** Accept that about 25 to 40 small plants are hidden. Larger ones come back
   automatically when they file with OSHA. A human pass with phone calls, or a review by the county
   economic development offices, could recover the rest.
3. **Check OSHA addresses that look like offices.** OSHA filers with "Suite" or "Ste" in the address,
   or a downtown address, may file from an office, as Nello does. Check those against the company's
   plant address.
4. **Repeat this audit after the spring 2027 OSHA import, with a person as one checker.** That will
   show whether the error rates fall, and how far the AI checkers agree with a human.

## Follow-up: company websites (November 14, 2026)

The audit showed that the web checks often skipped a company's own contact page. So
`scripts/check_sites.py` now reads the addresses on every company's website (home, contact,
locations and about pages; schema.org data and written-out addresses) and compares them with the
file. It runs every month, changes nothing, and writes [`site-address-check.csv`](site-address-check.csv).

Of 584 companies with a website:

| Result | Companies |
|---|---:|
| The site gives the file's address | 233 |
| Same street, other number (Elkhart County's two numbering systems) | 7 |
| Other addresses in the region only | 21 |
| Only addresses outside the region (corporate offices) | 16 |
| No readable address | 186 |
| Site did not load | 121 |

Seventeen records were corrected from the companies' own sites:
- Utilimaster to Bristol (Wakarusa is no longer listed)
- Nello to its tower plant at 1201 S Sheridan St (its OSHA filing gave the downtown office)
- Frontline to Warsaw, Dee Blast to Coloma, and Express Press, American Cargo, KRA International,
  Midwest Rake, Precision Process and Shepherd Caster to their current addresses
- MOR/ryde to 1966 Sterling Ave
- Exact addresses in place of vague ones for Alexander Chemical, Industrial Maintenance Welding,
  Midwest Timber, Delivery Concepts and E-Pak
- Standard Tool & Die confirmed

Most of the 21 remaining mismatches are plants confirmed by OSHA filings at the listed address, or
multi-plant companies whose site lists other plants. They are left for a person to review.

## Follow-up: review of the website mismatches (November 14, 2026)

Reviewing the 21 website mismatches showed that the OSHA import itself had attached filings by
company name alone. Two kinds of error followed:
- **Stale addresses.** A plant that had moved kept its old HIFLD address even though its 2025 OSHA
  filing gave the new one. Gast, Jet Technologies, Curtis Products, Symmetry Medical, Cleer
  Vision, Modineer and Midwest Finishing are examples.
- **Merged plants.** Separate plants of one company were folded into a single file: Keystone RV's
  Goshen plants, AK Industries, Global Composites, Brinkley, LECO, Thor's Postle Aluminum and
  Reflex plants, and Aluminum Trailer's Plants 3 and 4.

`scripts/import_osha.py` now handles both:
- A filing matched by name or OSHA ID to a file on another street moves that file to the filing's
  address, unless another filing of that name is on the file's street.
- Further filings at other streets get their own files.
- Buildings at one address stay one plant, and a hand-written company-wide file never moves.
- A new tenant at a closed plant's address gets its own file, so the closure stays on record.
- Addresses compare "CR" with "County Road" and "LaPorte" with "La Porte".
- When the Census geocoder lacks a newer street, OpenStreetMap places the plant, and the county
  outlines check that it is in the region.

Results of the re-run:
- 15 files moved to their filing's address.
- 48 plants added as their own files.
- Four addresses got their current filer's name: House of Fara became Alexandria Moulding, Lewis
  Bros. Bakeries became LaPorte Bakery, Silco Tec became Avient, and Worldwide Foam took the
  closed Silgan plant's address.
- Thor Motor Coach's diesel service department was removed as not a plant.

## Follow-up: placement, websites, headcounts, names (November 14, 2026)

**Plants that could not be placed.** 21 of 22 plants with a 2025 OSHA filing but no coordinates
are on the map now. The import retries cleaned addresses (PO boxes, "CR", "SR" and "M-" spelled
out, a "Britol" typo) and falls back to OpenStreetMap. As a last resort it places the plant at its
town's center, the median of the plants already mapped there, and marks it city-level. Examples:
Bennington Marine (574 employees), Lippert in Topeka (586), American Licorice (330), Lakota
Trailers and Viaggio. Removed in the same step:
- four Paul's Auto Yard salvage yards, filed under a manufacturing code;
- Turtle Top's company-wide filing, which duplicated its New Paris plants.

**Website links.** Every website on file was checked again:
- 70 links that no longer resolve, are parked, or now land on unrelated sites (a toy shop, a slots
  site, a card printer) were removed. The old address is kept as `former_website`.
- 33 redirects to a successor or rebrand now point there.
- Four unconfirmed records whose only website was gone are presumed closed.

The log is in `website-link-fixes-2026-11-14.csv`.

**Headcounts against county jobs.** The map's site headcounts add up to 84% of QCEW manufacturing
employment (117,000 of 139,000), with no county far above 100%. LaGrange (57%) and Whitley (54%) are
the thinnest, matching the coverage check. The largest HIFLD estimates led to one stale record: the
"Monaco Coach" plant at 606 Nelsons Parkway, carried with 2,300 estimated employees, is Thor Motor
Coach's Plant 850A. L-P Specialty Products' plant is now Inteplast Building Products. The OSHA
import now ignores generic words ("coach", "products") when it compares names.

**Names.** HIFLD title-cased acronyms ("Ak Industries", "Kz Rv", "Rbc Precision", "Mctd"). 62 are
restored (AK, KZ RV, RBC, MCTD, LECO, CTB and others), and two raw OSHA names were cleaned up.

## Follow-up: HIFLD headcount estimates against OSHA filings (November 14, 2026)

228 plants had both a HIFLD employee estimate (base year 2022) and a 2025 OSHA Form 300A count:
- The median estimate is 1.13 times the OSHA count, and 71% of estimates are within a factor of
  two of it.
- The error depends on size. Plants estimated under 50 employees are underestimated (median
  0.79x), and plants estimated at 250 or more are overestimated (median 1.77x).
- 10 plants estimated at 20 or more filed fewer than 20, and 5 the other way round.

The largest gaps turned out to be our own matching: companies that file separately for buildings
or departments at one address had only one filing on the plant's record. Keystone RV's Hackberry
Drive plant showed 7 employees. The import now adds up the filings at a plant's address, counting
an identical figure once. Sixteen plants were corrected, including Keystone (7 to 482), Carpenter
(22 to 299), Welch Packaging (37 to 309) and Foamcraft (2 to 59).

Same-address duplicates found by the consistency check were also resolved:
- Removed as duplicates: Robert Bosch's St. Joseph plant (an estimated 700 against 182 filed with
  OSHA), Schafer, Tigmaster, Winona Powder Coating, Securall / A & A, Thor at 701 County Road 15,
  and a filing named "Saint Joseph" that is Walsworth's plant.
- Removed as not a plant: FedEx Office.
- Moved: Serenade Foods, to its own plant address.
