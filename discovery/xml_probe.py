import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from radar.bosa import Session
OUT = Path(__file__).resolve().parent / "out"
IDS = {"appel": "6ef05f03-6dd2-46da-9838-208ed14f9fff", "attribution": "9cecaf15-5514-4c07-86a9-58bcf6916ebc"}

async def main():
    async with Session() as s:
        for k, wid in IDS.items():
            d = await s.call(f"/api/dos/publication-workspaces/{wid}?includeDrafts=false")
            v = (d.get("versions") or [{}])[-1]
            xml = (v.get("notice") or {}).get("xmlContent") or d.get("xmlContent") or ""
            if not xml:
                # chercher le XML n'importe où dans la réponse
                def find(o):
                    if isinstance(o, dict):
                        for kk, vv in o.items():
                            if kk == "xmlContent" and vv: return vv
                            r = find(vv)
                            if r: return r
                    if isinstance(o, list):
                        for x in o:
                            r = find(x)
                            if r: return r
                xml = find(d) or ""
            (OUT / f"xml_{k}.xml").write_text(xml)
            meta = {kk: vv for kk, vv in d.items() if kk != "versions"}
            meta["version_keys"] = sorted(v.keys()); meta["n_versions"] = len(d.get("versions") or [])
            meta["submissionDeadline"] = v.get("submissionDeadline")
            (OUT / f"xml_{k}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)[:20000])
    print("ok")

asyncio.run(main())
