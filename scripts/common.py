"""Shared helpers for the data-pull scripts: the Michiana county list and name matching."""
import os, re, tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
# state FIPS + county FIPS for the region (Indiana 18, Michigan 26)
COUNTIES = {"18141": "St. Joseph, IN", "18039": "Elkhart, IN", "18099": "Marshall, IN", "18091": "LaPorte, IN", "18085": "Kosciusko, IN",
            "18149": "Starke, IN", "18049": "Fulton, IN", "18087": "LaGrange, IN", "18113": "Noble, IN", "18183": "Whitley, IN",
            "26021": "Berrien, MI", "26027": "Cass, MI", "26159": "Van Buren, MI"}
SUFFIXES = r"\b(inc|incorporated|llc|l l c|corp|corporation|co|company|ltd|lp|llp|the|of|usa|us|group|holdings|intl|international|mfg|manufacturing|industries|enterprises|div|division|plant|plt)\b"

def norm(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    s = re.sub(SUFFIXES, " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def companies():
    out = []
    for n in sorted(os.listdir(P("companies"))):
        if n.endswith(".toml"):
            with open(P("companies", n), "rb") as fh:
                c = tomllib.load(fh)
            c["_id"] = re.sub(r"[^a-z0-9]+", "-", n[:-5].lower()).strip("-")
            out.append(c)
    return out

def matcher(cs):
    """Return match(name, city) -> company id, by normalized name, then by the first three words plus city."""
    exact, prefix = {}, {}
    for c in cs:
        n = norm(c["name"])
        exact.setdefault(n, c["_id"])
        prefix.setdefault((" ".join(n.split()[:3]), (c.get("city") or "").lower()), c["_id"])
    def match(name, city=""):
        n = norm(name)
        if n in exact:
            return exact[n]
        k = (" ".join(n.split()[:3]), (city or "").lower())
        return prefix.get(k)
    return match
