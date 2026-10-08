"""Trouve comment télécharger un document : menu « ⋮ » d'une ligne, puis « Télécharger »."""
import asyncio, json, re
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
WID = "6ef05f03-6dd2-46da-9838-208ed14f9fff"


async def main():
    from playwright.async_api import async_playwright
    res = {"requests": []}
    async with async_playwright() as p:
        br = await p.chromium.launch()
        ctx = await br.new_context(locale="fr-BE", accept_downloads=True, viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        page.on("request", lambda r: res["requests"].append({"url": r.url, "method": r.method, "type": r.resource_type})
                if r.resource_type in ("xhr", "fetch", "document", "other") and "translations" not in r.url else None)
        await page.goto(f"https://www.publicprocurement.be/publication-workspaces/{WID}", wait_until="networkidle", timeout=90000)
        for t in ("Accepter les cookies",):
            b = page.get_by_text(t, exact=True)
            if await b.count(): await b.first.click()
        await page.get_by_text("Documents", exact=True).first.click()
        await page.wait_for_timeout(3000)
        res["mark_before_menu"] = len(res["requests"])
        rows = page.locator("tr").filter(has_text=re.compile(r"_CS\.pdf", re.I))
        res["rows_found"] = await rows.count()
        row = rows.first
        btns = row.locator("button")
        res["row_buttons"] = await btns.count()
        await btns.last.click()
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUT / "doc_menu.png"))
        items = page.locator("[role=menuitem], .mat-mdc-menu-item, .mat-menu-item")
        res["menu_items"] = [ (await items.nth(i).inner_text()).strip() for i in range(await items.count())]
        res["mark_before_click"] = len(res["requests"])
        try:
            async with page.expect_download(timeout=90000) as dl:
                await page.locator("span:visible", has_text="Télécharger la dernière version").first.click()
            d = await dl.value
            data = Path(await d.path()).read_bytes()
            res["download"] = {"url": d.url[:300], "suggested": d.suggested_filename, "bytes": len(data), "head": data[:8].hex()}
            import pymupdf
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                res["pages"] = doc.page_count
                res["toc"] = doc.get_toc()[:80]
                txt = [doc[i].get_text() for i in range(doc.page_count)]
            AUT = re.compile(r"(auteur\s+d[eu]\s+projet|bureau\s+d['’]?\s*[ée]tudes?|architecte|ing[ée]nieur)", re.I)
            res["auteur_lines"] = [(i + 1, " ".join(l.split())[:250]) for i, t in enumerate(txt) for l in t.splitlines() if AUT.search(l)][:40]
        except Exception as e:
            res["download_error"] = f"{type(e).__name__}: {e}"[:400]
        res["after_click"] = res["requests"][res["mark_before_click"]:]
        await br.close()
    (OUT / "csc_probe2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        (OUT / "csc_probe2.json").write_text(json.dumps({"exception": traceback.format_exc()}, ensure_ascii=False))
