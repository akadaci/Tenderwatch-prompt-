"""Collecte TED (avis européens) Belgique + Grand-Duché → fiches Radar Chantiers.

API officielle : POST https://api.ted.europa.eu/v3/notices/search (sans authentification)
Doc : https://docs.ted.europa.eu/api/latest/search.html — syntaxe : https://ted.europa.eu/en/help/search-browse
"""
import re
from datetime import datetime, timedelta, timezone
import httpx
from radar.common import clean, today, save

TED_API = "https://api.ted.europa.eu/v3/notices/search"
PAGE_MAX = 250
# Champs vérifiés dans la liste officielle des champs de recherche TED
SAFE_FIELDS = ["publication-number", "notice-title", "buyer-name", "buyer-country", "classification-cpv",
               "publication-date", "deadline-receipt-tender-date-lot", "notice-type",
               "estimated-value-lot", "estimated-value-cur-lot", "total-value", "total-value-cur",
               "organisation-name-tenderer", "organisation-identifier-tenderer"]
# Champs non confirmés : tentés d'abord, abandonnés automatiquement si TED répond 400
EXTRA_FIELDS = ["place-of-performance", "organisation-city-buyer"]
# CPV utiles à Fischer : 45 travaux, 44 matériaux/structures, 71 services d'architecture et d'ingénierie
CPV_KEEP = ("45", "44", "71")
LANGS = ("fra", "nld", "deu", "eng")


class TedError(Exception):
    pass


def _first(v):
    if isinstance(v, list):
        for x in v:
            r = _first(x)
            if r not in (None, ""):
                return r
        return None
    if isinstance(v, dict):
        low = {str(k).lower(): x for k, x in v.items()}
        for lang in LANGS:
            if lang in low:
                return _first(low[lang])
        for x in v.values():
            r = _first(x)
            if r not in (None, ""):
                return r
        return None
    return v


def _all(v):
    if isinstance(v, list):
        out = []
        for x in v:
            out += _all(x)
        return out
    if isinstance(v, dict):
        return _all(next(iter(v.values()))) if v else []
    return [v] if v not in (None, "") else []


def _date(v):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(_first(v) or ""))
    return m.group(1) if m else ""


def _num(v):
    try:
        return float(_first(v))
    except (TypeError, ValueError):
        return None


def be_number(values):
    """Premier numéro d'entreprise belge valide (contrôle : 97 - (8 chiffres mod 97))."""
    for x in _all(values):
        s = str(x).strip().upper()
        s = s[2:] if s.startswith("BE") else s
        if re.search(r"[A-Z]", s):
            continue
        d = re.sub(r"\D", "", s)
        d = "0" + d if len(d) == 9 else d
        if len(d) == 10 and d[0] in "01" and 97 - int(d[:8]) % 97 == int(d[8:]):
            return d
    return ""


def fetch(days_back=7, countries=("BEL", "LUX"), max_notices=3000, client=None):
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y%m%d")
    query = f"buyer-country IN ({' '.join(countries)}) AND publication-date >= {since}"
    fields = SAFE_FIELDS + EXTRA_FIELDS
    own = client is None
    client = client or httpx.Client(timeout=90.0)
    notices, page = [], 1
    try:
        while len(notices) < max_notices:
            body = {"query": query, "fields": fields, "page": page, "limit": PAGE_MAX,
                    "scope": "ALL", "paginationMode": "PAGE_NUMBER"}
            r = client.post(TED_API, json=body, headers={"Accept": "application/json"})
            if r.status_code == 400 and fields != SAFE_FIELDS:
                print(f"[ted] 400 avec champs étendus → champs sûrs. Réponse : {r.text[:300]}")
                fields = SAFE_FIELDS
                continue
            if r.status_code >= 400:
                raise TedError(f"TED HTTP {r.status_code} : {r.text[:500]}")
            data = r.json()
            if "notices" not in data:
                raise TedError(f"Réponse TED inattendue : clés {list(data)[:10]}")
            batch = data["notices"]
            notices += batch
            print(f"[ted] page {page} : {len(batch)} avis (total annoncé : {data.get('totalNoticeCount')})")
            if len(batch) < PAGE_MAX:
                break
            page += 1
    except httpx.HTTPError as e:
        raise TedError(f"TED inaccessible : {type(e).__name__}: {e}") from e
    finally:
        if own:
            client.close()
    return notices[:max_notices], fields


def to_fiche(raw):
    """Avis TED → fiche Radar Chantiers, ou None si hors périmètre Fischer."""
    pub = str(_first(raw.get("publication-number")) or "")
    if not pub:
        return None
    cpvs = [str(c)[:8] for c in _all(raw.get("classification-cpv"))]
    if not any(c.startswith(CPV_KEEP) for c in cpvs):
        return None
    ntype = str(_first(raw.get("notice-type")) or "").lower()
    award = ntype.startswith(("can", "veat")) or "award" in ntype
    services_etude = all(c.startswith("71") for c in cpvs if c.startswith(CPV_KEEP))
    winner = clean(_first(raw.get("organisation-name-tenderer")), 150)
    if ntype.startswith("pin"):
        etape = 1
    elif award and services_etude:
        etape = 2                       # marché d'auteur de projet attribué → bureau d'études connu
    elif award:
        etape = 5
    elif services_etude:
        etape = 1                       # étude mise en concurrence → projet repéré
    else:
        etape = 4
    value = _num(raw.get("total-value")) or _num(raw.get("estimated-value-lot"))
    cur = str(_first(raw.get("total-value-cur")) or _first(raw.get("estimated-value-cur-lot")) or "")
    country = str(_first(raw.get("buyer-country")) or "")
    city = clean(_first(raw.get("organisation-city-buyer")), 80)
    deadline = _date(raw.get("deadline-receipt-tender-date-lot"))
    url = f"https://ted.europa.eu/fr/notice/{pub}/html"
    f = {
        "id": f"ted-{pub}", "source_type": "TED", "nom": clean(_first(raw.get("notice-title")), 200),
        "lieu": ", ".join(x for x in (city, {"BEL": "Belgique", "LUX": "Luxembourg"}.get(country, country)) if x),
        "mo": clean(_first(raw.get("buyer-name")), 150), "etape": etape,
        "entreprise": "" if services_etude else (winner if award else ""),
        "be": winner if (award and services_etude) else "",
        "montant": f"{value:.0f}" if value and (not cur or cur == "EUR") else "",
        "source": url, "verif": "vérifié", "verif_date": today(),
        "preuve": f"Avis TED n° {pub} ({ntype or 'type inconnu'}), publié le {_date(raw.get('publication-date'))}.",
        "date_publication": _date(raw.get("publication-date")), "date_limite": deadline,
        "cpv": ",".join(dict.fromkeys(cpvs)), "pays": country,
        "bce": be_number(raw.get("organisation-identifier-tenderer")) if award else "",
    }
    if cur and cur != "EUR" and value:
        f["notes"] = f"Montant : {value:.0f} {cur}"
    if deadline:
        f["action"] = "Vérifier la prescription avant la date limite"
        f["date_action"] = deadline
    return f


def run(days_back=7):
    raws, fields = fetch(days_back=days_back)
    fiches = [f for f in (to_fiche(r) for r in raws) if f]
    new, total = save("ted", fiches, {"source": "TED API v3", "fields": fields, "days_back": days_back,
                                     "received": len(raws), "kept": len(fiches)})
    print(f"[ted] {len(raws)} avis reçus, {len(fiches)} dans le périmètre Fischer, {new} nouveaux, {total} au total")
    return new
