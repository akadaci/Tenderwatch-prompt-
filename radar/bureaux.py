"""Nom des bureaux d'études / auteurs de projet, tiré des passages recopiés du cahier des charges.
Règle : on ne garde un nom que s'il suit directement l'intitulé (« Auteur de projet : X », « Bureau d'études | X »,
« X - Bureau d'études »). Sinon rien : mieux vaut pas de nom qu'un nom inventé. Le passage d'origine reste affiché."""
import re, unicodedata

CHARGE = r"(?:conception|direction|surveillance|haute\s+surveillance|contr[ôo]le|[ée]tudes?|ex[ée]cution)"
ROLE = re.compile(r"\b(auteurs?\s+d[eu]\s+projet|bureau\s+d['’]?\s*[ée]tudes?|ing[ée]nieur\s+(?:en\s+)?stabilit[ée]|architecte(?=\s*[:|])|studiebureau|ontwerper)"
                  r"(?:\s+charg[ée]e?\s+de\s+(?:la\s+|l['’])?" + CHARGE + r"(?:\s*,?\s*(?:et\s+)?(?:du|de\s+la|de\s+l['’]|des)?\s*" + CHARGE + r")*)?", re.I)
STOP = re.compile(r"\s*(?:,|\(|;|\bBoulevard\b|\bBd\.?\s|\bRue\b|\bAvenue\b|\bAv\.\s|\bPlace\b|\bplace\b|\bChauss[ée]e\b|\bCh[ée]e\b|\bRoute\b|\bQuai\b|"
                  r"\bSquare\b|\bn°|\b\d{1,4}\s*,?\s*(?:place|rue|avenue|bd|boulevard|chauss[ée]e)\b|\b\d{4}\s+[A-Z]|\bAdresse\b|\bFonction\b|\bT[ée]l\b|"
                  r"\bStatut\b|\bBureau\s+d|\bAuteur\s+de|\bD[ée]partement\b|\bDEPARTEMENT\b|\bDirection\s+r[ée]gionale\b|\s-\s|\s–\s|$)")
REJET = re.compile(r"^(?:INDICE|DATE|DESIGNATION|DOSSIER|CODE|LIBELL|STADE|PLAN|Fait\s+[àa]|Signature|SERVICE|POLE|Statut|ET\b|DE\b|D['’]|"
                   r"NOM\b|Comme|INSCRIT|le\b|la\b|les\b|l['’]|du\b|des\b|un\b|une\b|pour\b|par\b|sera\b|est\b|doit\b)", re.I)
# liste d'abréviations (« AP Auteur de projet / CS Coordinateur… ») : ce n'est pas un nom
AUTRE_ROLE = re.compile(r"\b(?:coordinat\w+|entreprises?|entrepreneurs?|ma[îi]tres?\s+d['’]ouvrage|adjudicat\w+|soumissionnaires?|pouvoir|fonctionnaire|"
                        r"direction\s+des\s+travaux|s[ée]curit[ée]|ing[ée]nieur|architecte\b)", re.I)
SIGLES = r"\b(?:s\.?a\.?|s\.?r\.?l\.?|s\.?p\.?r\.?l\.?|s\.?c\.?r\.?l\.?|sc|scs|asbl|bv|nv|bvba|cvba|s[àa]rl|soci[ée]t[ée]\s+d['’]architectes?)\b\.?"


def _nom(apres):
    apres = re.sub(r"^\s*[:|–\-]*\s*\|?\s*", "", apres)
    m = re.match(r"NOM\s*(?:&|et)\s*Pr[ée]nom\s*:\s*(.+?)\s+Fonction", apres, re.I)
    if m:
        return m.group(1).strip()
    s = STOP.search(apres)
    nom = apres[:s.start()] if s else apres
    nom = re.sub(r"\s+", " ", nom).strip(" .:-|")[:70]
    if len(nom) < 3 or REJET.match(nom) or nom.isdigit() or "demander" in nom.lower() or AUTRE_ROLE.search(nom):
        return ""
    return nom


def role_of(lbl):
    l = lbl.lower()
    if "auteur" in l or "ontwerper" in l:
        return "Auteur de projet"
    if "architecte" in l:
        return "Architecte"
    return "Bureau d'études"


def extraire(items):
    """[{role, nom, ou}] depuis les passages « auteur » (texte recopié + emplacement)."""
    out, vus = [], set()
    for it in items or []:
        t = " ".join(str(it.get("texte", "")).split())
        for m in ROLE.finditer(t):
            apres = t[m.end():]
            avant = re.search(r"([A-Z][\w&.'’ ]{1,40}?)\s+[-–]\s*$", t[:m.start()])
            avant = avant.group(1).strip() if avant and not REJET.match(avant.group(1)) else ""
            if re.match(r"\s*[:|]", apres):
                nom = _nom(apres)
            elif avant:
                nom = avant
            elif m.start() < 5:
                nom = _nom(apres)
            else:
                nom = ""
            if nom:
                k = cle(nom)
                if k and k not in vus:
                    vus.add(k)
                    out.append({"role": role_of(m.group(1)), "nom": nom, "ou": it.get("ou")})
    return out


def cle(nom):
    s = unicodedata.normalize("NFD", nom.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(SIGLES, " ", s)
    s = re.sub(r"\b(cabinet|bureau|d['’]?architect\w*|architecture|architectes?)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)
