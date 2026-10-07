"""Demandes de permis d'urbanisme — Région de Bruxelles-Capitale (service officiel NOVA, urban.brussels).
Catalogue : https://geobru-geonetwork.irisnet.be/geonetwork/srv/api/records/6d3208f6-aeee-11ee-80af-00090ffe0001
Seuls les GROS projets sont gardés (surface projetée ou mots-clés), pour ne pas noyer Radar Chantiers."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import httpx
from radar.common import clean, today, save

WFS = "https://geoservices-vector.irisnet.be/geoserver/Nova/wfs"
MIN_AREA_M2 = 1000
KEYWORDS = re.compile(
    r"\b(immeubles?|logements|appartements|[ée]cole|cr[èe]che|h[ôo]pital|maison de repos|bureaux|"
    r"centre sportif|piscine|parking|entrep[ôo]t|h[ôo]tel|r[ée]sidence|d[ée]molir et reconstruire|"
    r"reconstruction|ensemble|complexe|tour|appartementen|gebouw|school|kantoren|woningen)\b", re.I)
EXCLUDE = re.compile(r"\b(abattre|arbres?|ch[âa]ssis|enseigne|v[ée]randa|lucarne|terrasse|antenne|"
                     r"panneaux? photovolta|bomen|reclame)\b", re.I)


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _url(params):
    # forme vérifiée en ligne : ':', '/', quotes et '<' non encodés comme ci-dessous
    return WFS + "?" + "&".join(k + "=" + quote(v, safe=":/'=").replace("%20", "+") for k, v in params.items())


def fetch(days_back=7, count=2000, client=None):
    today_ = datetime.now(timezone.utc)
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "Nova:PlanningPermits",
              "outputFormat": "application/json", "count": str(count), "sortBy": "requestReceptionDate D",
              "cql_filter": f"requestReceptionDate<='{(today_ + timedelta(days=1)):%Y-%m-%d}'"}
    own = client is None
    client = client or httpx.Client(timeout=120.0)
    try:
        r = client.get(_url(params))
        r.raise_for_status()
        data = r.json()
    finally:
        if own:
            client.close()
    since = today_ - timedelta(days=days_back)
    out = []
    for f in data.get("features", []):
        p = f.get("properties") or {}
        d = _dt(p.get("requestReceptionDate"))
        if d and since <= d <= today_ + timedelta(days=1):    # écarte les dates erronées de la source
            out.append(p)
    return out


def area(p):
    return sum(float(v) for k, v in p.items() if k.endswith("ProjectedArea") and isinstance(v, (int, float)))


def is_big(p):
    obj = f"{p.get('caseFrenchObject') or ''} {p.get('caseDutchObject') or ''}"
    if area(p) >= MIN_AREA_M2:
        return True
    return bool(KEYWORDS.search(obj)) and not EXCLUDE.search(obj)


def to_fiche(p):
    ref = p.get("novaReference")
    if not ref or not is_big(p):
        return None
    obj = clean(p.get("caseFrenchObject") or p.get("caseDutchObject"), 200) or clean(p.get("caseSubTypeFrenchName"))
    street = " ".join(str(x) for x in (p.get("streetFrenchName"), p.get("streetNumberFrom")) if x)
    commune = p.get("addressMunicipalityFrenchName") or ""
    a = area(p)
    src = _url({"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "Nova:PlanningPermits",
                "outputFormat": "application/json", "cql_filter": f"novaReference='{ref}'"})
    d = str(p.get("requestReceptionDate") or "")[:10]
    return {
        "id": f"nova-{ref}", "source_type": "Permis", "nom": obj,
        "lieu": ", ".join(x for x in (street, f"{p.get('zipCode') or ''} {commune}".strip()) if x),
        "type": clean(p.get("caseSubTypeFrenchName"), 80), "mo": "", "etape": 1,
        "source": src, "verif": "vérifié", "verif_date": today(),
        "preuve": f"Demande de permis {ref} reçue le {d} (urban.brussels, service NOVA)"
                  + (f", surface projetée {a:.0f} m²" if a else "") + ".",
        "date_publication": d, "notes": f"Autorité : {p.get('managingAuthorityFrenchName') or '?'}"
                                        + (f" · statut : {p['caseStatusFrenchName']}" if p.get("caseStatusFrenchName") else ""),
    }


def run(days_back=7):
    items = fetch(days_back=days_back)
    fiches = [f for f in (to_fiche(p) for p in items) if f]
    new, total = save("permis_bruxelles", fiches, {"source": "urban.brussels NOVA (WFS)", "days_back": days_back,
                                                   "received": len(items), "kept": len(fiches)})
    print(f"[nova] {len(items)} demandes sur {days_back} j, {len(fiches)} gros projets, {new} nouveaux")
    return new
