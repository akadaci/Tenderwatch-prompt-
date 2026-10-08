"""Documents hébergés sur 3P (cloud.3p.eu) : accessibles sans compte ?
Ouvre le lien de l'avis comme un visiteur : choix du français, cookies acceptés, puis relevé de la page
(liens, boutons, formulaires) et tentative de téléchargement du premier document.
Résultat : discovery/out/p3_probe.json + captures p3_*.png"""
import asyncio, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "discovery" / "out" / "p3_probe.json"
URLS = ["https://cloud.3p.eu/Downloads/1/1221/69/2026", "https://cloud.3p.eu/Downloads/1/1377/LG/2026"]


async def main():
    from playwright.async_api import async_playwright
    res = []
    async with async_playwright() as p:
        br = await p.chromium.launch()
        for i, url in enumerate(URLS):
            it = {"url": url, "etapes": []}
            ctx = await br.new_context(locale="fr-BE", accept_downloads=True)
            pg = await ctx.new_page()
            reqs = []
            pg.on("response", lambda r: reqs.append({"url": r.url[:200], "status": r.status, "type": r.headers.get("content-type", "")[:60]}))
            try:
                await pg.goto(url, wait_until="networkidle", timeout=60000)
                await pg.screenshot(path=str(ROOT / "discovery" / "out" / f"p3_{i}_a.png"))
                for txt in ["français (Belgique)", "Français", "français"]:
                    loc = pg.get_by_text(txt, exact=False).first
                    if await loc.count():
                        await loc.click(); await pg.wait_for_load_state("networkidle"); it["etapes"].append("langue " + txt); break
                for txt in ["Submit", "Accepter", "OK", "J'accepte"]:
                    loc = pg.get_by_role("button", name=txt)
                    if await loc.count():
                        await loc.first.click(); await pg.wait_for_timeout(1500); it["etapes"].append("cookies " + txt); break
                await pg.wait_for_timeout(2000)
                await pg.screenshot(path=str(ROOT / "discovery" / "out" / f"p3_{i}_b.png"), full_page=True)
                it["titre"] = await pg.title()
                it["texte"] = (await pg.inner_text("body"))[:3000]
                it["liens"] = await pg.eval_on_selector_all("a", "as => as.slice(0,80).map(a => [a.innerText.trim().slice(0,80), a.href.slice(0,200)])")
                it["champs"] = await pg.eval_on_selector_all("input,select,button", "as => as.slice(0,60).map(a => [a.tagName, a.type||'', a.name||a.id||'', (a.value||a.innerText||'').slice(0,60)])")
                # tentative : premier lien qui ressemble à un document
                doc = pg.locator("a:has-text('.pdf'), a:has-text('.zip'), a:has-text('Télécharger'), a:has-text('Download')").first
                if await doc.count():
                    try:
                        async with pg.expect_download(timeout=30000) as dl:
                            await doc.click()
                        d = await dl.value
                        it["telechargement"] = {"nom": d.suggested_filename, "ok": True}
                    except Exception as e:
                        it["telechargement"] = {"erreur": str(e)[:300]}
                        await pg.screenshot(path=str(ROOT / "discovery" / "out" / f"p3_{i}_c.png"), full_page=True)
                        it["texte_apres"] = (await pg.inner_text("body"))[:1500]
            except Exception as e:
                it["erreur"] = f"{type(e).__name__}: {e}"[:400]
            it["reponses"] = reqs[-25:]
            res.append(it)
            OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
            await ctx.close()
        await br.close()


asyncio.run(main())
