"""Bulletin des Adjudications (plateforme e-Procurement, SPF BOSA) → fiches Radar Chantiers.

Accès : le site public publicprocurement.be/bda utilise une API JSON avec un jeton anonyme.
La recherche est faite DEPUIS la page, dans un vrai navigateur (Chromium), comme un visiteur :
aucun identifiant n'est stocké. Volume volontairement faible (conditions d'utilisation : ne pas surcharger)."""
import asyncio, json, re
from datetime import datetime, timedelta, timezone
from radar.common import clean, today, save, DATA

BDA = "https://www.publicprocurement.be/bda"
API = "/api/sea/search/publications"
PAGE_SIZE = 100
MAX_PAGES = 30
CPV_KEEP = ("45", "44", "71")
NUTS = {"BE1": "Bruxelles", "BE21": "Anvers", "BE22": "Limbourg", "BE23": "Flandre-Orientale",
        "BE24": "Brabant flamand", "BE25": "Flandre-Occidentale", "BE31": "Brabant wallon", "BE32": "Hainaut",
        "BE33": "Liège", "BE34": "Luxembourg (prov.)", "BE35": "Namur", "LU": "Grand-Duché"}

JS_FETCH = """async ([api, body]) => {
  const r = await fetch(api, {method: 'POST', credentials: 'include',
    headers: {'Content-Type': 'application/json', 'Accept': 'application/json',
              'Authorization': 'Bearer ' + window.__twToken, 'BelGov-Trace-Id': crypto.randomUUID()},
    body: JSON.stringify(body)});
  return {status: r.status, text: await r.text()};
}"""


def txt(v, langs=("FR", "NL", "DE", "EN")):
    """[{language, text}] → texte dans la langue préférée."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return txt(v.get("names") or v.get("titles") or v.get("descriptions") or v.get("text") or "")
    if isinstance(v, list) and v:
        if all(isinstance(x, dict) and "language" in x for x in v):
            for l in langs:
                for x in v:
                    if str(x.get("language", "")).upper() == l and x.get("text"):
                        return x["text"]
            return v[0].get("text", "")
        return txt(v[0])
    return ""


def nuts_label(codes):
    out = []
    for c in codes or []:
        c = c if isinstance(c, str) else (c.get("code") if isinstance(c, dict) else "")
        for k in sorted(NUTS, key=len, reverse=True):
            if c and c.upper().startswith(k):
                out.append(NUTS[k]); break
    return ", ".join(dict.fromkeys(out))


def kind(p):
    """Sous-type eForms → nature de l'avis. Table officielle :
    https://docs.ted.europa.eu/eforms/1.13/schema/documents-forms-and-notices.html"""
    st = str(p.get("noticeSubType") or "").upper()
    if st in ("E1", "E2") or (st.isdigit() and 1 <= int(st) <= 9):
        return "prior"
    if st == "E3" or (st.isdigit() and 10 <= int(st) <= 24):
        return "contract"
    if st == "E4" or (st.isdigit() and 25 <= int(st) <= 37):
        return "award"
    if st in ("E5", "E6") or (st.isdigit() and 38 <= int(st) <= 40):
        return "other"                      # modification / clôture de contrat : écarté
    return "unknown"


def to_fiche(p):
    wid = p.get("publicationWorkspaceId")
    d = p.get("dossier") or {}
    cpvs = [str((p.get("cpvMainCode") or {}).get("code", ""))] + [str(c.get("code", "")) for c in p.get("cpvAdditionalCodes") or []]
    cpvs = [c[:8] for c in cpvs if c]
    k = kind(p)
    if not wid or k in ("other", "unknown") or not any(c.startswith(CPV_KEEP) for c in cpvs):
        return None
    etude = all(c.startswith("71") for c in cpvs if c.startswith(CPV_KEEP))
    etape = 1 if k == "prior" else (2 if k == "award" and etude else 5 if k == "award" else 1 if etude else 4)
    pub_date = str(p.get("publicationDate") or p.get("dispatchDate") or "")[:10]
    ref = d.get("referenceNumber") or d.get("number") or ""
    ted = p.get("publicationReferenceNumbersTED") or []
    org = txt((p.get("organisation") or {}).get("organisationNames") or p.get("organisationNames") or "")
    return {
        "id": f"bda-{wid}", "source_type": "BDA", "nom": clean(txt(d.get("titles")), 200),
        "lieu": nuts_label(p.get("nutsCodes")), "province": nuts_label(p.get("nutsCodes")).split(", ")[0],
        "mo": clean(org, 150), "etape": etape, "sur_ted": bool(p.get("tedPublished")),
        "source": f"https://www.publicprocurement.be/publication-workspaces/{wid}",
        "verif": "vérifié", "verif_date": today(),
        "preuve": f"Bulletin des Adjudications, réf. {ref or '?'} ({ {'prior': 'préinformation', 'contract': 'avis de marché', 'award': 'attribution'}[k]}, sous-type eForms {p.get('noticeSubType')}), publié le {pub_date}.",
        "date_publication": pub_date, "cpv": ",".join(dict.fromkeys(cpvs)),
        "ted_ref": ",".join(str(x) for x in ted) if ted else "",
        "notes": clean(txt(d.get("descriptions")), 300),
    }


async def fetch(days_back=7):
    from playwright.async_api import async_playwright
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    pubs, meta = [], {}
    async with async_playwright() as pw:
        br = await pw.chromium.launch()
        page = await br.new_page(locale="fr-BE")
        got = asyncio.get_event_loop().create_future()

        async def on_resp(r):
            if "openid-connect/token" in r.url and r.status == 200 and not got.done():
                try:
                    got.set_result((await r.json()).get("access_token"))
                except Exception as e:
                    got.set_exception(e)
        page.on("response", on_resp)
        await page.goto(BDA, wait_until="networkidle", timeout=90000)
        token = await asyncio.wait_for(got, 60)
        await page.evaluate("t => { window.__twToken = t }", token)
        for n in range(1, MAX_PAGES + 1):
            res = await page.evaluate(JS_FETCH, [API, {"includeOrganisationChildren": True, "page": n, "pageSize": PAGE_SIZE}])
            if res["status"] != 200:
                raise RuntimeError(f"BDA HTTP {res['status']} page {n} : {res['text'][:300]}")
            j = json.loads(res["text"])
            batch = j.get("publications", [])
            if n == 1:
                meta = {k: v for k, v in j.items() if k != "publications"}
            pubs += batch
            oldest = min((str(p.get("publicationDate") or p.get("dispatchDate") or "9999")[:10] for p in batch), default="")
            print(f"[bda] page {n} : {len(batch)} avis, plus ancien {oldest}")
            if len(batch) < PAGE_SIZE or (oldest and oldest < since):
                break
            await page.wait_for_timeout(1500)          # rythme lent volontaire
        await br.close()
    pubs = [p for p in pubs if str(p.get("publicationDate") or p.get("dispatchDate") or "")[:10] >= since]
    return pubs, meta


def run(days_back=7):
    pubs, meta = asyncio.run(fetch(days_back))
    # Échantillon brut pour contrôle de la conversion (petit, écrasé à chaque passage)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "_bda_controle.json").write_text(json.dumps({
        "meta": meta, "types": sorted({f"{p.get('publicationType')}|{p.get('noticeSubType')}|{p.get('natures')}" for p in pubs}),
        "exemples": pubs[:3], "exemple_attribution": [p for p in pubs if kind(p) == "award"][:1]}, ensure_ascii=False, indent=1)[:200000])
    fiches = [f for f in (to_fiche(p) for p in pubs) if f]
    new, total = save("bda", fiches, {"source": "Bulletin des Adjudications (e-Procurement)", "days_back": days_back,
                                     "received": len(pubs), "kept": len(fiches)})
    print(f"[bda] {len(pubs)} avis sur {days_back} j, {len(fiches)} dans le périmètre Fischer, {new} nouveaux")
    return new
