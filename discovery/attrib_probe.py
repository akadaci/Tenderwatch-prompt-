"""Un avis d'attribution BDA a son propre espace, sans documents (vérifié le 08/10/2026).
Retrouver l'avis de MARCHÉ d'origine (même procedureId) pour lire son cahier des charges.
1) quels filtres l'API de recherche accepte-t-elle ? 2) que fait la recherche de la page web ?
Résultat : discovery/out/attrib_probe2.json"""
import asyncio, json, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radar.bosa import Session

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "discovery" / "out" / "attrib_probe2.json"
API = "/api/sea/search/publications"
BASE = {"includeOrganisationChildren": True, "page": 1, "pageSize": 25}
res = {"essais": [], "ui": []}


def items(r):
    return (r or {}).get("publications") or [] if isinstance(r, dict) else []


def save():
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))


async def main():
    async with Session(pause_ms=700) as s:
        # requêtes de la page web quand on tape dans la recherche
        reqs = []
        s.page.on("request", lambda q: reqs.append({"url": q.url, "body": q.post_data}) if "/api/sea/" in q.url else None)
        awards = []
        for p in range(1, 6):
            r = await s.call(API, "POST", {**BASE, "page": p, "pageSize": 100})
            res.setdefault("cles_reponse", list(r.keys()) if isinstance(r, dict) else str(r)[:200])
            for x in items(r):
                st = str(x.get("noticeSubType") or "")
                if st in {str(i) for i in range(29, 38)} and (x.get("cpvMainCode") or {}).get("code", "").startswith("45"):
                    awards.append(x)
            if len(awards) >= 6:
                break
        res["awards"] = [{"pid": a.get("procedureId"), "dossier": (a.get("dossier") or {}).get("number"),
                          "ref": a.get("referenceNumber"), "wid": a.get("publicationWorkspaceId"),
                          "titre": ((a.get("dossier") or {}).get("titles") or [{}])[0].get("text", "")[:100]} for a in awards[:6]]
        save()
        for a in res["awards"][:4]:
            for nom, extra in [("procedureId", {"procedureId": a["pid"]}), ("procedureIds", {"procedureIds": [a["pid"]]}),
                               ("terms", {"terms": a["dossier"]}), ("term", {"term": a["dossier"]}),
                               ("searchText", {"searchText": a["dossier"]}), ("dossierNumber", {"dossierNumber": a["dossier"]}),
                               ("referenceNumber", {"referenceNumber": a["dossier"]}), ("query", {"query": a["dossier"]})]:
                it = {"award": a["dossier"], "filtre": nom}
                try:
                    r = await s.call(API, "POST", {**BASE, **extra})
                    xs = items(r)
                    it.update({"total": (r or {}).get("totalCount") if isinstance(r, dict) else None, "n": len(xs),
                               "meme_procedure": sum(1 for x in xs if x.get("procedureId") == a["pid"]),
                               "trouves": [{"st": x.get("noticeSubType"), "wid": x.get("publicationWorkspaceId"), "ref": x.get("referenceNumber")}
                                           for x in xs if x.get("procedureId") == a["pid"]][:5]})
                except Exception as e:
                    it["erreur"] = f"{type(e).__name__}: {e}"[:300]
                res["essais"].append(it); save()
        # recherche via l'interface : saisir le n° de dossier dans le champ de recherche
        try:
            a = res["awards"][0]
            inp = s.page.locator("input[type=search], input[type=text]").first
            await inp.fill(a["dossier"]); await inp.press("Enter")
            await s.page.wait_for_timeout(6000)
            res["ui"] = reqs[-6:]
            await s.page.screenshot(path=str(ROOT / "discovery" / "out" / "bda_search_ui.png"))
        except Exception as e:
            res["ui_erreur"] = traceback.format_exc()[-800:]
        save()
        # documents de l'avis de marché d'origine, si trouvé
        for it in res["essais"]:
            for t in it.get("trouves", []):
                if str(t["st"]) in {str(i) for i in range(10, 25)}:
                    try:
                        d = await s.call(f"/api/dos/publication-workspaces/{t['wid']}/documents?full=false&type=WORKSPACE&type=ESPD_REQUEST&type=SDI")
                        t["documents"] = [((x.get("versions") or [{}])[-1].get("document") or {}).get("originalFileName") for x in (d or [])][:15]
                    except Exception as e:
                        t["documents_erreur"] = str(e)[:200]
        save()


asyncio.run(main())
