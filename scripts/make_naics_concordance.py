#!/usr/bin/env python3
"""Older manufacturing NAICS codes (2002, 2007, 2012, 2017 editions) and their NAICS 2022 code. Run once;
the result is committed.

    python3 scripts/make_naics_concordance.py DIR    # DIR holds the four Census concordance files

HIFLD (base year 2022) still carries codes from the 2002 and 2007 editions (332116 metal stamping,
331111 iron and steel mills, 336399 other motor vehicle parts), and OSHA filers use several editions.
This chains the Census Bureau's concordances (census.gov/naics/?concordances, public, no key)
2002 -> 2007 -> 2012 -> 2017 -> 2022:

    2002_to_2007_NAICS.xls, 2007_to_2012_NAICS.xls   (old Excel format: pip3 install xlrd)
    2012_to_2017_NAICS.xlsx, 2017_to_2022_NAICS.xlsx  (read with the standard library)

A code is chained from the latest edition that lists it. It goes into `codes` only when it leads to
exactly one NAICS 2022 code; codes that split into several go into `split`, for a person to decide.
Writes data/naics_concordance.json; common.naics_2022() reads it.
"""
import json, os, re, sys
from collections import defaultdict
from common import P
from make_naics_titles import rows as xlsx_rows

def pairs_xls(path):
    import xlrd   # only needed for the two old-format files
    s = xlrd.open_workbook(path).sheet_by_index(0)
    for i in range(s.nrows):
        a, c = s.cell_value(i, 0), s.cell_value(i, 2)
        if isinstance(a, float) and isinstance(c, float):
            yield "%06d" % a, "%06d" % c

def pairs_xlsx(path):
    for r in xlsx_rows(open(path, "rb").read()):
        a, c = str(r.get("A", "")).split(".")[0].strip(), str(r.get("C", "")).split(".")[0].strip()
        if re.fullmatch(r"\d{6}", a) and re.fullmatch(r"\d{6}", c):
            yield a, c

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__)
    steps = []   # (edition, {old: {new, ...}}) in order
    for ed, f, reader in (("2002", "2002_to_2007_NAICS.xls", pairs_xls), ("2007", "2007_to_2012_NAICS.xls", pairs_xls),
                          ("2012", "2012_to_2017_NAICS.xlsx", pairs_xlsx), ("2017", "2017_to_2022_NAICS.xlsx", pairs_xlsx)):
        m = defaultdict(set)
        for a, c in reader(os.path.join(d, f)):
            m[a].add(c)
        if len(m) < 900:
            sys.exit("%s: only %d codes read; the file layout may have changed" % (f, len(m)))
        steps.append((ed, m))
    titles = json.load(open(P("data", "naics_titles.json")))["titles"]
    codes, split = {}, {}
    for code in sorted({a for _, m in steps for a in m if a[:2] in ("31", "32", "33")}):
        if code in titles:
            continue   # already a NAICS 2022 code
        start = max(i for i, (_, m) in enumerate(steps) if code in m)   # the latest edition that lists it
        cur = {code}
        for _, m in steps[start:]:
            cur = set().union(*(m.get(x, {x}) for x in cur))
        cur = {x for x in cur if x in titles}
        if len(cur) == 1:
            codes[code] = next(iter(cur))
        elif cur:
            split[code] = sorted(cur)
    json.dump({"source": "U.S. Census Bureau NAICS concordances 2002-2007, 2007-2012, 2012-2017, 2017-2022, chained",
               "codes": codes, "split": split}, open(P("data", "naics_concordance.json"), "w"), indent=0)
    print("wrote data/naics_concordance.json: %d older codes with one NAICS 2022 code, %d that split" % (len(codes), len(split)))

if __name__ == "__main__":
    main()
