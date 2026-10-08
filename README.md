# Radar Data — collecte automatique pour Radar Chantiers

Collecte gratuite sur GitHub Actions, toutes les 6 h. Chaque fiche contient le lien vers sa source officielle.

| Source | Contenu | Fichier |
|---|---|---|
| TED (API officielle UE) | Avis européens Belgique + Grand-Duché : travaux (CPV 45), matériaux (44), études (71) | `data/ted.json` |
| Bulletin des Adjudications (e-Procurement, SPF BOSA) | Tous les avis belges, y compris sous les seuils européens | `data/bda.json` |
| urban.brussels NOVA | Gros projets de permis d'urbanisme à Bruxelles | `data/permis_bruxelles.json` |

Étapes Radar : 1 projet repéré (préinformation, étude lancée, permis) · 2 bureau d'études connu (mission d'étude attribuée) · 4 publié · 5 attribué.
Types d'avis BDA selon la table officielle eForms : https://docs.ted.europa.eu/eforms/1.13/schema/documents-forms-and-notices.html

État de la dernière collecte : `data/_etat.json`. Relancer à la main : onglet **Actions** → **Collecte** → **Run workflow**.

Non couvert : permis wallons et luxembourgeois (pas de données ouvertes exploitables), portail luxembourgeois des marchés (connexion obligatoire), lotissements wallons (données en retard : 1 décision depuis juillet 2026).

## Page « Radar Chantiers Public »
`page/index.html` est la page publiée sur claude.ai : https://claude.ai/artifact/3ai4wX3L6GtBhuyjsnpgQJ
Elle affiche `data/radar_public.json` (republié chaque matin par une tâche planifiée Claude).
