"""Appels d'offres où aucun document n'a été listé (vérifié le 08/10/2026) : pourquoi ?
1) liste des documents sans filtre de type ; 2) lien « documents du marché » dans l'avis eForms (BT-15).
Résultat : discovery/out/docs_probe.json"""
import asyncio, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radar.bosa import Session

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "discovery" / "out" / "docs_probe.json"
WIDS = []
d = json.loads((ROOT / "data" / "csc.json").read_text())
for w, v in d.items():
    if not v.get("documents_lus") and not v.get("sans_avis_de_marche") and not v.get("documents_ignores"):
        WIDS.append((v.get("via") or {}).get("wid") or w)
WIDS = WIDS[:6]


async def main():
    res = []
    async with Session(pause_ms=700) as s:
        for wid in WIDS:
            it = {"wid": wid}
            for nom, q in [("sans_filtre", ""), ("filtre_actuel", "&type=WORKSPACE&type=ESPD_REQUEST&type=SDI")]:
                try:
                    docs = await s.call(f"/api/dos/publication-workspaces/{wid}/documents?full=false{q}")
                    it[nom] = [{"type": x.get("type"), "nom": ((x.get("versions") or [{}])[-1].get("document") or {}).get("originalFileName")} for x in (docs or [])][:20]
                except Exception as e:
                    it[nom] = f"erreur {e}"[:200]
            try:
                ws = await s.call(f"/api/dos/publication-workspaces/{wid}?includeDrafts=false")
                xml = ((ws.get("versions") or [{}])[-1].get("notice") or {}).get("xmlContent") or ""
                it["uris"] = sorted(set(re.findall(r"<cbc:URI>([^<]+)</cbc:URI>", xml)))[:10]
                it["cles_workspace"] = list(ws.keys())[:30]
            except Exception as e:
                it["ws_erreur"] = str(e)[:200]
            res.append(it)
            OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))


asyncio.run(main())
