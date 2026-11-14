#!/usr/bin/env python3
"""Apply the results of a verification check of imported records, under CURATION.md.

    python3 scripts/apply_checks.py results.json [more.json ...] [--date YYYY-MM-DD] [--csv audits/file.csv] [--dry-run]

Each results file is a JSON array of per-record findings, one object per company file:
  {"id", "status", "facility", "last_evidence_year", "current_name", "closed_year", "evidence", "note"}
with status one of operating, closed, moved, acquired_renamed, other_occupant, address_unconfirmed,
no_trace. The checks
behind them are web lookups (name, street address, website, Wayback Machine, news, listings).

Rules, for imported records only (HIFLD or OSHA; hand-written files are never changed here):
- operating at a production site: `verified` (the date) and `verified_note` are set;
- operating, but an office, sales, service or retail site: `removed`, since it makes nothing;
- closed with a year and a source: `closed`, `closed_note`, `closed_source`;
- moved, with a current address in the region (by ZIP code, data/region_zips.json, or by a city
  with company files in the region): the
  address is updated, lat/lon dropped for the geocoder, `verified` set and the move noted;
- closed without a year, no_trace, moved elsewhere, other_occupant (another
  business is at the address), a vacant site or a residence: `presumed_closed` with the finding as
  `presumed_closed_reason`; listing a plant that does not exist is worse than missing one;
- acquired_renamed, when the finding ties the new name to this address (same plant, address or
  phone; the new owner lists a site there) without hedging, and no file in the same city already
  carries it: `name` becomes the current name, the old one goes to `formerly`, the old
  website and UEI are dropped; otherwise presumed_closed;
- address_unconfirmed (the company operates in the region, but nothing confirms or contradicts this
  address): left unchanged, since the company exists;
- a finding whose note says the record was not actually searched (UNVERIFIED, search budget) is
  skipped and listed, to be checked again.
Optionally writes every finding with the action taken to a CSV for the audit trail.
"""
import csv, datetime, json, re, sys
from common import P, companies, company_path, set_field, del_field, norm

UNSEARCHED = re.compile(r"(?i)\bunverified\b|search budget|budget ran out|not searched|never searched|no lookups|no name or address|no address search|not researched")
HEDGED = re.compile(r"(?i)not confirm|unconfirm|inferen|no source|could just be|not verified|may be|possibly|appears to|unclear whether|no address|redirects? to|is down|is dead")
TIED = re.compile(r"(?i)same (plant|address|site|phone)|at this address|lists? (its|a|the)? ?\w* ?(plant|site|location|facility)? ?(at|in) |\d+ ([NSEW]\.? )?\w+ (St|Rd|Dr|Ave|Blvd|Pkwy|Way|Ct|Ln|Street|Road|Drive|Avenue)\b")

def main(args):
    dry = "--dry-run" in args
    opt = lambda k: args[args.index(k) + 1] if k in args else None
    date = opt("--date") or datetime.date.today().isoformat()
    out_csv = opt("--csv")
    files = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] not in ("--date", "--csv"))]
    found = [x for f in files for x in json.load(open(f))]
    cs = {c["_id"]: c for c in companies()}
    zips = json.load(open(P("data", "region_zips.json")))["zips"]
    region_cities = {(c.get("city") or "").lower() for c in cs.values() if c.get("state") in ("IN", "MI")}
    def in_region(addr):
        """By ZIP code when the address has one, else by a city that has company files in the region."""
        z = re.search(r"\b(\d{5})(-\d{4})?\s*$", addr)
        if z:
            return z[1] in zips
        m = re.search(r",\s*([^,]+),\s*(IN|MI)\s*$", addr)
        return bool(m) and m[1].strip().lower() in region_cities
    names_in_city = {(norm(c["name"]), (c.get("city") or "").lower()) for c in cs.values() if not c.get("closed") and not c.get("presumed_closed") and not c.get("removed")}
    log, counts, skipped = [], {}, []
    for x in found:
        c = cs.get(x.get("id"))
        if not c:
            continue
        path = company_path(c["_id"])
        src = (c.get("source") or "")
        note = (x.get("note") or "").strip()
        ev = [e for e in (x.get("evidence") or []) if isinstance(e, str) and e.startswith("http")] if isinstance(x.get("evidence"), list) else ([x["evidence"]] if str(x.get("evidence") or "").startswith("http") else [])
        st, fac = x.get("status"), x.get("facility") or ""
        if not src.startswith(("HIFLD", "OSHA")):
            action = "skipped: hand-written file"
        elif UNSEARCHED.search(note):
            action = "skipped: not searched"; skipped.append(c["_id"])
        elif st == "address_unconfirmed":
            action = "unchanged: the company operates in the region, this address is unconfirmed"
        elif st == "operating" and fac in ("office_or_hq", "service_or_retail", "warehouse_distribution") and not re.search(r"(?i)manufactur|plant|production|makes|fabricat", note):
            action = "removed"
            if not dry:
                set_field(path, "removed", date)
                set_field(path, "removed_reason", "not a production site (%s), found in a verification check: %s" % (fac.replace("_", " "), note))
        elif st == "operating" and fac != "residence_or_vacant":
            action = "verified"
            if not dry:
                set_field(path, "verified", date)
                set_field(path, "verified_note", note + (" Source: " + ev[0] if ev else ""))
        elif st == "moved" and in_region(x.get("current_address") or "") and fac not in ("office_or_hq", "service_or_retail", "warehouse_distribution") \
                and not re.search(r"(?i)\b(store|branch|showroom|retail)\b", note):
            action = "moved to " + x["current_address"]
            if not dry:
                set_field(path, "address", x["current_address"].strip()); del_field(path, "lat"); del_field(path, "lon")
                city = re.search(r",\s*([^,]+),\s*(IN|MI)\b", x["current_address"])
                if city:
                    set_field(path, "city", city[1].strip())
                set_field(path, "status_note", "Moved from %s; found in a verification check (%s): %s" % (c.get("address", ""), date, note))
                set_field(path, "verified", date)
                del_field(path, "presumed_closed"); del_field(path, "presumed_closed_reason")
        elif st == "closed" and x.get("closed_year") and ev:
            action = "closed"
            if not dry:
                set_field(path, "closed", str(x["closed_year"])); set_field(path, "closed_note", note); set_field(path, "closed_source", ev[0])
        elif st == "acquired_renamed" and x.get("current_name") and not HEDGED.search(note) and TIED.search(note) \
                and fac not in ("office_or_hq", "service_or_retail", "warehouse_distribution") \
                and (norm(x["current_name"]), (c.get("city") or "").lower()) not in names_in_city:
            action = "renamed to " + x["current_name"]
            if not dry:
                set_field(path, "formerly", "; ".join(v for v in (c.get("formerly"), c["name"]) if v))
                set_field(path, "name", x["current_name"])
                set_field(path, "status_note", "Renamed in a verification check (%s): %s%s" % (date, note, " Source: " + ev[0] if ev else ""))
                del_field(path, "website"); del_field(path, "uei")
                set_field(path, "verified", date)
            names_in_city.add((norm(x["current_name"]), (c.get("city") or "").lower()))
        else:
            action = "presumed closed"
            why = {"no_trace": "no current trace of this company at this address", "moved": "the company operates elsewhere, not at this address",
                   "other_occupant": "another business is at this address now" + (" (%s)" % x["current_name"] if x.get("current_name") else ""),
                   "acquired_renamed": "renamed or acquired, but the new name is not tied to this address" + (" (%s)" % x["current_name"] if x.get("current_name") else ""),
                   "closed": "reported closed, without a dated source", "operating": "the address is vacant or a residence"}.get(st, st)
            if not dry:
                set_field(path, "presumed_closed", date)
                set_field(path, "presumed_closed_reason", "Verification check: %s. %s%s" % (why, note, " Source: " + ev[0] if ev else ""))
        counts[action.split(" to ")[0]] = counts.get(action.split(" to ")[0], 0) + 1
        log.append({"file": "companies/" + c["_file"], "name": c["name"], "address": c.get("address", ""), "status": st, "facility": fac,
                    "last_evidence_year": x.get("last_evidence_year") or "", "current_name": x.get("current_name") or "", "action": action,
                    "finding": note, "evidence": " ".join(ev)})
    if out_csv:
        new = not __import__("os").path.exists(out_csv)
        with open(out_csv, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(log[0]) if log else ["file"])
            if new:
                w.writeheader()
            w.writerows(log)
    print("%d findings: %s" % (len(found), ", ".join("%s %d" % kv for kv in sorted(counts.items(), key=lambda kv: -kv[1]))))
    if skipped:
        print("not searched, check again: " + " ".join(skipped))

if __name__ == "__main__":
    main(sys.argv[1:])
