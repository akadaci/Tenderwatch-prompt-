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


def bda_probe():
    """Jeton anonyme, pagination, filtres et structure complète d'un avis du Bulletin des Adjudications."""
    base = "https://www.publicprocurement.be"
    out = {}
    with httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (compatible; RadarData/1.0)"}) as c:
        tok = None
        for label, kw in (("basic_vide", {"auth": ("frontend-public", "")}),
                          ("client_id_corps", {"extra": {"client_id": "frontend-public"}})):
            data = {"grant_type": "client_credentials", "scope": "openid", **kw.get("extra", {})}
            r = c.post(f"{base}/auth/realms/supplier/protocol/openid-connect/token", data=data, auth=kw.get("auth"))
            out[f"token_{label}"] = {"status": r.status_code, "keys": list(r.json()) if "json" in r.headers.get("content-type", "") else r.text[:200]}
            if r.status_code == 200 and not tok:
                tok = r.json().get("access_token"); out["token_ok"] = label
                out["token_expires_in"] = r.json().get("expires_in")
        if not tok:
            dump("bda_probe.json", out); return
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
        r = c.post(f"{base}/api/sea/search/publications", headers=h, json={"includeOrganisationChildren": True, "page": 1, "pageSize": 100})
        j = r.json()
        out["page1"] = {"status": r.status_code, "top_keys": [k for k in j if k != "publications"],
                        "top": {k: v for k, v in j.items() if k != "publications"}, "n": len(j.get("publications", [])),
                        "dates": [p.get("publicationDate") or p.get("dispatchDate") for p in j.get("publications", [])][:100],
                        "types": sorted({f"{p.get('publicationType')}|{p.get('noticeSubType')}" for p in j.get("publications", [])})}
        out["sample_full"] = j.get("publications", [])[:2]
        award = [p for p in j.get("publications", []) if "AWARD" in str(p.get("publicationType", "")).upper() or "RESULT" in str(p.get("publicationType", "")).upper()]
        out["sample_award"] = award[:1]
        r2 = c.post(f"{base}/api/sea/search/publications", headers=h, json={"includeOrganisationChildren": True, "page": 2, "pageSize": 100})
        out["page2"] = {"status": r2.status_code, "n": len(r2.json().get("publications", [])) if r2.status_code == 200 else r2.text[:300]}
        for name, extra in (("cpv", {"cpvCodes": ["45000000-7"]}), ("date", {"publicationDateFrom": "2026-10-01"}),
                            ("nuts", {"nutsCodes": ["BE33"]})):
            rr = c.post(f"{base}/api/sea/search/publications", headers=h, json={"includeOrganisationChildren": True, "page": 1, "pageSize": 5, **extra})
            out[f"filter_{name}"] = {"status": rr.status_code, "body": rr.text[:300] if rr.status_code != 200 else
                                     {k: v for k, v in rr.json().items() if k != "publications"}}
        for u in (f"{base}/robots.txt", "https://bosa.belgium.be/fr/conditions-dutilisation-pour-la-plateforme-e-procurement"):
            try:
                rr = c.get(u, follow_redirects=True)
                txt = re.sub(r"<[^>]+>", " ", rr.text); txt = re.sub(r"\s+", " ", txt)
                out[u] = {"status": rr.status_code, "text": txt[:15000]}
            except Exception as e:
                out[u] = {"error": str(e)}
    dump("bda_probe.json", out)
    print("[bda] sonde terminée")


async def browser_token():
    """Le navigateur obtient lui-même le jeton anonyme (comme un visiteur) ; il n'est jamais enregistré."""
    from playwright.async_api import async_playwright
    box = {}
    async with async_playwright() as p:
        br = await p.chromium.launch()
        page = await br.new_page()
        async def on_resp(r):
            if "openid-connect/token" in r.url and r.status == 200:
                try:
                    box["token"] = (await r.json()).get("access_token")
                except Exception:
                    pass
        page.on("response", on_resp)
        await page.goto("https://www.publicprocurement.be/bda", wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(3000)
        await br.close()
    return box.get("token")


def bda_probe2():
    base = "https://www.publicprocurement.be"
    out = {}
    with httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (compatible; RadarData/1.0)"}, follow_redirects=True) as c:
        for u in (f"{base}/robots.txt", "https://bosa.belgium.be/fr/conditions-dutilisation-pour-la-plateforme-e-procurement"):
            try:
                rr = c.get(u)
                txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", rr.text, flags=re.S)
                txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt))
                out[u] = {"status": rr.status_code, "text": txt[:20000]}
            except Exception as e:
                out[u] = {"error": str(e)}
        tok = asyncio.run(browser_token())
        out["token_from_browser"] = bool(tok)
        if tok:
            h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
            url = f"{base}/api/sea/search/publications"
            j = c.post(url, headers=h, json={"includeOrganisationChildren": True, "page": 1, "pageSize": 100}).json()
            pubs = j.get("publications", [])
            out["page1"] = {"top": {k: v for k, v in j.items() if k != "publications"}, "n": len(pubs),
                            "dates": [x.get("publicationDate") for x in pubs],
                            "types": sorted({f"{x.get('publicationType')}|{x.get('noticeSubType')}|{x.get('natures')}" for x in pubs})}
            out["samples"] = pubs[:3]
            out["sample_award"] = [x for x in pubs if "ward" in json.dumps(x.get("publicationType")) or "ttribution" in json.dumps(x)][:1]
            out["page5"] = {"dates": [x.get("publicationDate") for x in c.post(url, headers=h, json={"includeOrganisationChildren": True, "page": 5, "pageSize": 100}).json().get("publications", [])][:3]}
            for name, extra in (("cpv", {"cpvCodes": ["45000000-7"]}), ("cpvMain", {"cpvMainCodes": ["45000000"]}),
                                ("dateFrom", {"publicationDateFrom": "2026-10-01"}), ("nuts", {"nutsCodes": ["BE33"]}),
                                ("sort", {"sortBy": "publicationDate", "sortOrder": "DESC"})):
                rr = c.post(url, headers=h, json={"includeOrganisationChildren": True, "page": 1, "pageSize": 5, **extra})
                body = rr.json() if "json" in rr.headers.get("content-type", "") else rr.text[:300]
                out[f"filter_{name}"] = {"status": rr.status_code,
                                         "info": {k: v for k, v in body.items() if k != "publications"} if isinstance(body, dict) else body,
                                         "first_dates_cpv": [(x.get("publicationDate"), (x.get("cpvMainCode") or {}).get("code"), x.get("nutsCodes")) for x in (body.get("publications", []) if isinstance(body, dict) else [])]}
    dump("bda_probe2.json", out)
    print("[bda] sonde 2 terminée, jeton :", out.get("token_from_browser"))


async def bda_detail_url():
    from playwright.async_api import async_playwright
    res = {}
    async with async_playwright() as p:
        br = await p.chromium.launch()
        page = await br.new_page(locale="fr-BE")
        await page.goto("https://www.publicprocurement.be/bda", wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(5000)
        cands = await page.eval_on_selector_all("a", "els => els.map(a => [a.innerText.trim().slice(0,100), a.href]).filter(x => /bda|publication|notice/i.test(x[1]))")
        res["anchors"] = cands[:40]
        try:
            el = page.locator("mat-card, .publication, [class*=result] a, [class*=card]").first
            await el.click(timeout=15000)
            await page.wait_for_timeout(5000)
            res["after_click_url"] = page.url
            await page.screenshot(path=str(OUT / "bda_detail.png"), full_page=True)
        except Exception as e:
            res["click_error"] = str(e)
        await br.close()
    dump("bda_detail.json", res)


async def round2():
    await capture(["https://www.publicprocurement.be/bda"], "bda", follow=r"$^")
    await capture(["https://pmp.b2g.etat.lu/entreprise"], "pmp", follow=r"consultation|avis|recherche|search|appel")


if __name__ == "__main__":
    try:
        bda_probe2()
    except Exception as e:
        print(f"::warning::bda_probe2 : {type(e).__name__}: {e}")
    raise SystemExit(0)
    try:
        bda_probe()
    except Exception as e:
        print(f"::warning::bda_probe : {e}")
    try:
        asyncio.run(bda_detail_url())
    except Exception as e:
        print(f"::warning::bda_detail : {e}")
    raise SystemExit(0)
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
