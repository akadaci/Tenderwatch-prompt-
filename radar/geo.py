"""Géolocalisation par code postal ou nom de commune.
Source : GeoNames, codes postaux Belgique et Luxembourg (CC BY 4.0) — https://download.geonames.org/export/zip/
Précision : centre de la commune / du code postal, jamais l'adresse exacte du chantier."""
import csv, io, re, unicodedata, zipfile
from pathlib import Path
import httpx

CACHE = Path(__file__).resolve().parent.parent / ".cache"
URL = "https://download.geonames.org/export/zip/{cc}.zip"
_by_cp, _by_name = {}, {}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\(.*?\)", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _load():
    if _by_cp:
        return
    CACHE.mkdir(exist_ok=True)
    for cc in ("BE", "LU"):
        f = CACHE / f"{cc}.zip"
        if not f.exists():
            r = httpx.get(URL.format(cc=cc), timeout=60, follow_redirects=True)
            r.raise_for_status()
            f.write_bytes(r.content)
        with zipfile.ZipFile(f) as z:
            rows = csv.reader(io.TextIOWrapper(z.open(f"{cc}.txt"), encoding="utf-8"), delimiter="\t")
            for row in rows:
                # pays, code postal, nom, admin1, code1, admin2, code2, admin3, code3, lat, lon, précision
                cp, name, lat, lon = row[1], row[2], float(row[9]), float(row[10])
                key = f"{cc}-{cp}"
                _by_cp.setdefault(key, (lat, lon, name))
                for n in {norm(name), norm(row[5]) if cc == "LU" else ""} - {""}:
                    _by_name.setdefault(n, (lat, lon, name))


def locate(postcode=None, city=None, country="BE"):
    """(lat, lon, libellé, précision) ou None."""
    _load()
    cc = "LU" if str(country).upper() in ("LU", "LUX") else "BE"
    cp = re.sub(r"\D", "", str(postcode or ""))
    if cp and f"{cc}-{cp}" in _by_cp:
        lat, lon, name = _by_cp[f"{cc}-{cp}"]
        return round(lat, 4), round(lon, 4), name, "code postal"
    n = norm(city)
    for cand in (n, n.split(" ")[0] if n else ""):
        if cand and cand in _by_name:
            lat, lon, name = _by_name[cand]
            return round(lat, 4), round(lon, 4), name, "commune"
    return None
