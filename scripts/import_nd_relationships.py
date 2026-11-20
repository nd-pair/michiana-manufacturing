#!/usr/bin/env python3
"""Update data/nd_relationships.toml from iNDustry Labs' list of companies where Notre Dame has a relationship
at the senior leadership level (a CSV report, sent periodically; it stays outside the repo).

    python3 scripts/import_nd_relationships.py path/to/Company-List.csv

Only company names and websites are kept; the CSV is not copied into the repo. Each organization is linked to
the company files it covers:
- `files`: company ids on the map. Kept as edited by hand; a new name is matched automatically by website
  domain, then by name (open files only), and printed for review.
- `group = true`: flag every site of the same company group (for example a parent listed once for many plants).
- `names`: a pattern (case-insensitive) for company names to flag as well, where one company's plants carry
  several names or fall into several groups (Lippert, LCI, Kinro).
- `off_map`: why an organization on the list is not on the map (a bank, a law firm, a hospital, outside the
  region, ...); it is listed in the ND relationships view without a column.
Organizations no longer on the list are dropped; the file always mirrors the latest list.
"""
import csv, datetime, re, sys, tomllib
from common import P, companies, norm

PATH = P("data", "nd_relationships.toml")
dom = lambda u: re.sub(r"^www\.", "", re.sub(r"^https?://", "", (u or "").strip().lower()).split("/")[0])

def q(s):
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')

def write(orgs, updated):
    out = ["# Organizations where Notre Dame (iNDustry Labs) has a relationship at the senior leadership level.",
           "# From iNDustry Labs' list, shared to flag these companies on the map; updated with",
           "# scripts/import_nd_relationships.py. Company names and websites only.",
           "# files: company ids on the map; group = true flags every site of the company group;",
           "# off_map: why an organization is listed without a column on the map.",
           "", "source = \"iNDustry Labs, University of Notre Dame\"", "updated = %s" % q(updated), ""]
    for o in sorted(orgs, key=lambda o: o["name"].lower()):
        out += ["[[org]]", "name = %s" % q(o["name"])]
        if o.get("website"):
            out.append("website = %s" % q(o["website"]))
        out.append("files = [%s]" % ", ".join(q(f) for f in o.get("files", [])))
        if o.get("group"):
            out.append("group = true")
        if o.get("names"):
            out.append("names = %s" % q(o["names"]))
        if o.get("off_map"):
            out.append("off_map = %s" % q(o["off_map"]))
        out.append("")
    open(PATH, "w").write("\n".join(out))

def main():
    rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")))
    try:
        old = {norm(o["name"]): o for o in tomllib.load(open(PATH, "rb")).get("org", [])}
    except FileNotFoundError:
        old = {}
    cs = [c for c in companies() if not any(c.get(k) for k in ("closed", "presumed_closed", "removed"))]
    by_dom, by_name = {}, {}
    for c in cs:
        if c.get("website"):
            by_dom.setdefault(dom(c["website"]), []).append(c["_id"])
        by_name.setdefault(norm(c["name"]), []).append(c["_id"])
    orgs, review = [], []
    for r in rows:
        name = (r.get("Company Name") or "").strip()
        if not name:
            continue
        o = old.get(norm(name))
        if o is None:
            d = dom(r.get("Website"))
            o = {"name": name, "website": d, "files": by_dom.get(d) or by_name.get(norm(name)) or []}
            review.append(o)
        o["website"] = o.get("website") or dom(r.get("Website"))
        orgs.append(o)
    write(orgs, datetime.date.today().isoformat())
    print("data/nd_relationships.toml: %d organizations, %d linked to the map, %d listed off the map, %d new"
          % (len(orgs), sum(1 for o in orgs if o.get("files")), sum(1 for o in orgs if o.get("off_map")), len(review)))
    for o in review:
        print("  new: %s -> %s" % (o["name"], ", ".join(o["files"]) or "no match (set files or off_map by hand)"))

if __name__ == "__main__":
    main()
