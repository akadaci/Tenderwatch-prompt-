"""Prototype : télécharge les documents de 3 marchés comme un visiteur, extrait le texte,
repère l'auteur de projet et les passages sur les fixations. Seuls des EXTRAITS sont enregistrés."""
import asyncio, io, json, re, zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
IDS = ["c20e76bf-b6d8-42fd-bea0-2c8c1b3bede5", "6ef05f03-6dd2-46da-9838-208ed14f9fff", "6a378623-2691-4f6f-a519-6cd2466ae7a1"]
AUTEUR = re.compile(r"(auteur\s+d[eu]\s+projet|bureau\s+d['’]?\s*[ée]tudes?|ontwerper|studiebureau|architecte\s*:)", re.I)
FIX = re.compile(r"\b(chevilles?|ancrages?|scellements?|goujons?|tiges?\s+filet[ée]es?|r[ée]sine|fixations?\s+chimiques?|"
                 r"ATE|ETA|hilti|w[üu]rth|fischer|spit|simpson|halfen|rawlplug|mungo|pluggen|ankers?|verankering|"
                 r"chemische\s+verankering|draadstang|coupe-feu|brandwerend|rails?\s+d['’]ancrage)\b", re.I)


def texts_from(name, data, depth=0):
    """[(nom de fichier, texte)] pour PDF, DOCX, ZIP (récursif)."""
    out = []
    low = name.lower()
    try:
        if low.endswith(".zip") and depth < 3:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for n in z.namelist():
                    if n.endswith("/") or z.getinfo(n).file_size > 60_000_000:
                        continue
                    out += texts_from(n, z.read(n), depth + 1)
        elif low.endswith(".pdf"):
            import pymupdf
            with pymupdf.open(stream=data, filetype="pdf") as d:
                out.append((name, "\n".join(p.get_text() for p in d)))
        elif low.endswith(".docx"):
            import docx
            out.append((name, "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)))
        else:
            out.append((name, None))
    except Exception as e:
        out.append((name, f"__ERREUR__ {type(e).__name__}: {e}"))
    return out


def lines(text, rx, n=25, width=260):
    res, seen = [], set()
    for line in (text or "").splitlines():
        l = " ".join(line.split())
        if len(l) > 8 and rx.search(l) and l not in seen:
            seen.add(l); res.append(l[:width])
            if len(res) >= n:
                break
    return res


async def main():
    from playwright.async_api import async_playwright
    report = []
    async with async_playwright() as p:
        br = await p.chromium.launch()
        ctx = await br.new_context(locale="fr-BE", accept_downloads=True)
        page = await ctx.new_page()
        box = {}

        async def on_resp(r):
            if "openid-connect/token" in r.url and r.status == 200:
                try: box["t"] = (await r.json()).get("access_token")
                except Exception: pass
        page.on("response", on_resp)
        net = []
        page.on("request", lambda r: net.append(r.url) if re.search(r"download|content|file", r.url, re.I) else None)
        for wid in IDS:
            rep = {"id": wid, "files": []}
            await page.goto(f"https://www.publicprocurement.be/publication-workspaces/{wid}", wait_until="networkidle", timeout=90000)
            await page.wait_for_timeout(3000)
            docs = await page.evaluate("""async (wid) => {
              const r = await fetch(`/api/dos/publication-workspaces/${wid}/documents?full=false&type=WORKSPACE&type=ESPD_REQUEST&type=SDI`,
                {headers: {'Authorization': 'Bearer ' + window.__t, 'BelGov-Trace-Id': crypto.randomUUID()}});
              return {status: r.status, text: await r.text()};
            }""", wid) if False else None
            # Passer par l'interface : onglet Documents puis clic sur chaque titre
            loc = page.get_by_text("Documents", exact=True)
            if await loc.count():
                await loc.first.click(); await page.wait_for_timeout(3000)
            rows = page.locator("td").filter(has_text=re.compile(r"\.(zip|pdf|docx)$", re.I))
            n = await rows.count()
            rep["n_rows"] = n
            for i in range(min(n, 12)):
                name = (await rows.nth(i).inner_text()).strip()
                if re.search(r"ESPD|DUME|rectificatif|PSS|plan", name, re.I):
                    continue
                try:
                    async with page.expect_download(timeout=60000) as dl:
                        await rows.nth(i).click()
                    d = await dl.value
                    path = await d.path()
                    data = Path(path).read_bytes()
                    rep["download_url_example"] = d.url[:200]
                    for fname, txt in texts_from(name, data):
                        rep["files"].append({"in": name, "file": fname, "chars": len(txt or ""),
                                             "auteur": lines(txt, AUTEUR, 8), "fixation": lines(txt, FIX, 25)})
                except Exception as e:
                    rep["files"].append({"in": name, "error": f"{type(e).__name__}: {e}"[:300]})
            report.append(rep)
        report.append({"network_download_like": sorted(set(net))[:30]})
        await br.close()
    (OUT / "csc_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print("[csc] terminé")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        (OUT / "csc_probe.json").write_text(json.dumps({"exception": traceback.format_exc()}, ensure_ascii=False))
