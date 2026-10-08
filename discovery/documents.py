"""Découverte : les documents d'un marché (cahier spécial des charges) sont-ils accessibles sans compte ?
Ouvre 3 avis du Bulletin des Adjudications dans Chromium, enregistre les appels de données,
clique sur l'onglet des documents s'il existe et tente un téléchargement."""
import asyncio, base64, json, re
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
IDS = ["c20e76bf-b6d8-42fd-bea0-2c8c1b3bede5", "6ef05f03-6dd2-46da-9838-208ed14f9fff", "6a378623-2691-4f6f-a519-6cd2466ae7a1"]


async def main():
    from playwright.async_api import async_playwright
    res = {"pages": []}
    async with async_playwright() as p:
        br = await p.chromium.launch()
        ctx = await br.new_context(locale="fr-BE", accept_downloads=True)
        page = await ctx.new_page()
        reqs = []

        async def on_resp(r):
            if r.request.resource_type in ("xhr", "fetch"):
                e = {"url": r.url, "method": r.request.method, "status": r.status, "ctype": r.headers.get("content-type", ""),
                     "post": (r.request.post_data or "")[:800]}
                if "json" in e["ctype"] and "token" not in r.url:
                    try:
                        e["body"] = (await r.text())[:5000]
                    except Exception:
                        pass
                reqs.append(e)
        page.on("response", on_resp)
        token = {}
        page.on("response", lambda r: asyncio.ensure_future(_tok(r, token)))
        for i, wid in enumerate(IDS):
            info = {"id": wid}
            try:
                await page.goto(f"https://www.publicprocurement.be/publication-workspaces/{wid}", wait_until="networkidle", timeout=90000)
                await page.wait_for_timeout(4000)
                info["url"] = page.url
                info["text"] = (await page.inner_text("body"))[:6000]
                await page.screenshot(path=str(OUT / f"doc_page_{i}.png"), full_page=True)
                for label in ("Documents", "Documenten", "Dokumente"):
                    loc = page.get_by_text(label, exact=True)
                    if await loc.count():
                        await loc.first.click(); await page.wait_for_timeout(4000)
                        info["clicked"] = label
                        info["text_docs"] = (await page.inner_text("body"))[:6000]
                        await page.screenshot(path=str(OUT / f"doc_tab_{i}.png"), full_page=True)
                        break
            except Exception as e:
                info["error"] = f"{type(e).__name__}: {e}"
            res["pages"].append(info)
        # Tentative de téléchargement : premier appel de l'API dont l'URL évoque un document/fichier
        cands = [r["url"] for r in reqs if re.search(r"document|file|download|attachment", r["url"], re.I)]
        res["doc_api_candidates"] = sorted(set(cands))[:40]
        res["requests"] = reqs
        await br.close()
    (OUT / "documents.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("[documents] pages:", len(res["pages"]), "requêtes:", len(res["requests"]), "candidats:", len(res["doc_api_candidates"]))


async def _tok(r, box):
    if "openid-connect/token" in r.url and r.status == 200:
        try:
            box["t"] = (await r.json()).get("access_token")
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        import traceback
        (OUT / "documents.json").write_text(json.dumps({"exception": traceback.format_exc()}, ensure_ascii=False))
