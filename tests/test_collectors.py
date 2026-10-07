import json, httpx, pytest
from pathlib import Path
from radar import ted, nova, common
FIX = Path(__file__).parent / "fixtures"

def test_ted_mapping():
    a, b, c, d = (ted.to_fiche(r) for r in json.loads((FIX / "ted_sample.json").read_text())["notices"])
    assert d is None                                         # papier : hors périmètre Fischer
    assert (a["etape"], a["mo"], a["lieu"], a["montant"], a["date_limite"]) == (4, "SPW Mobilité", "Namur, Belgique", "1250000", "2026-10-30")
    assert a["source"] == "https://ted.europa.eu/fr/notice/612345-2026/html" and a["verif"] == "vérifié"
    assert (b["etape"], b["entreprise"], b["bce"], b["montant"]) == (5, "Galère SA", "0202239951", "845000")
    assert (c["etape"], c["be"], c["entreprise"]) == (2, "Bureau Greisch", "")    # bureau d'études connu

def test_ted_fetch_pagination_and_fallback():
    calls = []
    def h(req):
        body = json.loads(req.content); calls.append(body)
        if "place-of-performance" in body["fields"]:
            return httpx.Response(400, json={"message": "unknown field"})
        n = 250 if body["page"] == 1 else 3
        return httpx.Response(200, json={"notices": [{"publication-number": f"{body['page']}-{i}"} for i in range(n)]})
    out, fields = ted.fetch(client=httpx.Client(transport=httpx.MockTransport(h)))
    assert len(out) == 253 and fields == ted.SAFE_FIELDS
    assert calls[-1]["query"].startswith("buyer-country IN (BEL LUX) AND publication-date >= ")
    with pytest.raises(ted.TedError):
        ted.fetch(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503, text="down"))))

def test_nova_filter_and_mapping(monkeypatch):
    feats = json.loads((FIX / "nova_sample.json").read_text())["features"]
    p = {**feats[1]["properties"]}                           # « Transformer un immeuble de bureaux… »
    f = nova.to_fiche(p)
    assert f and f["etape"] == 1 and f["id"] == "nova-04/PFD/2048096" and "Bruxelles" in f["lieu"]
    assert "novaReference='04/PFD/2048096'" in f["source"]
    assert nova.to_fiche({**feats[2]["properties"]}) is None             # saules : petit projet
    assert nova.to_fiche({"novaReference": "x", "caseFrenchObject": "Rénovation", "housingProjectedArea": 2400.0})
    assert nova.to_fiche({"novaReference": "y", "caseFrenchObject": "Abattre 3 arbres devant l'immeuble"}) is None

def test_save_merges(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA", tmp_path)
    assert common.save("x", [{"id": "a", "date_publication": "2026-10-01"}], {}) == (1, 1)
    assert common.save("x", [{"id": "a", "etape": 5}, {"id": "b"}], {}) == (1, 2)
    d = json.loads((tmp_path / "x.json").read_text())
    assert d["new_ids"] == ["b"] and {r["id"]: r for r in d["records"]}["a"]["etape"] == 5
