"""Découverte (à lancer sur GitHub, qui a accès à Internet) :
1. e-Procurement (publicprocurement.be) : un vrai navigateur ouvre le site et enregistre les flux de données appelés.
2. Portail des marchés publics Luxembourg : recherche des flux RSS d'avis.
3. Lotissements wallons (SPW) : structure du service REST.
Résultats écrits dans discovery/out/ pour analyse."""
import asyncio, json, re
from pathlib import Path
import httpx

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1))


async def enot():
    from playwright.async_api import async_playwright
    reqs = []
    async with async_playwright() as p:
        br = await p.chromium.launch()
        page = await br.new_page(locale="fr-BE")

        async def on_resp(r):
            if r.request.resource_type in ("xhr", "fetch", "document"):
                entry = {"url": r.url, "method": r.request.method, "status": r.status,
                         "type": r.request.resource_type, "ctype": r.headers.get("content-type", ""),
                         "post": (r.request.post_data or "")[:1000]}
                if "json" in entry["ctype"]:
                    try:
                        entry["body"] = (await r.text())[:4000]
                    except Exception as e:
                        entry["body_error"] = str(e)
                reqs.append(entry)
        page.on("response", on_resp)
        visited = []
        for url in ("https://www.publicprocurement.be/", "https://www.publicprocurement.be/fr"):
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                visited.append(url)
            except Exception as e:
                visited.append(f"{url} → {e}")
        await page.screenshot(path=str(OUT / "enot_home.png"), full_page=True)
        links = await page.eval_on_selector_all("a", "els => els.map(a => [a.innerText.trim().slice(0,80), a.href]).filter(x => x[1])")
        dump("enot_links.json", links)
        targets = [h for t, h in links if re.search(r"recherch|search|zoek|avis|publication|notice|bekendmaking", f"{t} {h}", re.I)]
        for h in list(dict.fromkeys(targets))[:4]:
            try:
                await page.goto(h, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(3000)
                visited.append(h)
                await page.screenshot(path=str(OUT / f"enot_{len(visited)}.png"), full_page=True)
            except Exception as e:
                visited.append(f"{h} → {e}")
        await br.close()
    dump("enot_requests.json", {"visited": visited, "requests": reqs})
    print(f"[enot] {len(reqs)} requêtes enregistrées, {sum('json' in r['ctype'] for r in reqs)} JSON")


def lux():
    found = {}
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; RadarData/1.0)"}) as c:
        for url in ("https://marches.public.lu/fr.html", "https://pmp.b2g.etat.lu/", "https://marches.public.lu/fr/support/rss.html"):
            try:
                r = c.get(url)
                html = r.text
                feeds = re.findall(r'href="([^"]+)"[^>]*type="application/(?:rss|atom)\+xml"', html) + \
                        re.findall(r'href="([^"]*(?:rss|RSS|feed|\.xml)[^"]*)"', html)
                found[url] = {"status": r.status_code, "final_url": str(r.url), "feeds": sorted(set(feeds))[:50]}
            except Exception as e:
                found[url] = {"error": f"{type(e).__name__}: {e}"}
        for u in {f for v in found.values() for f in v.get("feeds", [])}:
            full = u if u.startswith("http") else httpx.URL("https://marches.public.lu").join(u)
            try:
                r = c.get(str(full))
                found.setdefault("_feeds", {})[str(full)] = {"status": r.status_code, "ctype": r.headers.get("content-type"),
                                                             "head": r.text[:1500]}
            except Exception as e:
                found.setdefault("_feeds", {})[str(full)] = {"error": str(e)}
    dump("lux_rss.json", found)
    print(f"[lux] {sum(len(v.get('feeds', [])) for k, v in found.items() if k != '_feeds')} liens de flux candidats")


def wallonie():
    base = "https://geoservices.wallonie.be/arcgis/rest/services/AMENAGEMENT_TERRITOIRE/LOT/MapServer"
    res = {}
    with httpx.Client(timeout=60) as c:
        try:
            svc = c.get(base, params={"f": "json"}).json()
            res["service"] = {"layers": svc.get("layers"), "error": svc.get("error")}
            for lyr in (svc.get("layers") or [])[:4]:
                info = c.get(f"{base}/{lyr['id']}", params={"f": "json"}).json()
                sample = c.get(f"{base}/{lyr['id']}/query", params={"where": "1=1", "outFields": "*", "returnGeometry": "false",
                                                                    "resultRecordCount": "3", "f": "json"}).json()
                res[str(lyr["id"])] = {"name": info.get("name"), "fields": [(f["name"], f["type"]) for f in info.get("fields", [])],
                                       "sample": sample.get("features", [])[:3], "error": sample.get("error")}
        except Exception as e:
            res["error"] = f"{type(e).__name__}: {e}"
    dump("wallonie_lotissements.json", res)
    print(f"[wallonie] {len(res)} entrées")


if __name__ == "__main__":
    for name, fn in (("lux", lux), ("wallonie", wallonie)):
        try:
            fn()
        except Exception as e:
            print(f"::warning::{name} : {e}")
    try:
        asyncio.run(enot())
    except Exception as e:
        print(f"::warning::enot : {e}")
