"""Which local companies could supply the parts of a humanoid robot, from data/humanoid.toml.

Used by build.py. A company matches a component by NAICS prefix or by a pattern in its name,
products and description, unless an exclude pattern sits within 25 characters of the match or its
NAICS code is excluded; company files can add (`humanoid`) or remove (`humanoid_not`) components.
"""
import re, tomllib
from common import P

def load():
    spec = tomllib.load(open(P("data", "humanoid.toml"), "rb"))
    for c in spec["component"]:
        c["_pat"] = [re.compile(p, re.I) for p in c.get("patterns", [])]
        c["_ex"] = [re.compile(p, re.I) for p in c.get("exclude", [])]
    return spec

def infer(spec, text, naics):
    out = []
    for c in spec["component"]:
        if any(naics.startswith(x) for x in c.get("exclude_naics", [])):
            continue
        hit = any(naics.startswith(x) for x in c.get("naics", []))
        for p in c["_pat"]:
            if hit:
                break
            for m in p.finditer(text):
                near = text[max(0, m.start() - 25):m.end() + 25]
                if not any(e.search(near) for e in c["_ex"]):
                    hit = True; break
        if hit:
            out.append(c["id"])
    return out

FUNDING = re.compile(r"\b(robot\w*|autonom\w*|actuat\w*|servo\w*|exoskeleton\w*|prosthe\w*|haptic\w*|tactile|lidar|machine vision|"
                     r"unmanned|drones?|motors?\b(?! home| coach| vehicle)|sensors?|sensing|manipulat\w*|gripp\w*|mechatronic\w*|legged|humanoid\w*)", re.I)

def funding(events):
    """Federal awards of $250k+ and SBIR/STTR awards on the timeline whose titles mention robotics, actuation or sensing, by year."""
    years = {}
    for e in events:
        if e.get("kind") in ("federal", "sbir") and FUNDING.search(e.get("title", "")):
            y = years.setdefault(e["date"][:4], {"amount": 0, "n": 0})
            y["amount"] += e.get("amount") or 0; y["n"] += 1
    return {y: {"amount": round(v["amount"]), "n": v["n"]} for y, v in sorted(years.items())}

def coverage(spec, companies):
    """Per component: distinct local supplier groups, inferred and confirmed; and the cost shares covered."""
    comp = {c["id"]: {"all": set(), "confirmed": set()} for c in spec["component"]}
    for o in companies:
        for k in o.get("hum", []):
            comp[k]["all"].add(o["group"])
            if o.get("hum_ev") == "confirmed":
                comp[k]["confirmed"].add(o["group"])
    cost = {c["id"]: c["cost"] for c in spec["component"]}
    for c in spec["component"]:   # build-to-print parts: any capable contract shop is available
        comp[c["id"]]["available"] = comp[c["id"]]["all"] if c.get("build_to_print") else comp[c["id"]]["confirmed"]
    share = lambda key, lo, hi=10**9: sum(cost[k] for k, v in comp.items() if lo <= len(v[key]) <= hi)
    return {"two_plus": share("all", 2), "one": share("all", 1, 1), "available_two_plus": share("available", 2), "confirmed_two_plus": share("confirmed", 2),
            "gaps": sum(1 for v in comp.values() if not v["all"]), "components": len(comp),
            "suppliers": len({o["group"] for o in companies if o.get("hum")})}
