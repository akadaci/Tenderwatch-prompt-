"""Lecture intégrale de Qualiroutes (chapitres C, J, K, N, H, L, M en vigueur) et du CCTB 01.13 :
extraction des passages qui parlent de fixation (ancrage, cheville, scellement, résine, rail, coupe-feu…),
avec chapitre, page et titre d'article. Résultat : discovery/out/referentiels.json"""
import io, json, re, sys, zipfile
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "discovery" / "out" / "referentiels.json"
Q = "https://infrastructures.wallonie.be/files/PDF/POUVOIR%20LOCAL/1-ROUTES/1-2-Qualite-et-construction/1-2-1-Qualiroutes/CCT-2021/Chapitre%20{}.pdf"
CCTB = ["https://batiments.wallonie.be/files/CCT_DOCS/CCTB_01.13/CCTB_01.13_pdf.zip"]
PAGES = {"K": range(119, 124), "N": range(41, 45), "J": None}
MOTS = re.compile(r"(ancrage|cheville|scellement|scellé|goujon|tige[s]? filetée|résine|rail[s]? d|rails? de fixation|EAD\s*33|ETAG|ETA\b|ATE\b|"
                  r"évaluation technique européenne|1992-4|arrachement|coupe-feu|résistant au feu|EI\s?\d{2,3}|intumescent|ETICS|rosace|colliers?|"
                  r"suspente|chemin[s]? de câbles|consoles?|platine|A4-70|inoxydable|HCR|1504-6|EN 1881)", re.I)
TITRE = re.compile(r"^\s*((?:[A-Q]\.\s?)?\d{1,2}(?:\.\d{1,2}){1,5}\.?)\s+([A-ZÉÈÀÂÎÔÛÇ][^\n]{3,120})$")


def extraire(nom, data):
    import pymupdf
    res = []
    with pymupdf.open(stream=data, filetype="pdf") as d:
        titre = ""
        for i in range(d.page_count):
            lignes = d[i].get_text().splitlines()
            for j, l in enumerate(lignes):
                m = TITRE.match(l)
                if m:
                    titre = (m.group(1) + " " + m.group(2)).strip()[:140]
                if MOTS.search(l):
                    bloc = " ".join(x.strip() for x in lignes[max(0, j - 1):j + 3])
                    res.append({"doc": nom, "page": i + 1, "article": titre, "texte": re.sub(r"\s+", " ", bloc)[:700]})
    return res


def main():
    out = {"qualiroutes": [], "cctb": [], "erreurs": []}
    with httpx.Client(timeout=180, follow_redirects=True) as h:
        for ch in "CJKNHLM":
            try:
                r = h.get(Q.format(ch))
                if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                    out["erreurs"].append(f"Qualiroutes {ch}: HTTP {r.status_code}"); continue
                out["qualiroutes"] += extraire(f"Qualiroutes chapitre {ch}", r.content)
                if ch in PAGES:
                    import pymupdf
                    with pymupdf.open(stream=r.content, filetype="pdf") as d:
                        rng = PAGES[ch] or [i + 1 for i in range(d.page_count) if "J. 12.2" in d[i].get_text() or "GARDE-CORPS" in d[i].get_text()]
                        out.setdefault("pages", {})[ch] = {str(i): d[i - 1].get_text() for i in rng if 0 < i <= d.page_count}
            except Exception as e:
                out["erreurs"].append(f"Qualiroutes {ch}: {e}")
            OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0))
        for u in CCTB:
            try:
                r = h.get(u)
                if r.status_code != 200:
                    out["erreurs"].append(f"CCTB {u}: HTTP {r.status_code}"); continue
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    noms = [n for n in z.namelist() if n.lower().endswith(".pdf")]
                    out["cctb_fichiers"] = noms[:50]
                    for n in noms:
                        out["cctb"] += extraire(f"CCTB 01.13 {Path(n).name}", z.read(n))
                break
            except Exception as e:
                out["erreurs"].append(f"CCTB {u}: {e}")
    out["n"] = {"qualiroutes": len(out["qualiroutes"]), "cctb": len(out["cctb"])}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    print(out["n"], out["erreurs"])


main()
