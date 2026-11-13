#!/usr/bin/env python3
"""Take a company off the map, keeping its file so the monthly imports do not add it again.

    python3 scripts/remove_company.py companies/acme--elkhart--100.toml "duplicate of acme.toml"
    python3 scripts/remove_company.py "Acme Corp" "not a manufacturer: a sales office"
    python3 scripts/remove_company.py --undo companies/acme--elkhart--100.toml

Sets `removed` (today's date) and `removed_reason` in the company file. Use it for entries that
should never have been on the map: duplicates, sites outside the region, offices or warehouses that
make nothing, or businesses that do not exist. A company that existed and shut down is marked closed
instead (see CURATION.md). The About page counts removed entries; the file and its history stay.
"""
import datetime, os, re, sys, tomllib
from common import P, companies, norm, set_field

def main(args):
    undo = "--undo" in args
    args = [a for a in args if a != "--undo"]
    if not args or (not undo and len(args) < 2):
        sys.exit(__doc__)
    target, reason = args[0], " ".join(args[1:]).strip()
    path = target if os.path.exists(target) else None
    if not path:
        hits = [c for c in companies() if norm(c["name"]) == norm(target)]
        if len(hits) != 1:
            sys.exit("%d companies match %r; give the file path instead%s" % (len(hits), target,
                     "".join("\n  companies/" + c["_file"] for c in hits)))
        path = P("companies", hits[0]["_file"])
    text = open(path, encoding="utf-8").read()
    if undo:
        text = re.sub(r"(?m)^removed(_reason)? = .*\n", "", text)
        open(path, "w", encoding="utf-8").write(text)
        print("restored", path); return
    set_field(path, "removed", datetime.date.today().isoformat())
    set_field(path, "removed_reason", reason)
    tomllib.load(open(path, "rb"))
    print("removed from the map:", path, "-", reason)

if __name__ == "__main__":
    main(sys.argv[1:])
