"""Les documents d'un marché ATTRIBUÉ restent-ils téléchargeables sur e-Procurement ?
Pour 15 avis d'attribution de travaux (BDA), on liste les documents et on tente le téléchargement du premier.
Résultat : discovery/out/attrib_probe.json"""
import asyncio, json, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from radar.bosa import Session
from radar.csc import find_url

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "discovery" / "out" / "attrib_probe.json"


async def main():
    bda = json.loads((ROOT / "data" / "bda.json").read_text())["records"]
    cibles = [r for r in bda if r["etape"] == 5 and (r.get("cpv") or "").startswith(("45", "44"))][:15]
    res = []
    async with Session(pause_ms=800) as s, httpx.AsyncClient(timeout=120, follow_redirects=True) as http:
        for r in cibles:
            wid = r["id"][4:]
            it = {"wid": wid, "nom": r["nom"][:120], "date": r.get("date")}
            try:
                ws = await s.call(f"/api/dos/publication-workspaces/{wid}?includeDrafts=false")
                it["versions"] = [(v.get("notice") or {}).get("noticeSubType") or (v.get("notice") or {}).get("formType") or "?" for v in (ws.get("versions") or [])] if isinstance(ws, dict) else str(ws)[:200]
                docs = await s.call(f"/api/dos/publication-workspaces/{wid}/documents?full=false&type=WORKSPACE&type=ESPD_REQUEST&type=SDI")
                noms = [((d.get("versions") or [{}])[-1].get("document") or {}).get("originalFileName") for d in (docs or [])]
                it["documents"] = noms
                for d in docs or []:
                    v = (d.get("versions") or [{}])[-1]
                    n = ((v.get("document") or {}).get("originalFileName") or "")
                    if "espd" in n.lower():
                        continue
                    info = await s.call(f"/api/dos/publication-workspace-document-versions/{v['id']}/download-url?unpublished=false")
                    url = find_url(info)
                    it["essai"] = {"document": n, "lien": bool(url)}
                    if url:
                        g = await http.get(url)
                        it["essai"].update({"http": g.status_code, "octets": len(g.content)})
                    break
            except Exception as e:
                it["erreur"] = f"{type(e).__name__}: {e}"[:300]
                it["trace"] = traceback.format_exc()[-600:]
            res.append(it)
            OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False)[:3000])


asyncio.run(main())
