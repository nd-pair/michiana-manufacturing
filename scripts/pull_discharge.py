#!/usr/bin/env python3
"""Water permits and discharge reports for plants in the region, from EPA ECHO (Clean Water Act; no key).
Writes data/discharge.json, shown in the Materials & recovery tab (Aqueous) and on company cards.

    python3 scripts/pull_discharge.py
    python3 scripts/pull_discharge.py --rematch   # only match the saved permits to company files again

- Permits in effect, by county (ECHO cwa_rest_services): wastewater discharge permits (NPDES individual and
  general permits, for plants that discharge to a river or ditch), industrial stormwater permits, and
  industrial-user (sewer-use) permits that a city sewer utility or IDEM issued and entered in EPA's system.
  Construction stormwater, biosolids and sewer plants (POTWs) are left out. Sewer-use permits are listed only
  where the issuer reports them: Michigan City, La Porte, Plymouth, Bremen, Goshen and IDEM's own, not South
  Bend, Elkhart, Mishawaka or Warsaw.
- Discharge reports (ECHO Water Pollutant Loading Tool, dmr_rest_services, the latest full year): for each
  discharge permit, the average wastewater flow and the pounds of each reported pollutant.
Each permit is matched to a company file like the EPA waste data (scripts/pull_waste.py: by hand in
data/waste_matches.toml, then street address, then name and city, then a nearby shared name word).
"""
import datetime, json, sys, time, urllib.request
from common import P, COUNTIES
from pull_waste import UA, company_index

ECHO = "https://echodata.epa.gov/echo/"
COLS = {"SourceID": 2, "CWPName": 1, "CWPStreet": 3, "CWPCity": 4, "CWPState": 5, "CWPZip": 7, "FacLat": 26, "FacLong": 27,
        "CWPNAICSCodes": 24, "CWPFacilityTypeIndicator": 30, "CWPPermitTypeDesc": 56, "CWPEffectiveDate": 59,
        "CWPExpirationDate": 61, "PermitComponents": 63, "CWPDateLastInspection": 68, "CWPSNCStatus": 100}

def get(path, tries=3):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(ECHO + path, headers=UA), timeout=180).read())["Results"]
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5)

def kind(f):
    """discharge (individual or general NPDES permit), stormwater (industrial), sewer (industrial user), or None to skip."""
    t, comp, pid = f.get("CWPPermitTypeDesc") or "", f.get("PermitComponents") or "", f["SourceID"]
    if f.get("CWPFacilityTypeIndicator") == "POTW" or "Construction Stormwater" in comp or "Biosolids" in comp or "Associated" in t:
        return None
    if "IU Permit" in t:
        return "sewer"
    if "Industrial Stormwater" in comp or pid[:4] in ("INRM", "MIS2", "MIS3", "MIS4"):
        return "stormwater"
    if "NPDES" in t or "General Permit" in t:
        return "discharge"
    return None

def permits():
    out = []
    cols = ",".join(str(v) for v in COLS.values())
    for fips in COUNTIES:
        r = get("cwa_rest_services.get_facilities?output=JSON&p_fips=%s&p_pstat=EFF" % fips)
        n, page = int(r.get("QueryRows") or 0), 1
        while (page - 1) * 5000 < n:
            for f in get("cwa_rest_services.get_qid?output=JSON&qid=%s&pageno=%d&qcolumns=%s" % (r["QueryID"], page, cols)).get("Facilities", []):
                k = kind(f)
                if not k:
                    continue
                try:
                    lat, lon = float(f["FacLat"]), float(f["FacLong"])
                except (TypeError, ValueError):
                    lat = lon = None
                out.append({"id": f["SourceID"], "kind": k, "name": f["CWPName"], "street": f.get("CWPStreet") or "",
                            "city": (f.get("CWPCity") or "").title(), "state": f.get("CWPState"), "zip": (f.get("CWPZip") or "")[:5],
                            "county": fips, "lat": lat, "lon": lon, "naics": (f.get("CWPNAICSCodes") or "").split(",")[0].strip(),
                            "type": f.get("CWPPermitTypeDesc"), "effective": f.get("CWPEffectiveDate"), "expires": f.get("CWPExpirationDate"),
                            "inspected": f.get("CWPDateLastInspection"), "snc": f.get("CWPSNCStatus")})
            page += 1
    return out

def loads(pid, year):
    """Average wastewater flow (million gallons a day) and pounds of each pollutant reported in the year."""
    rows = get("dmr_rest_services.get_custom_data_annual?output=JSON&p_year=%d&p_permit_id=%s" % (year, pid)).get("Results") or []
    num = lambda v: float(str(v).replace(",", "")) if v not in (None, "", "--") else 0.0
    flow = max((num(r.get("AvgWastewaterFlow")) for r in rows), default=0.0)
    lb = {}
    for r in rows:
        v = num(r.get("PollutantLoad"))
        if v > 0 and r.get("ParameterDesc"):
            lb[r["ParameterDesc"]] = lb.get(r["ParameterDesc"], 0) + v
    return {"flow_mgd": round(flow, 4) or None, "lb": {k: round(v, 1) for k, v in sorted(lb.items(), key=lambda kv: -kv[1])}}

def keep(p):
    """Plants worth listing: matched to a company file, holding a sewer-use permit, or in manufacturing,
    wholesale scrap or waste treatment by NAICS."""
    n = p["naics"]
    return p.get("company") or p["kind"] == "sewer" or n[:2] in ("31", "32", "33") or n[:4] in ("4239", "5629")

def main():
    path = P("data", "discharge.json")
    try:
        out = json.load(open(path))
    except FileNotFoundError:
        out = {}
    find = company_index()
    match = lambda p: find(p["name"], p["street"], p["city"], p["lat"], p["lon"], p["id"])
    if "--rematch" in sys.argv:
        for p in out.get("permits", []):
            p["company"] = match(p)
        json.dump(out, open(path, "w"), indent=1, sort_keys=True)
        print("rematched: %d of %d permits with a company file" % (sum(1 for p in out.get("permits", []) if p["company"]), len(out.get("permits", []))))
        return
    ps = permits()
    for p in ps:
        p["company"] = match(p)
    ps = [p for p in ps if keep(p)]
    # the latest full year, unless it has clearly fewer reports than the year before (still being entered)
    year = datetime.date.today().year - 1
    test = [p for p in ps if p["id"][2:4] == "00"] or [p for p in ps if p["kind"] == "discharge"]
    if sum(1 for p in test if loads(p["id"], year)["lb"]) < 0.8 * sum(1 for p in test if loads(p["id"], year - 1)["lb"]):
        year -= 1
    for p in ps:
        if p["kind"] in ("discharge", "stormwater"):
            p.update(loads(p["id"], year))
    ps.sort(key=lambda p: (p["kind"], -(p.get("flow_mgd") or 0), p["name"]))
    out = {"permits": ps, "dmr_year": year, "pulled": datetime.date.today().isoformat(),
           "source": "U.S. EPA ECHO: Clean Water Act permits (ICIS-NPDES) and the Water Pollutant Loading Tool"}
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    by = {}
    for p in ps:
        by[p["kind"]] = by.get(p["kind"], 0) + 1
    print("wrote data/discharge.json: %s permits (%s); %d matched to a company file; discharge reports for %d"
          % (len(ps), ", ".join("%s %d" % kv for kv in sorted(by.items())), sum(1 for p in ps if p["company"]), year))

if __name__ == "__main__":
    main()
