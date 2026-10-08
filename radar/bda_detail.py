"""Fiche détaillée des avis du BDA : adresse de l'acheteur (pour la carte), date limite, numéro BCE,
entreprise gagnante quand l'avis la contient. Lecture du XML eForms officiel joint à l'avis."""
import asyncio, json, re
import xml.etree.ElementTree as ET
from radar.common import DATA

CACHE_FILE = DATA / "bda_detail.json"
MAX_PER_RUN = 400


def _t(el, path):
    x = el.find(path) if el is not None else None
    return (x.text or "").strip() if x is not None and x.text else ""


def parse_xml(xml):
    out = {}
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    orgs = {}
    for o in root.iter():
        if o.tag.endswith("}Organization") and o.find(".//{*}Company") is not None:
            c = o.find(".//{*}Company")
            oid = _t(c, "./{*}PartyIdentification/{*}ID")
            addr = c.find("./{*}PostalAddress")
            orgs[oid] = {"nom": _t(c, "./{*}PartyName/{*}Name"), "rue": _t(addr, "./{*}StreetName"),
                         "ville": _t(addr, "./{*}CityName"), "cp": _t(addr, "./{*}PostalZone"),
                         "pays": _t(addr, "./{*}Country/{*}IdentificationCode"),
                         "bce": _t(c, "./{*}PartyLegalEntity/{*}CompanyID")}
    buyer_ids = [(_t(p, "./{*}Party/{*}PartyIdentification/{*}ID")) for p in root.iter() if p.tag.endswith("}ContractingParty")]
    buyer = next((orgs[i] for i in buyer_ids if i in orgs), None)
    if buyer:
        out["acheteur"] = buyer
    winners = []
    for tp in root.iter():
        if tp.tag.endswith("}TenderingParty"):
            for t in tp.iter():
                if t.tag.endswith("}Tenderer"):
                    i = _t(t, "./{*}ID")
                    if i in orgs and orgs[i]["nom"] not in [w["nom"] for w in winners]:
                        winners.append(orgs[i])
    if winners:
        out["gagnants"] = winners
    loc = [_t(a, "./{*}CountrySubentityCode") for a in root.iter() if a.tag.endswith("}RealizedLocation") for a in [a.find("./{*}Address")] if a is not None]
    out["nuts_execution"] = [x for x in loc if x]
    return out


async def fetch_details(ids):
    from radar.bosa import Session
    res = {}
    async with Session() as s:
        for wid in ids:
            try:
                d = await s.call(f"/api/dos/publication-workspaces/{wid}?includeDrafts=false")
            except Exception as e:
                res[wid] = {"erreur": str(e)[:200]}
                continue
            versions = d.get("versions") or []
            v = versions[-1] if versions else {}
            xml = (v.get("notice") or {}).get("xmlContent") or ""
            info = parse_xml(xml) if xml else {}
            info["date_limite"] = (v.get("submissionDeadline") or "")[:10]
            res[wid] = info
    return res


def run():
    cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    bda = json.loads((DATA / "bda.json").read_text())["records"]
    todo = [r["id"][4:] for r in bda if r["id"][4:] not in cache][:MAX_PER_RUN]
    if todo:
        cache.update(asyncio.run(fetch_details(todo)))
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")))
    print(f"[bda_detail] {len(todo)} fiches détaillées lues, {len(cache)} en cache")
    return len(todo)
