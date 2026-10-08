"""Nomenclature de la gamme Fischer, relevée sur fischer.be/fr-be/produits le 08/10/2026
(coupe-feu : absent de fischer.be, relevé sur fischer.fr/fr-fr/produits/firestop-coupe-feu).
Chaque famille : produits (noms exacts du site), page source, et les formulations qu'un cahier des charges
utilise pour décrire ce besoin (FR + NL). Ces formulations sont des règles de correspondance, pas des
données Fischer : la correspondance proposée est toujours « à valider »."""
import re

BE = "https://www.fischer.be/fr-be/produits/"
FR = "https://www.fischer.fr/fr-fr/produits/"
FIX = r"(?:fix\w*|cheville\w*|ancr\w*|bevestig\w*|plug\w*|anker\w*)"

FAMILLES = [
    {"id": "chimique", "nom": "Fixation chimique (scellement par injection)",
     "produits": ["FIS EM Plus", "FIS V Plus", "FIS SB", "FIS HB", "FIS V Zero", "Ampoules FHB II / RM II", "Tiges FIS A / RG M", "Douilles FIS E / RG MI"],
     "url": BE + "fixations-chimiques",
     "termes": r"scellements?\s+chimiques?|ancrages?\s+chimiques?|fixations?\s+chimiques?|r[ée]sines?\s+(?:d['’]injection|d['’]ancrage|de\s+scellement|[ée]poxy|vinylester)|"
               r"mortiers?\s+d['’]injection|ampoules?\s+de\s+r[ée]sine|chevilles?\s+chimiques?|chemische?\s+ankers?|injectiemortel|chemisch\s+verankerd"},
    {"id": "armatures", "nom": "Scellement d'armatures et renforcement",
     "produits": ["FIS EM Plus (fers à béton)", "Barre de traction FRA", "Armature VBS", "Connecteur de cisaillement FCC"],
     "url": BE + "renovation-renforcement",
     "termes": r"scellements?\s+(?:de|des|d['’])\s*(?:fers|armatures?|barres?|aciers?)|armatures?\s+(?:rapport[ée]es|post-?install[ée]es|scell[ée]es|ancr[ée]es)|"
               r"reprises?\s+de\s+b[ée]tonnage|connecteurs?\s+de\s+cisaillement|goujons?\s+de\s+cisaillement|wapening\s+(?:inboren|verlijmen|verankeren)|EAD\s+330087"},
    {"id": "reparation", "nom": "Mortiers de réparation du béton",
     "produits": ["CreNovate R2 / R3 / R4", "Agent de liaison anticorrosion", "Coulis de ciment", "FastFill"],
     "url": BE + "renovation-renforcement/mortier-de-reparation-crenovate",
     "termes": r"mortiers?\s+de\s+r[ée]paration|r[ée]paration\s+(?:du|des|de)\s+b[ée]tons?|EN\s*1504-3|passivation\s+des\s+armatures|betonherstel\w*"},
    {"id": "goujon", "nom": "Goujons d'ancrage (béton)",
     "produits": ["FAZ II Plus", "FBN II", "FWA Plus"],
     "url": BE + "chevilles-metalliques/goujon-d-ancrage",
     "termes": r"goujons?\s+d['’]ancrage|chevilles?\s+(?:m[ée]caniques?|m[ée]talliques?|acier)\s+[àa]\s+expansion|ancrages?\s+m[ée]caniques?|"
               r"expansion\s+contr[ôo]l[ée]e|dispositifs?\s+d['’]expansion|keilbouten?|keilankers?|expansieankers?|goujons?\s+(?:inox|galvanis[ée]s?|M\d{1,2})"},
    {"id": "vis_beton", "nom": "Vis à béton",
     "produits": ["UltraCut FBS II", "FBS 5"],
     "url": BE + "chevilles-metalliques/vis-a-beton",
     "termes": r"vis\s+(?:[àa]\s+b[ée]ton|d['’]ancrage\s+(?:dans|pour)\s+(?:le\s+)?b[ée]ton)|betonschroe(?:f|ven)"},
    {"id": "lourde", "nom": "Chevilles lourdes à douille / à dépouille",
     "produits": ["FH II", "FSA", "TA M", "ZYKON FZA", "FSU"],
     "url": BE + "chevilles-metalliques/cheville-a-douille",
     "termes": r"chevilles?\s+(?:lourdes?|[àa]\s+douille|hautes?\s+performances?)|ancrages?\s+lourds?|d[ée]pouille\s+arri[èe]re|ondersnijdingsankers?|hulsankers?|zwaarlastankers?"},
    {"id": "frapper", "nom": "Chevilles à frapper et suspension de plafonds",
     "produits": ["FNA II", "EA II", "Suspente trapézoïdale TZ", "Cheville à bascule KDS"],
     "url": BE + "chevilles-metalliques/cheville-clou",
     "termes": r"chevilles?\s+(?:[àa]\s+frapper|femelles?|clous?)|(?:faux|plafonds?)[\s-]+plafonds?\s+suspendus?|suspentes?\s+(?:de|du|des)\s+(?:faux[\s-]?)?plafonds?|"
               r"suspension\s+(?:de|du|des)\s+(?:faux[\s-]?)?plafonds?|inslagankers?|plafondankers?"},
    {"id": "insert", "nom": "Rails d'ancrage à couler (insert)",
     "produits": ["InnoLock FES-RS-S", "FES-H", "FES-C", "Boulons FBC"],
     "url": BE + "cast-in-channel-system-systeme-de-rails-insert",
     "termes": r"rails?\s+(?:d['’]ancrage|insert|[àa]\s+couler|noy[ée]s?|(?:incorpor|int[ée]gr)[ée]s?\s+(?:au|dans\s+le)\s+b[ée]ton)|ankerrails?|ingestorte\s+rails?|halfen|jordahl"},
    {"id": "rails", "nom": "Rails de montage et consoles (supportage)",
     "produits": ["Rails légers FLS", "Rails FUS", "Rails charges lourdes FMS", "Consoles FCA / ALK", "Platines FCN / FSM Clix"],
     "url": BE + "techniques-de-supportage/systeme-de-rails",
     "termes": r"rails?\s+(?:de\s+montage|l[ée]gers?|perfor[ée]s?|profil[ée]s?)|profil[ée]s?\s+de\s+montage|syst[èe]mes?\s+de\s+(?:supportage|montage\s+(?:mod|par\s+rails))|"
               r"supportage\s+(?:des|de|du)\s+(?:gaines|tuyauteries|conduites|canalisations|chemins|r[ée]seaux|c[âa]bles|[ée]quipements)|consoles?\s+(?:murales?|de\s+supportage|support)|"
               r"chemins?\s+de\s+c[âa]bles|moyens?\s+de\s+supportage|montagerails?|draagsysteem|ophangsysteem|steunconstructie"},
    {"id": "colliers", "nom": "Colliers de tuyauterie et ventilation",
     "produits": ["FRS / FRS Plus", "FGRS", "Collier froid FRSK", "Colliers ventilation LGS", "Collier poire FRSP"],
     "url": BE + "techniques-de-supportage/colliers",
     "termes": r"colliers?\s+(?:isophoniques?|de\s+fixation|pour\s+tuyau\w*|de\s+serrage|[àa]\s+(?:caoutchouc|garniture|double\s+vis)|de\s+ventilation|pour\s+gaines?)|"
               r"colliers?\s+(?:anti-?)?vibratiles?|buisbeugels?|(?:fixation|suspension)\s+des\s+(?:tuyauteries|conduites|gaines)|tiges?\s+filet[ée]es?\s+et\s+colliers?"},
    {"id": "pointfixe", "nom": "Points fixes et guides coulissants",
     "produits": ["Point fixe FSFP", "Collier point fixe FFPC", "Coulisseaux FSC", "Éléments pendulaires PDH"],
     "url": BE + "techniques-de-supportage/point-fixe",
     "termes": r"points?\s+fixes?|guides?\s+(?:coulissants?|de\s+dilatation)|coulisseaux?|vaste\s+punten?|glijbeugels?"},
    {"id": "electro", "nom": "Électro-fixations (câbles et tubes)",
     "produits": ["Étrier SHA", "Arceau KB", "ClipFix plus", "Pontets BSM", "Clips RC / SCN"],
     "url": BE + "electro-fixations",
     "termes": r"(?:fixations?|attaches?|colliers?|brides?)\s+(?:de|des|pour)\s+(?:c[âa]bles|tubes?\s+[ée]lectriques?|gaines?\s+[ée]lectriques?)|"
               r"c[âa]bles\s+(?:fix[ée]s|attach[ée]s)|kabelbeugels?|kabelklemmen"},
    {"id": "sanitaire", "nom": "Fixations sanitaires",
     "produits": ["WST II (lavabos)", "UST (urinoirs)", "WC WCN / WB 5N", "WDP (sur panneaux)", "Fixation chauffe-eau"],
     "url": BE + "fixations-sanitaires",
     "termes": r"(?:fixations?|consoles?|scellements?)\s+(?:de|des|du|pour)\s+(?:lavabos?|lave-mains?|wc|urinoirs?|appareils?\s+sanitaires?|chauffe-eau|boilers?|cuvettes?)|"
               r"(?:lavabos?|urinoirs?|wc\s+suspendus?|chauffe-eau|boilers?)\s+(?:fix[ée]s?|suspendus?|ancr[ée]s?)|sanitaire\s+bevestiging\w*"},
    {"id": "isolant", "nom": "Chevilles d'isolant (ETICS, isolation)",
     "produits": ["TermoZ CN plus", "TermoZ CS II", "TermoZ SV II ecotwist", "Fixations isolant DHK / DHM", "FIF-CN II 8"],
     "url": BE + "fixations-d-isolants",
     "termes": r"chevilles?\s+(?:d['’]isolants?|pour\s+isolants?|[àa]\s+rosace|[àa]\s+frapper\s+pour\s+isolants?)|ETICS|isolations?\s+(?:thermiques?\s+)?(?:ext[ée]rieures?|par\s+l['’]ext[ée]rieur)|"
               r"enduits?\s+sur\s+isolants?|(?:fixation|chevillage)\s+(?:m[ée]canique\s+)?(?:de\s+l['’]|des\s+)isolants?|isolatiepluggen|schotelpluggen|buitengevelisolatie"},
    {"id": "thermax", "nom": "Fixation à travers l'isolation (montage à distance)",
     "produits": ["TherMax 8 / 10", "TherMax II", "FID II / FID II Plus"],
     "url": BE + "fixation-sur-etics-isolation",
     "termes": r"(?:fix\w+|ancr\w+|mont\w+)\s+(?:[àa]\s+travers|dans)\s+(?:l['’])?(?:isolant|isolation|ETICS)|montage\s+[àa]\s+distance|"
               r"(?:auvents?|marquises?|garde-corps|volets?|stores?|luminaires?)\s+(?:\w+\s+){0,3}sur\s+(?:fa[cç]ade\s+isol[ée]e|ETICS|isolant)|afstandsmontage"},
    {"id": "cadre", "nom": "Fixation de châssis et chevilles rallongées",
     "produits": ["SXR / SXRL", "DuoXpand", "F-S / F-M", "Vis de cadre FFS / FFSZ"],
     "url": BE + "fixations-pour-cadres-de-fenetre",
     "termes": r"chevilles?\s+(?:de\s+(?:cadre|ch[âa]ssis)|rallong[ée]es?|longues?)|(?:fixation|ancrage)s?\s+(?:des\s+)?(?:ch[âa]ssis|menuiseries?|cadres?|huisseries?|portes?\s+et\s+fen[êe]tres)|"
               r"vis\s+de\s+(?:cadre|ch[âa]ssis|r[ée]glage)|kozijnpluggen|kozijnschroeven|raamankers?"},
    {"id": "nylon", "nom": "Chevilles nylon universelles",
     "produits": ["DuoPower", "UX", "SX Plus", "HybridPower"],
     "url": BE + "fixations-courantes/chevilles-en-nylon",
     "termes": r"chevilles?\s+(?:en\s+(?:nylon|PVC|P\.V\.C\.)|nylon|universelles?|plastiques?|[àa]\s+expansion\s+(?:en\s+)?(?:nylon|plastique))|nylonpluggen|kunststofpluggen"},
    {"id": "creux", "nom": "Fixation en corps creux et plaques de plâtre",
     "produits": ["DuoTec", "DuoBlade", "HM / DuoHM", "Chevilles à bascule KD"],
     "url": BE + "fixations-pour-corps-creux",
     "termes": FIX + r"\w*\s+(?:\w+\s+){0,4}(?:plaques?\s+de\s+pl[âa]tre|cloisons?\s+(?:l[ée]g[èe]res?|s[èe]ches|creuses?)|corps\s+creux|gipsplaten?)|chevilles?\s+(?:[àa]\s+bascule|pour\s+(?:corps\s+creux|plaques?))|hollewandpluggen"},
    {"id": "cellulaire", "nom": "Fixation dans le béton cellulaire",
     "produits": ["FPX-I", "GB", "FTP"],
     "url": BE + "fixations-courantes/chevilles-en-nylon/cheville-pour-beton-cellulaire-gb",
     "termes": FIX + r"\w*\s+(?:\w+\s+){0,4}(?:b[ée]ton\s+cellulaire|cellenbeton|ytong)"},
    {"id": "vis_bois", "nom": "Vis bois et charpente",
     "produits": ["PowerFast II", "PowerFull II", "Tirefond PowerFast II HWTF"],
     "url": BE + "gamme-de-vis",
     "termes": r"vis\s+(?:[àa]\s+bois|de\s+charpente|[àa]\s+filetage\s+total|autoforeuses?\s+(?:pour|dans)\s+(?:le\s+)?bois|inox\s+(?:pour|dans)\s+(?:le\s+)?bois)|tire-?fonds?|houtschroe(?:f|ven)|constructieschroe(?:f|ven)"},
    {"id": "bardage", "nom": "Façades ventilées, bardage et terrasses",
     "produits": ["ACT (façades ventilées)", "Vis de façade FFSII", "Terradec / vis de terrasse FTS"],
     "url": BE + "act-systemes-de-facades-ventilees",
     "termes": r"fa[cç]ades?\s+ventil[ée]es?|bardages?\s+(?:ventil[ée]s?|bois|m[ée]talliques?|en\s+panneaux)|sous-?structures?\s+(?:de\s+(?:la\s+)?fa[cç]ade|du\s+bardage|aluminium)|"
               r"vis\s+de\s+(?:fa[cç]ade|bardage|terrasse)|geventileerde\s+gevel\w*|gevelbekleding"},
    {"id": "echafaudage", "nom": "Ancrages d'échafaudage et anneaux",
     "produits": ["Piton GS 12", "Chevilles S 14 ROE", "Anneau de levage RI"],
     "url": BE + "fixations-d-echafaudages-et-de-pitons",
     "termes": r"ancrages?\s+(?:d['’]|des\s+)[ée]chafaudages?|pitons?\s+d['’][ée]chafaudage|steigerankers?"},
    {"id": "chimie_bat", "nom": "Mousses et mastics",
     "produits": ["Mousse PU Premium", "Silicone DBSA / DSSA", "Mastic acrylique Multi AC", "Colle Multi MS"],
     "url": BE + "chimie-du-batiment",
     "termes": r"mousses?\s+(?:PU|polyur[ée]thane|expansive|de\s+montage)|mastics?\s+(?:silicone|acrylique|[ée]lastique|polyur[ée]thane|hybride|MS)|PU-?schuim"},
    {"id": "coupe_feu", "nom": "Coupe-feu (FireStop)",
     "produits": ["Mastic FFRS / FiAM / FiGM", "ElastoSeal FFB-ES Plus", "Mortier FFSC", "Collier FFC", "Bande FiPW", "Panneau FCPS", "Foam Barrier System PLUS", "Sacs FiP"],
     "url": FR + "firestop-coupe-feu",
     "termes": r"(?:mastics?|mortiers?|mousses?|colliers?|manchons?|manchettes?|bandes?|panneaux?|coussins?|sacs?|plaques?|enduits?|joints?)\s+(?:\w+\s+){0,2}(?:coupe-feu|intumescent\w*|r[ée]sistant\w*\s+au\s+feu)|"
               r"(?:calfeutrements?|obturations?|traversées?|r[ée]servations?|percements?)\s+(?:\w+\s+){0,4}(?:coupe-feu|r[ée]sistant\w*\s+au\s+feu|EI\s?\d{2,3}|Rf\s?\d)|"
               r"brandwerende?\s+(?:afdichting|manchet|kit|mastiek|doorvoer|mortel)\w*|brandmanchet\w*"},
]
for f in FAMILLES:
    f["rx"] = re.compile(r"\b(?:" + f["termes"] + r")", re.I)

# familles absentes du site belge : on le dit au lieu de proposer
HORS_GAMME_BE = {"coupe_feu": "gamme présentée sur fischer.fr, pas sur fischer.be : vérifier la disponibilité en Belgique"}


def familles(texte):
    """Familles Fischer dont la formulation apparaît dans le passage (ordre du catalogue)."""
    return [f for f in FAMILLES if f["rx"].search(texte)]


def resume(f):
    return {"id": f["id"], "famille": f["nom"], "produits": f["produits"], "url": f["url"],
            **({"remarque": HORS_GAMME_BE[f["id"]]} if f["id"] in HORS_GAMME_BE else {})}
