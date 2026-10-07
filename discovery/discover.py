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


async def capture(start_urls, prefix, follow=r"$^"):
    """Ouvre des pages dans Chromium et enregistre les appels de données (en-têtes sensibles masqués)."""
    import base64
    from playwright.async_api import async_playwright
    reqs, visited = [], []
    async with async_playwright() as p:
        br = await p.chromium.launch()
        page = await br.new_page(locale="fr-BE")

        async def on_resp(r):
            if r.request.resource_type not in ("xhr", "fetch"):
                return
            h = await r.request.all_headers()
            auth = h.get("authorization", "")
            if auth.lower().startswith("basic "):
                try:
                    auth = "Basic user=" + base64.b64decode(auth[6:]).decode().split(":")[0]
                except Exception:
                    auth = "Basic ?"
            elif auth:
                auth = auth.split(" ")[0] + " <masqué>"
            entry = {"url": r.url, "method": r.request.method, "status": r.status,
                     "ctype": r.headers.get("content-type", ""), "auth": auth,
                     "req_headers": sorted(k for k in h if not k.startswith(":")),
                     "post": (r.request.post_data or "")[:2000]}
            if "json" in entry["ctype"] and "token" not in r.url:
                try:
                    entry["body"] = (await r.text())[:6000]
                except Exception as e:
                    entry["body_error"] = str(e)
            reqs.append(entry)
        page.on("response", on_resp)
        for url in start_urls:
            try:
                await page.goto(url, wait_until="networkidle", timeout=90000)
                await page.wait_for_timeout(5000)
                for _ in range(3):
                    await page.mouse.wheel(0, 3000); await page.wait_for_timeout(1500)
                visited.append(page.url)
                await page.screenshot(path=str(OUT / f"{prefix}_{len(visited)}.png"), full_page=True)
                links = await page.eval_on_selector_all("a", "els => els.map(a => [a.innerText.trim().slice(0,80), a.href])")
                dump(f"{prefix}_links_{len(visited)}.json", links)
                for t, h in links:
                    if re.search(follow, f"{t} {h}", re.I) and len(visited) < 6:
                        try:
                            await page.goto(h, wait_until="networkidle", timeout=90000)
                            await page.wait_for_timeout(4000)
                            visited.append(page.url)
                            await page.screenshot(path=str(OUT / f"{prefix}_{len(visited)}.png"), full_page=True)
                        except Exception as e:
                            visited.append(f"{h} → {e}")
                        break
            except Exception as e:
                visited.append(f"{url} → {e}")
        await br.close()
    dump(f"{prefix}_requests.json", {"visited": visited, "requests": reqs})
    print(f"[{prefix}] {len(reqs)} appels de données, {sum('json' in r['ctype'] for r in reqs)} JSON")


def wallonie_recent():
    base = "https://geoservices.wallonie.be/arcgis/rest/services/AMENAGEMENT_TERRITOIRE/LOT/MapServer/0/query"
    out = {}
    with httpx.Client(timeout=60) as c:
        for where in ("DATE_DE_DECISION >= DATE '2026-07-01'", "DATE_DE_DECISION >= timestamp '2026-07-01 00:00:00'",
                      "TIMESTAMP >= DATE '2026-07-01'"):
            r = c.get(base, params={"where": where, "outFields": "*", "returnGeometry": "true", "outSR": "31370",
                                    "resultRecordCount": "5", "orderByFields": "DATE_DE_DECISION DESC", "f": "json"})
            j = r.json()
            feats = j.get("features", [])
            out[where] = {"status": r.status_code, "error": j.get("error"), "n": len(feats),
                          "sample": [{"attributes": f["attributes"],
                                      "rings_points": sum(len(x) for x in (f.get("geometry") or {}).get("rings", []))} for f in feats[:3]]}
            cnt = c.get(base, params={"where": where, "returnCountOnly": "true", "f": "json"}).json()
            out[where]["count"] = cnt
    dump("wallonie_recent.json", out)
    print("[wallonie] requêtes datées testées")


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


async def round2():
    await capture(["https://www.publicprocurement.be/bda"], "bda", follow=r"$^")
    await capture(["https://pmp.b2g.etat.lu/entreprise"], "pmp", follow=r"consultation|avis|recherche|search|appel")


if __name__ == "__main__":
    try:
        wallonie_recent()
    except Exception as e:
        print(f"::warning::wallonie_recent : {e}")
    try:
        asyncio.run(round2())
    except Exception as e:
        print(f"::warning::round2 : {e}")
    raise SystemExit(0)
    for name, fn in (("lux", lux), ("wallonie", wallonie)):
        try:
            fn()
        except Exception as e:
            print(f"::warning::{name} : {e}")
    try:
        asyncio.run(enot())
    except Exception as e:
        print(f"::warning::enot : {e}")
