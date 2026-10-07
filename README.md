# Radar Data — collecte automatique pour Radar Chantiers

Collecte gratuite, sans serveur, sur GitHub Actions (toutes les 6 h) :

| Source | Contenu | Étape Radar |
|---|---|---|
| TED (API officielle UE) | Avis Belgique + Grand-Duché, travaux (CPV 45), matériaux (44), études (71) | 1, 2, 4, 5 |
| urban.brussels NOVA | Gros projets de permis d'urbanisme à Bruxelles | 1 |

Résultats : `data/ted.json`, `data/permis_bruxelles.json` — chaque fiche contient sa source officielle.
Relancer à la main : onglet **Actions** → **Collecte** → **Run workflow**.

`discovery/` : recherche des flux e-Procurement (Belgique), RSS du portail luxembourgeois et lotissements wallons.
