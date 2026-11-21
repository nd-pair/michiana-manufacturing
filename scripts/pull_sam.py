#!/usr/bin/env python3
"""CAGE codes and UEIs from SAM.gov's monthly public entity extract. Writes data/sam.json, the `cage` (and, where
missing, `uei`) fields of matched company files, and audits/sam-manufacturers-not-on-map.csv.

    SAM_API_KEY=... python3 scripts/pull_sam.py        # download the latest monthly file (one API request)
    python3 scripts/pull_sam.py --file SAM_PUBLIC_MONTHLY_V2_YYYYMMDD.ZIP   # use a file already downloaded
    python3 scripts/pull_sam.py --rematch              # only match the saved registrations to company files again

The public extract (SAM.gov Entity Extracts API; a personal API key, kept as the SAM_API_KEY secret, allows 10
requests a day) lists every active registration and those expired in the last six months: UEI, CAGE code,
legal and DBA name, physical address, primary NAICS. Only registrations at a ZIP code in the region
(data/region_zips.json) are read; points of contact and every other field are skipped.

A registration is matched to a company file by its UEI when a file carries it (or by hand, in
data/waste_matches.toml with the UEI as `epa_id`), otherwise by its physical street address plus a shared
distinctive word in the name, among files on the map. A CAGE code belongs to one registration, and a
registration to one physical address, so a company's code lands on the site SAM lists, not on its other plants.
The file gets `cage`, and `uei` if it had none; a file whose UEI differs from an address match is left alone
and reported. Codes are never removed: a registration that lapses keeps its CAGE code.

Reported for review, changing nothing: active registrations that match a closed or presumed-closed file (a
lead that the plant operates, not proof), and manufacturers (primary NAICS 31-33) registered in the region
with no company file (audits/sam-manufacturers-not-on-map.csv).
"""
import csv, datetime, io, json, os, re, shutil, sys, tempfile, tomllib, urllib.error, urllib.request, zipfile
from common import P, companies, company_path, norm, set_field
from import_osha import addr_key
from pull_waste import GENERIC, UA

API = "https://api.sam.gov/data-services/v1/extracts"
# 0-based positions in the pipe-delimited public V2 file ("SAM Master Extract Mapping v6.0 Public File V2 Layout")
F = {"uei": 0, "cage": 3, "code": 5, "expires": 8, "name": 11, "dba": 12, "division": 13, "street": 15,
     "city": 17, "state": 18, "zip": 19, "country": 21, "naics": 32}
OFF = ("closed", "presumed_closed", "removed")

def download(folder):
    key = os.environ.get("SAM_API_KEY")
    if not key:
        sys.exit("pull_sam.py: no SAM_API_KEY; nothing pulled")
    q = "fileType=ENTITY&sensitivity=PUBLIC&frequency=MONTHLY&version=V2&charset=ASCII&api_key=" + key
    try:
        r = urllib.request.urlopen(urllib.request.Request(API + "?" + q, headers=UA), timeout=1800)
    except urllib.error.HTTPError as e:   # the message names the status, never the URL (which holds the key)
        sys.exit("pull_sam.py: SAM.gov answered %d: %s" % (e.code, e.read(600).decode("utf-8", "replace").replace(key, "<key>")))
    name = re.search(r'filename="?([^";]+)', r.headers.get("Content-Disposition", ""))
    path = os.path.join(folder, name.group(1) if name else "sam_extract.zip")
    with r, open(path, "wb") as fh:
        shutil.copyfileobj(r, fh, 1 << 22)
    if not zipfile.is_zipfile(path):
        sys.exit("pull_sam.py: SAM.gov sent no ZIP file: %s" % open(path, "rb").read(600).decode("utf-8", "replace").replace(key, "<key>"))
    return path

def records(path):
    z = zipfile.ZipFile(path)
    print("pull_sam.py: %s (%.1f MB): %s" % (os.path.basename(path), os.path.getsize(path) / 1e6,
          ", ".join("%s %d bytes" % (i.filename, i.file_size) for i in z.infolist())))
    inner = [n for n in z.namelist() if n.lower().endswith(".zip")]
    if inner and not any(n.lower().endswith((".dat", ".txt")) for n in z.namelist()):   # a ZIP inside the ZIP
        z = zipfile.ZipFile(io.BytesIO(z.read(inner[0])))
    names = [n for n in z.namelist() if n.lower().endswith((".dat", ".txt"))]
    if not names:
        sys.exit("pull_sam.py: no .dat or .txt file in the download")
    dat = names[0]
    with z.open(dat) as fh:
        for line in io.TextIOWrapper(fh, encoding="latin-1"):
            if line.startswith(("BOF ", "EOF ")):
                continue
            f = line.rstrip("\r\n").split("|")
            if len(f) < 33 or not re.fullmatch(r"[A-Z0-9]{12}", f[0]):
                sys.exit("pull_sam.py: unexpected record layout in %s: %r" % (dat, line[:120]))
            yield {k: f[i].strip() for k, i in F.items()}

def pull(path):
    zips = set(json.load(open(P("data", "region_zips.json")))["zips"])
    out = []
    for r in records(path):
        if r["country"] == "USA" and r["state"] in ("IN", "MI") and r["zip"][:5] in zips:
            out.append({"uei": r["uei"], "cage": r["cage"], "active": r["code"] == "A", "expires": r["expires"],
                        "name": r["name"], "dba": r["dba"], "division": r["division"], "street": r["street"],
                        "city": r["city"].title(), "state": r["state"], "zip": r["zip"][:5], "naics": r["naics"]})
    return out

def words(*names):
    return {w for n in names for w in norm(n).split() if len(w) > 2} - GENERIC

def match(ents):
    """Set e["company"] and e["how"] for each registration; returns the company files by id."""
    cs = {c["_id"]: c for c in companies()}
    try:
        hand = {m["epa_id"]: m["file"] for m in tomllib.load(open(P("data", "waste_matches.toml"), "rb")).get("match", [])}
    except FileNotFoundError:
        hand = {}
    by_uei = {c["uei"]: i for i, c in cs.items() if c.get("uei")}
    by_addr = {}
    for i, c in cs.items():
        k = addr_key((c.get("address") or "").split(",")[0], c.get("city"))
        if k:
            by_addr.setdefault(k, []).append(i)
    for e in ents:
        e["company"], e["how"] = None, None
        if e["uei"] in hand:
            e["company"], e["how"] = hand[e["uei"]] or None, "hand"
        elif e["uei"] in by_uei:
            e["company"], e["how"] = by_uei[e["uei"]], "uei"
        else:
            w = words(e["name"], e["dba"], e["division"])
            hits = [i for i in by_addr.get(addr_key(e["street"], e["city"]), []) if w & words(cs[i]["name"], cs[i].get("formerly", ""))]
            live = [i for i in hits if not any(cs[i].get(k) for k in OFF)]
            hits = live or hits   # a file off the map is matched only to report a lead
            if len(hits) == 1:
                e["company"], e["how"] = hits[0], "address"
    # two registrations matched to one file by address: neither is certain
    seen = {}
    for e in ents:
        if e["how"] == "address":
            seen.setdefault(e["company"], []).append(e)
    for i, es in seen.items():
        if len({e["uei"] for e in es}) > 1:
            for e in es:
                e["company"], e["how"] = None, "ambiguous"
    return cs

def apply(ents, cs):
    by_uei = {c["uei"]: i for i, c in cs.items() if c.get("uei")}
    new_cage = new_uei = changed = 0
    conflicts, leads = [], []
    for e in ents:
        c = cs.get(e["company"])
        if not c:
            continue
        if any(c.get(k) for k in OFF):
            if e["active"] and not c.get("removed"):   # removed files (offices, duplicates) are off the map by design
                leads.append((e, c))
            continue
        path = company_path(c["_id"])
        if c.get("uei") and c["uei"] != e["uei"] and e["how"] != "hand":
            conflicts.append((e, c)); continue
        if not c.get("uei"):
            if e["uei"] in by_uei:
                conflicts.append((e, c)); continue
            set_field(path, "uei", e["uei"]); by_uei[e["uei"]] = c["_id"]; new_uei += 1
        if e["cage"] and c.get("cage") != e["cage"]:
            set_field(path, "cage", e["cage"])
            if c.get("cage"):
                changed += 1
            else:
                new_cage += 1
    print("company files: %d new CAGE codes, %d changed, %d new UEIs" % (new_cage, changed, new_uei))
    for e, c in conflicts:
        print("  not changed, %s carries another UEI (%s): SAM %s %s, %s, %s" % (c["_id"], c.get("uei") or "on another file", e["uei"], e["name"], e["street"], e["city"]))
    for e, c in leads:
        print("  lead: active SAM registration (expires %s) matches %s, which is %s: %s, %s"
              % (e["expires"], c["_id"], next(k for k in OFF if c.get(k)).replace("_", " "), e["street"], e["city"]))

def not_on_map(ents):
    rows = sorted((e for e in ents if not e["company"] and e["active"] and e["naics"][:2] in ("31", "32", "33")), key=lambda e: (e["city"], e["name"]))
    with open(P("audits", "sam-manufacturers-not-on-map.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["uei", "cage", "name", "dba", "street", "city", "state", "zip", "primary_naics", "expires"])
        for e in rows:
            w.writerow([e["uei"], e["cage"], e["name"], e["dba"], e["street"], e["city"], e["state"], e["zip"], e["naics"], e["expires"]])
    print("audits/sam-manufacturers-not-on-map.csv: %d active manufacturer registrations with no company file" % len(rows))

def main():
    path = P("data", "sam.json")
    if "--rematch" in sys.argv:
        out = json.load(open(path))
    else:
        tmp = tempfile.mkdtemp()
        try:
            src = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else download(tmp)
            ents = pull(src)
            out = {"pulled": datetime.date.today().isoformat(), "file": os.path.basename(src),
                   "source": "SAM.gov public entity extract (monthly, V2), Entity Extracts API", "registrations": ents}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    ents = out["registrations"]
    cs = match(ents)
    apply(ents, cs)
    not_on_map(ents)
    # keep registrations matched to a file and manufacturers, the ones a later --rematch can use
    out["registrations"] = sorted((e for e in ents if e["company"] or e["naics"][:2] in ("31", "32", "33")), key=lambda e: e["uei"])
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    print("wrote data/sam.json: %d registrations in the region's ZIP codes, %d matched to a company file (%d by UEI, %d by address, %d by hand), %d ambiguous"
          % (len(ents), sum(1 for e in ents if e["company"]), sum(1 for e in ents if e["how"] == "uei"),
             sum(1 for e in ents if e["how"] == "address"), sum(1 for e in ents if e["how"] == "hand"), sum(1 for e in ents if e["how"] == "ambiguous")))

if __name__ == "__main__":
    main()
