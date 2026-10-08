import pymupdf, io, zipfile
from radar import csc

def make_pdf():
    d = pymupdf.open()
    p1 = d.new_page(); y = 72
    for l in ["CAHIER SPÉCIAL DES CHARGES", "Auteur de projet :", "Bureau Greisch SA - Liège", "1. Clauses administratives"]:
        p1.insert_text((50, y), l, fontsize=10); y += 16
    p2 = d.new_page(); y = 72
    for l in ["22.21 Ancrages et fixations", "22.21.1 Ancrages chimiques",
              "Les ancrages seront de type scellement chimique, Hilti HIT-RE 500 V4 ou équivalent,",
              "avec Évaluation Technique Européenne (ETA) pour béton fissuré.",
              "22.30 Isolation de façade", "Chevilles d'isolant à frapper, catégorie A à E selon ETA."]:
        p2.insert_text((50, y), l, fontsize=10); y += 16
    d.set_toc([[1, "Clauses administratives", 1], [1, "Ancrages et fixations", 2]])
    return d.tobytes()

def test_scan_pdf_and_zip():
    data = make_pdf()
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("LOT 1/CSC_technique.pdf", data); f.writestr("LOT 1/PSS.pdf", data); f.writestr("plans/plan_rdc.pdf", data)
    docs = csc.extract("LOT 1 - ARCHI.zip", z.getvalue())
    assert [n for n, _, _ in docs] == ["LOT 1 - ARCHI.zip › CSC_technique.pdf"]       # PSS et plans ignorés
    name, pages, toc = docs[0]
    auteur, fix = csc.scan(name, pages, toc)
    assert "Bureau Greisch SA" in auteur[0]["texte"] and auteur[0]["ou"]["page"] == 1
    top = csc.dedup(fix)
    hil = [f for f in top if f["marque"].lower() == "hilti"][0]
    assert "Hilti HIT-RE 500 V4 ou équivalent" in hil["texte"]                       # recopié mot pour mot
    assert hil["ou"] == {"document": name, "page": 2, "section": "22.21.1 Ancrages chimiques"}
    assert hil["fischer"][0]["id"] == "chimique" and "FIS EM Plus" in hil["fischer"][0]["produits"]
    assert hil["fischer"][0]["url"].startswith("https://www.fischer.be/fr-be/produits/fixations-chimiques")
    iso = [f for f in top if "isolant" in f["texte"]][0]
    assert iso["ou"]["section"] == "22.30 Isolation de façade" and iso["fischer"][0]["id"] == "isolant"
    assert top[0]["marque"]                                                          # marque citée en premier

def test_find_url_and_xlsx():
    assert csc.find_url({"a": {"b": ["x", "https://minio/x.pdf?sig=1"]}}) == "https://minio/x.pdf?sig=1"
    assert csc.find_url("https://minio/y") == "https://minio/y" and csc.find_url({"x": 1}) == ""
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Gros oeuvre"
    ws.append(["22.21.1", "Ancrage chimique Hilti HIT-HY 200 ou équivalent", "pc", 120])
    buf = io.BytesIO(); wb.save(buf)
    (name, pages, toc), = csc.extract("ME_Stabilite.xlsx", buf.getvalue())
    a, f = csc.scan(name, pages, toc)
    assert f[0]["marque"] == "Hilti" and "120" in f[0]["texte"]
    assert csc.EXCLUDE.search("2532_AIDE_SOU_PL_Sols.pdf") and not csc.EXCLUDE.search("58600-ARC 10-Menuiseries intérieures-.pdf")


def test_gamme_correspondances():
    from radar.gamme import familles
    cas = {"Les chemins de câbles seront fixés par consoles murales": "rails",
           "Les tuyauteries seront supportées par colliers isophoniques à double vis": "colliers",
           "Isolation thermique par l'extérieur (ETICS) fixée par chevilles à rosace": "isolant",
           "obturations des traversées de parois résistant au feu": "coupe_feu",
           "Façade ventilée avec sous-structure aluminium": "bardage",
           "mortier de réparation classe R4 selon EN 1504-3": "reparation"}
    for texte, attendu in cas.items():
        assert attendu in [f["id"] for f in familles(texte)], texte
    assert familles("le bureau d'études vérifiera les plans") == []
    assert familles("revêtu d'un coating autonivelant à base de résine époxy") == []
    assert [f["id"] for f in familles("tiges filetées scellées chimiquement dans le béton")] == ["chimique"]
