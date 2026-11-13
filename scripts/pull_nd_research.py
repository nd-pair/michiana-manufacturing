#!/usr/bin/env python3
"""Physical-AI research awards to the University of Notre Dame, from public federal data.

    python3 scripts/pull_nd_research.py        # writes data/nd_research.json

Every grant, cooperative agreement and contract to the University of Notre Dame du Lac since
FY2016, and its subawards on other institutions' awards, are read from USAspending.gov (all agencies:
NSF, NIH, DoD and DARPA, DOE, NASA, ...) and
kept when its title or description is about physical AI: robots, autonomy, actuators, prosthetics
and exoskeletons, haptics, drones, legged or humanoid systems, embodied or physical AI, robotic
manufacturing, in its title or at least three times in its description. NSF awards get their principal investigators from the NSF Award Search API.
Amounts are obligations recorded so far. The topic rules are in TOPICS below.
"""
import datetime, json, re, time, urllib.request
from common import P

UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)", "Content-Type": "application/json"}
SINCE = "2015-10-01"
CORE = re.compile(r"\b(robot\w*|humanoid\w*|exoskelet\w*|prosthe\w*|haptic\w*|tactile|legged|bipedal|biped|teleoperat\w*|"
                  r"autonomous (systems?|vehicles?|robots?|agents?|navigation|driving|aircraft|vessels?|machines?)|self-driving|unmanned|drones?|uavs?|uas|"
                  r"embodied (ai|intelligence|agents?|robots?)|physical ai|soft robot\w*|human-robot|motion planning|mechatronic\w*|gripp\w*|dexterous|swarm robot\w*)\b", re.I)
TOPICS = [
    ("Robots and manipulation", r"\b(robot\w*|manipulat\w*|gripp\w*|dexterous|humanoid\w*|legged|locomotion|teleoperat\w*|human-robot|motion planning)\b"),
    ("Autonomy and drones", r"\b(autonom\w*|self-driving|unmanned|drones?|uavs?|uas|swarm\w*)\b"),
    ("Prosthetics, exoskeletons and rehabilitation", r"\b(prosthe\w*|exoskelet\w*|orthos\w*|orthotic\w*|rehabilitat\w*|assistive)\b"),
    ("Sensing, haptics and actuation", r"\b(haptic\w*|tactile|actuat\w*|sensor\w*|soft robot\w*|mechatronic\w*)\b"),
    ("Manufacturing and cyber-physical systems", r"\b(manufactur\w*|welding|machining|additive|cyber-physical|factory|industrial)\b"),
]

def post(url, body):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(), headers=UA), timeout=120))

def awards(codes):
    out, page = [], 1
    while True:
        r = post("https://api.usaspending.gov/api/v2/search/spending_by_award/", {
            "filters": {"recipient_search_text": ["University of Notre Dame"], "award_type_codes": codes,
                        "time_period": [{"start_date": SINCE, "end_date": datetime.date.today().isoformat()}]},
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Awarding Sub Agency", "Funding Sub Agency",
                       "Start Date", "End Date", "Description", "generated_internal_id"],
            "limit": 100, "page": page, "sort": "Award Amount", "order": "desc"})
        out += r.get("results", [])
        if not r.get("page_metadata", {}).get("hasNext"):
            return out
        page += 1; time.sleep(0.3)

def subawards(codes):
    """Notre Dame's share of other institutions' awards (USAspending subaward reports)."""
    out, page = [], 1
    while True:
        r = post("https://api.usaspending.gov/api/v2/search/spending_by_award/", {"subawards": True,
            "filters": {"recipient_search_text": ["University of Notre Dame"], "award_type_codes": codes,
                        "time_period": [{"start_date": SINCE, "end_date": datetime.date.today().isoformat()}]},
            "fields": ["Sub-Award ID", "Sub-Awardee Name", "Sub-Award Amount", "Sub-Award Date", "Sub-Award Description",
                       "Prime Award ID", "Prime Recipient Name", "Awarding Agency", "Awarding Sub Agency", "prime_award_generated_internal_id"],
            "limit": 100, "page": page})
        out += r.get("results", [])
        if not r.get("page_metadata", {}).get("hasNext"):
            return out
        page += 1; time.sleep(0.3)

def nsf_pi(award_id):
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(
            "https://api.nsf.gov/services/v1/awards/%s.json?printFields=piFirstName,piLastName,title" % award_id, headers=UA), timeout=60))
        a = (r.get("response", {}).get("award") or [{}])[0]
        return " ".join(x for x in (a.get("piFirstName"), a.get("piLastName")) if x), a.get("title", "")
    except Exception:
        return "", ""

SMALL = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with"}
def tidy(t):
    """All-capital titles (contracts, subawards) in title case, keeping acronyms such as NRI, UAV, NSF."""
    t = re.sub(r'^TAS::.*?::TAS\s*"?|"$', "", t or "").strip()   # Treasury account prefix on some DoD awards
    if not t or t != t.upper():
        return t
    words = []
    for i, w in enumerate(t.split()):
        core = w.strip(":,;()\"")
        if core in ("NRI", "UAV", "UAVS", "UAS", "NSF", "NASA", "DOD", "CPS", "AI", "DDAS", "II", "III", "US", "U.S."):
            words.append(w if core != "UAVS" else w.replace("UAVS", "UAVs"))
        elif i and w.lower() in SMALL and not words[-1].endswith(":"):
            words.append(w.lower())
        else:
            words.append(w[:1] + w[1:].lower())
    return " ".join(words)

def main():
    rows = awards(["02", "03", "04", "05"]) + awards(["A", "B", "C", "D"])
    rows = [r for r in rows if "NOTRE DAME" in (r.get("Recipient Name") or "").upper()]
    keep = []
    for r in rows:
        text = r.get("Description") or ""
        head = re.split(r"\s+-\s+|\s+-(?=[A-Z])", text, maxsplit=1)[0]   # "TITLE -ABSTRACT" or "TITLE - PROJECT ABSTRACT"
        # physical AI in the title, or a recurring theme of the description (three mentions)
        if not (CORE.search(head) or len(CORE.findall(text)) >= 3):
            continue
        agency, sub = r.get("Awarding Agency") or "", r.get("Awarding Sub Agency") or ""
        aid = (r.get("Award ID") or "").strip()
        title = head.strip() if agency == "National Science Foundation" else text.strip()
        pi = ""
        if agency == "National Science Foundation" and re.fullmatch(r"\d{7}", aid):
            pi, t = nsf_pi(aid); title = t or title; time.sleep(0.2)
        topics = [name for name, rx in TOPICS if re.search(rx, text, re.I)]
        keep.append({"id": aid, "title": tidy(title[:240].strip()), "agency": agency, "sub_agency": sub, "funding_sub_agency": r.get("Funding Sub Agency") or "",
                     "amount": round(r.get("Award Amount") or 0), "start": r.get("Start Date") or "", "end": r.get("End Date") or "", "pi": pi,
                     "topics": topics or ["Robots and manipulation"], "url": "https://www.usaspending.gov/award/%s" % r.get("generated_internal_id", ""),
                     "kind": "contract" if (r.get("Award ID") or "")[:2].isalpha() and agency != "National Science Foundation" and not re.fullmatch(r"\d+", aid) else "grant"})
    # subawards: one entry per subaward (reports repeat with each modification; keep the largest amount)
    subs = {}
    for r in subawards(["02", "03", "04", "05"]) + subawards(["A", "B", "C", "D"]):
        if "NOTRE DAME" not in (r.get("Sub-Awardee Name") or "").upper():
            continue
        text = (r.get("Sub-Award Description") or "").replace("STATEMENT OF WORK", "").strip()
        if not (CORE.search(text[:200]) or len(CORE.findall(text)) >= 3):
            continue
        key = (r.get("Sub-Award ID"), r.get("Prime Award ID"))
        if key in subs and subs[key]["amount"] >= (r.get("Sub-Award Amount") or 0):
            continue
        topics = [name for name, rx in TOPICS if re.search(rx, text, re.I)]
        subs[key] = {"id": r.get("Sub-Award ID") or "", "title": tidy(re.sub(r"\s+", " ", text)[:240]), "agency": r.get("Awarding Agency") or "",
                     "sub_agency": r.get("Awarding Sub Agency") or "", "funding_sub_agency": "", "amount": round(r.get("Sub-Award Amount") or 0),
                     "start": r.get("Sub-Award Date") or "", "end": "", "pi": "", "topics": topics or ["Robots and manipulation"],
                     "url": "https://www.usaspending.gov/award/%s" % r.get("prime_award_generated_internal_id", ""), "kind": "subaward",
                     "via": (r.get("Prime Recipient Name") or "").title()}
    keep += list(subs.values())
    keep.sort(key=lambda a: a["start"], reverse=True)
    json.dump({"source": "USAspending.gov (all agencies, grants and contracts to the University of Notre Dame du Lac since FY2016); NSF Award Search for investigators",
               "pulled": datetime.date.today().isoformat(), "scanned": len(rows), "subawards_kept": len(subs), "awards": keep}, open(P("data", "nd_research.json"), "w"), indent=0)
    tot = sum(a["amount"] for a in keep)
    print("scanned %d Notre Dame prime awards; %d physical-AI awards (%d of them subawards), $%.1fM" % (len(rows), len(keep), len(subs), tot / 1e6))

if __name__ == "__main__":
    main()
