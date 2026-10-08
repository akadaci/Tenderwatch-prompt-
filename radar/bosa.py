"""Accès à l'API publique d'e-Procurement (SPF BOSA) depuis un vrai navigateur, comme un visiteur.
Le jeton anonyme est obtenu par la page elle-même et n'est jamais stocké."""
import asyncio, json

BASE = "https://www.publicprocurement.be"
JS = """async ([url, method, body]) => {
  const r = await fetch(url, {method, credentials: 'include',
    headers: {'Content-Type': 'application/json', 'Accept': 'application/json',
              'Authorization': 'Bearer ' + window.__twToken, 'BelGov-Trace-Id': crypto.randomUUID()},
    body: body ? JSON.stringify(body) : undefined});
  return {status: r.status, text: await r.text()};
}"""


class Session:
    """async with Session() as s: data = await s.get('/api/...')"""

    def __init__(self, pause_ms=600):
        self.pause_ms = pause_ms

    async def __aenter__(self):
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._br = await self._pw.chromium.launch()
        self.page = await self._br.new_page(locale="fr-BE")
        got = asyncio.get_event_loop().create_future()

        async def on_resp(r):
            if "openid-connect/token" in r.url and r.status == 200 and not got.done():
                try:
                    got.set_result((await r.json()).get("access_token"))
                except Exception as e:
                    got.set_exception(e)
        self.page.on("response", on_resp)
        await self.page.goto(BASE + "/bda", wait_until="networkidle", timeout=90000)
        await self.page.evaluate("t => { window.__twToken = t }", await asyncio.wait_for(got, 60))
        return self

    async def __aexit__(self, *exc):
        await self._br.close()
        await self._pw.stop()

    async def call(self, path, method="GET", body=None):
        res = await self.page.evaluate(JS, [path, method, body])
        await self.page.wait_for_timeout(self.pause_ms)        # rythme lent volontaire
        if res["status"] != 200:
            raise RuntimeError(f"BOSA HTTP {res['status']} {path} : {res['text'][:200]}")
        return json.loads(res["text"]) if res["text"] else None
