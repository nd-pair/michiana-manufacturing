# Audit of 100 HIFLD records, November 2026

**Question.** How many of the HIFLD records on the map are not operating manufacturing plants at
the listed address: offices, duplicate sites, closed plants or stale names?

**Answer.** Only 41 of the 100 sampled records could be shown to be an operating plant at the
listed address. Another 32 have a documented problem, and 27 left no current trace at all.
HIFLD's "2022" base year is misleading: the dataset carries plants that closed in 2009, 2013 and
2018 under names that went out of use years ago. Offices and duplicates are rare. The main
problems are closures and stale names.

Nothing was removed or edited because of this audit. The per-record findings, with sources, are in
[`2026-11-hifld-audit.csv`](2026-11-hifld-audit.csv).

## Sample and method

- **Population:** the 1,180 HIFLD-imported company files on the map on November 13, 2026, excluding
  files already marked closed or removed.
- **Sample:** 100 records drawn at random (Python `random.sample`, seed 20261113).
- **Signals checked automatically for every record:**
  - an OSHA Form 300A filing for 2025 by an establishment with the same name at that address
    (`data/osha.json`);
  - another name filing with OSHA at the same address (`osha_occupant`);
  - the website check from `scripts/check_closed.py`;
  - Indiana WARN closing notices;
  - other company files at the same address, with the same name or on the same domain.
- **Web verification, two passes by AI agents:**
  - The first pass checked all 100 records against company sites, search results, news,
    directories, and state and federal records.
  - The second pass took the 41 records the first left unresolved and searched each street
    address for its current occupant. It also checked Wayback Machine capture dates for dead
    domains.
- **Limits of the method:**
  - The web checks were made by AI agents with rate-limited search, and much of the evidence is
    undated. Each finding cites its source, but none has been reviewed by a person.
  - "No current trace" means the search found nothing. It does not prove that the plant closed.

## Results

| Verdict | Records | 95% interval | Meaning |
|---|---:|---|---|
| Confirmed operating (OSHA 2025) | 18 | | Same-name establishment filed with OSHA at this address for 2025 |
| Operating (web evidence) | 23 | | Live site, recent listing or news; often undated |
| **Operating, total** | **41** | **32–51%** | |
| Closed | 9 | 5–16% | Dated closure evidence (announcement, WARN notice, sale, demolition) |
| Different company now | 14 | 9–22% | Successor, renamed plant or new tenant at the address |
| Moved or wrong address | 7 | | Company operates, but not at the listed address |
| Not a production site | 2 | | Office or headquarters only |
| **Documented problem, total** | **32** | **24–42%** | |
| No current trace | 27 | 19–36% | Nothing found for the name or the address after two passes |

Applied to all 1,180 HIFLD records on the map, this suggests:

| Group | Estimated records | Range |
|---|---:|---|
| Documented problems | 380 | 280–500 |
| No trace | 320 | 220–420 |
| Operating as listed | 480 | 380–600 |

**Duplicates are rare.** Two sampled records share an address with another file:
- I/N Tek and I/N Kote, both now Cleveland-Cliffs New Carlisle;
- Marque and McCoy Miller, ambulance lines at 1110 D.I. Drive.

Two more share a name with a file at another address (Magnetech, South Bend; Amerimax, Elkhart);
these may be duplicates or real second sites. Most multi-site names in the sample, such as Lippert
and Blocksom, are genuine separate plants.

## Findings by group

**Closed (9).**
- Acument, Rochester: closed 2020.
- Atlas Die Chem-Milling, Elkhart: building listed for sale in 2025; not confirmed.
- Diversified Machine, Bristol: closed 2018, with a WARN notice.
- Eaton PSCO, Three Rivers: a different occupant is named in a 2024 state report.
- Gunite, Elkhart: closed 2013.
- Hermel Die Casting, Eau Claire: property sold and demolition begun in 2022.
- Liberty Homes, Syracuse: closed around 2009.
- Marque, Elkhart: production moved after a 2013 sale.
- Trelleborg Sealing Profiles, Bristol: closed December 2018.

**Different company now (14).** The plant may still run, but under another name:
- Sullair → Hitachi Global Air Power
- Dane Systems → JR Automation
- Da-Lite → Legrand AV
- I/N Tek → Cleveland-Cliffs
- Millennium Industries → TI Fluid Systems
- Specialty Heat Treating → Bodycote
- Skyline's Bristol RV division: sold in 2014 and moved
- A Homestead Shoppe → AHS Lighting
- Liberty Steel → Liberty 3D Technologies
- BPC → LaSalle Bristol

Four more addresses have a new tenant filing with OSHA:
- Nappanee Wood Products' address → LCI
- Terra Group's → Kountry Wood Products
- TL Industries' (defunct after 2006) → Haul-About
- Vitamins, Inc.'s → Viobin Products

**Moved or wrong address (7).**
- Griffin Tool: listed at 2951 Johnson Rd, not 3033.
- Lebermuth: South Bend only, no Bremen site found.
- Magnetech: headquarters moved to Ohio.
- Michigan City Paper Box: 1206 Pine St is listed under The Packaging Trust.
- OrthoPediatrics: now at 2850 Frontier Dr, Warsaw.
- Sundowner: Elkhart plants closed by 2008, production moved to Oklahoma.
- Vanair: Michigan City plants only.

**Not a production site (2).**
- Ag Plus: the cooperative's headquarters office.
- Ave Maria Press: a publisher whose own printing reportedly stopped.

**No current trace (27).** Many have dead, parked or repurposed domains: Superior Sample's now
serves a gambling site, R-Vision's is for sale, and Amerimax's and Covalence's are gone. Others are
small shops with no web presence, and one is a building listed for lease (Dekko, North Webster).
These are likely closed or renamed, but the evidence does not show it.

## Side finding: OSHA matching

The audit caught a flaw in the OSHA import added the same day. Matching by street address alone
had copied the current occupant's OSHA headcount onto stale HIFLD files. For example, TL Industries,
defunct since 2006, got Haul-About's employees.

Across the whole dataset, 89 HIFLD addresses had an OSHA filer with a different name. The import now
records such a filer as `osha_occupant` instead: the file keeps its own facts, the card shows the
other name, and the closure review lists it. This was fixed and redeployed on November 13
(commit 3db0270).

## Recommendations (for a person to act on; nothing is automatic)

1. **Closed (9).** Confirm the cited sources and mark each with `closed = YYYY-MM-DD` and
   `closed_source`.
2. **Different company now (14), and the 89 `osha_occupant` flags across the dataset.** Rename the
   file to the current company, or mark the old one closed and let the OSHA occupant be added. Most
   are quick to decide from the card.
3. **Moved or wrong address (7).** Correct the address, or mark the site closed where the company
   left.
4. **No trace (27 in the sample, roughly 320 overall).** Do not remove them. Instead, show
   confidence on the map: grade a HIFLD record "unconfirmed since 2022" until a same-name OSHA
   filing, a live website or a dated source confirms it. Readers then see which columns rest on
   HIFLD alone.
5. **Repeat the audit after the next OSHA import (spring 2027).** A plant that stops filing becomes
   a closure signal then. Re-sampling 100 records will show whether the corrections moved the
   numbers.
