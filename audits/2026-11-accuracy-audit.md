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
