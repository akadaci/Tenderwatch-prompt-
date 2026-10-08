"""Prépare data/radar_public.json pour la page « Radar Chantiers Public ».
Filtre validé : amont (étapes 1-2 : préinformations, études, gros permis), attributions de travaux (étape 5),
et appels d'offres en cours (étape 4) dans un onglet séparé. Doublons BDA/TED retirés (TED gardé : il a le gagnant)."""
import json, re, unicodedata
from datetime import datetime, timedelta, timezone
from radar.common import DATA, now_iso

WALLONIE = {"Liège", "Namur", "Hainaut", "Brabant wallon", "Luxembourg (prov.)"}
FLANDRE = {"Anvers", "Limbourg", "Flandre-Orientale", "Brabant flamand", "Flandre-Occidentale"}
KEEP_DAYS = 60
# Secteurs Fischer : préfixes CPV officiels + mots-clés FR/NL (classement automatique, indicatif)
SECTEURS = [
    ("Ponts et ouvrages d'art", ("45221",), r"\b(pont|ponts|brug|bruggen|viaduc|tunnel|passerelle|quai|kaaimuur|ouvrage d'art)\b"),
    ("Façades", ("45443", "45262650"), r"\b(fa[cç]ades?|gevels?|bardage|gevelrenovatie|parement)\b"),
    ("Eau et épuration", ("45252", "45232", "45247", "45248"), r"\b(épuration|epuration|égout|egout|égouttage|riolering|waterzuivering|station de pompage|bassin d'orage|collecteur)\b"),
    ("Éclairage public", ("45316",), r"\b([ée]clairage public|openbare verlichting|straatverlichting)\b"),
    ("Écoles, santé, bâtiments publics", ("45214", "45215", "45216", "45212"), r"\b([ée]coles?|school|scholen|cr[èe]che|kinderdagverblijf|h[ôo]pital|ziekenhuis|maison de repos|woonzorgcentrum|piscine|zwembad|hall sportif|sporthal)\b"),
    ("Logements et rénovation", ("45211", "45321", "45453", "45421"), r"\b(logements?|woningen|appartements?|r[ée]novation [ée]nerg[ée]tique|isolation|renovatie|sociale woningen|immeuble)\b"),
    ("Techniques spéciales", ("4533", "4531", "45259"), r"\b(hvac|chauffage|ventilation|sanitaire|[ée]lectricit[ée]|verwarming|sprinkler|coupe-feu|brandwerend)\b"),
    ("Voirie et infrastructures", ("45233", "45234", "45112"), r"\b(voirie|wegenis|rond-point|parking|trottoirs?|fietspad|chauss[ée]e|rail)\b"),
]


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def ted_core(title):
    # TED préfixe « Belgique – Catégorie – » au titre d'origine
    parts = re.split(r"\s[–-]\s", title or "", maxsplit=2)
    return parts[2] if len(parts) == 3 else title


def secteur(r):
    cpvs = (r.get("cpv") or "").split(",")
    text = norm(f"{r.get('nom', '')} {r.get('notes', '')}")
    for name, prefixes, rx in SECTEURS:
        if any(c.startswith(prefixes) for c in cpvs if c) or re.search(rx, text, re.I):
            return name
    return "Autres travaux" if any(c.startswith("45") for c in cpvs) else ("Études" if any(c.startswith("71") for c in cpvs) else "")


PROVINCES = WALLONIE | FLANDRE | {"Bruxelles", "Grand-Duché"}


def region(r):
    p = r.get("province") or ""
    if not p:                                     # avis collectés avant l'ajout du champ province
        lieu = r.get("lieu") or ""
        p = next((x for x in PROVINCES if x in lieu), "")
        if not p and (r.get("pays") == "LUX" or lieu.endswith("Luxembourg")):
            p = "Grand-Duché"
    if p in WALLONIE: return "Wallonie"
    if p in FLANDRE: return "Flandre"
    if p == "Bruxelles": return "Bruxelles"
    if p == "Grand-Duché": return "Grand-Duché"
    return "Non précisé"


def load(name):
    try:
        return json.loads((DATA / f"{name}.json").read_text())["records"]
    except (OSError, ValueError, KeyError):
        return []


def build():
    since = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    ted, bda, permis = load("ted"), load("bda"), load("permis_bruxelles")
    ted_keys = {(norm(ted_core(r["nom"]))[:60], norm(r.get("mo"))[:25]) for r in ted}
    dup = 0
    out = []
    for r in ted + bda + permis:
        if (r.get("date_publication") or "") < since:
            continue
        if r["source_type"] == "BDA" and (norm(r["nom"])[:60], norm(r.get("mo"))[:25]) in ted_keys:
            dup += 1
            continue
        e = r["etape"]
        cpvs = (r.get("cpv") or "").split(",")
        travaux = any(c.startswith(("45", "44")) for c in cpvs)
        if e in (1, 2):
            vue = "amont"
        elif e == 5 and travaux:
            vue = "attributions"
        elif e == 4:
            vue = "appels"
        else:
            continue
        nom = ted_core(r["nom"]) if r["source_type"] == "TED" else r["nom"]
        out.append({k: v for k, v in {
            "id": r["id"], "vue": vue, "etape": e, "src": r["source_type"], "nom": nom, "mo": r.get("mo"),
            "lieu": r.get("lieu"), "region": region(r), "secteur": secteur(r) or "Autres",
            "entreprise": r.get("entreprise"), "be": r.get("be"), "bce": r.get("bce"), "montant": r.get("montant"),
            "date": r.get("date_publication"), "limite": r.get("date_limite"), "cpv": r.get("cpv"),
            "source": r.get("source"), "preuve": r.get("preuve"), "desc": (r.get("notes") or "")[:280],
        }.items() if v})
    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    res = {"updated": now_iso(), "keep_days": KEEP_DAYS, "doublons_retires": dup, "count": len(out), "records": out}
    (DATA / "radar_public.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")))
    print(f"[export] {len(out)} fiches ({dup} doublons BDA/TED retirés)")
    return res


if __name__ == "__main__":
    build()
