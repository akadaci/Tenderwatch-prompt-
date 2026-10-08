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
    assert hil["suggestion"].startswith("Chimique FIS EM Plus")
    iso = [f for f in top if "isolant" in f["texte"]][0]
    assert iso["ou"]["section"] == "22.30 Isolation de façade" and iso["suggestion"] == "Chevilles d'isolant Termoz"
    assert top[0]["marque"]                                                          # marque citée en premier
