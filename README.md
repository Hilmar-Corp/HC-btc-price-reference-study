# HC-btc-price-reference-study

[![Research Assurance](https://github.com/Hilmar-Corp/HC-btc-price-reference-study/actions/workflows/research-assurance.yml/badge.svg?branch=main)](https://github.com/Hilmar-Corp/HC-btc-price-reference-study/actions/workflows/research-assurance.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Research](https://img.shields.io/badge/research-multi--source-2ea44f)
![Assurance](https://img.shields.io/badge/assurance-fail--closed-2ea44f)
[![Licence Apache 2.0](https://img.shields.io/badge/licence-Apache--2.0-blue)](LICENSE)

Expérience reproductible accompagnant une note HilmarCorp Research consacrée à la construction d'un prix de référence pour Bitcoin.

**Qui fixe réellement le prix de Bitcoin ?**

Le dépôt étudie deux dimensions distinctes de la mesure du prix de Bitcoin :

- les différences observées entre plusieurs plateformes à un instant donné ;
- l'effet de la convention temporelle utilisée pour définir une valorisation quotidienne.

Le dépôt contient le code de recherche, les contrôles méthodologiques, les artefacts dérivés, les figures de publication et le dispositif d'assurance associé.

## Question de recherche

Bitcoin est négocié en continu sur plusieurs plateformes.

Il ne dispose ni d'une plateforme mondiale unique, ni d'une clôture quotidienne universelle comparable à la clôture officielle d'un marché organisé traditionnel.

La recherche distingue donc deux questions :

1. Dans quelle mesure les prix observés simultanément sur plusieurs plateformes diffèrent-ils ?
2. Dans quelle mesure la mesure d'un rendement quotidien dépend-elle de l'heure retenue comme frontière de valorisation ?

L'étude ne cherche pas à identifier un « vrai prix » unique de Bitcoin.

Elle documente la manière dont une référence de prix dépend de conventions explicites de source, d'horodatage et d'agrégation.

## Périmètre

Période principale :

    17 août 2017 au 10 août 2026

Sources principales :

    Coinbase BTC-USD
    Bitstamp BTC/USD

Source indépendante utilisée pour la revalidation d'événements extrêmes :

    Kraken BTC/USD

Fréquence principale :

    horaire

Conventions de valorisation quotidienne :

    00:00 UTC
    16:00 Europe/London
    16:00 America/New_York

Les conversions Londres et New York sont effectuées avec des fuseaux horaires IANA et tiennent compte des changements d'heure saisonniers.

## Méthodologie

Pour les prix de plateforme P(i,t), la référence de recherche à l'instant t est construite à partir de la médiane des sources disponibles :

    M(t) = médiane(P(1,t), ..., P(N,t))

La dispersion inter-plateformes est mesurée en points de base relativement à cette médiane :

    D(t) = 10 000 × [max(P(i,t)) - min(P(i,t))] / M(t)

La mesure du rendement quotidien dépend d'une heure de valorisation τ :

    r(t,τ) = P(t,τ) / P(t-1,τ) - 1

Cette construction permet de séparer :

- l'effet source : plusieurs plateformes à heure de valorisation identique ;
- l'effet frontière : une même règle de référence à différentes heures de valorisation.

## Principes de traitement des données

Le protocole applique les règles suivantes :

- normalisation des horodatages en UTC ;
- absence d'interpolation ;
- absence de forward-fill ;
- absence de fallback silencieux entre fournisseurs ;
- exclusion explicite des observations indisponibles ;
- contrôles de doublons ;
- contrôles de positivité et de finitude ;
- horodatages exacts ou fenêtres bornées explicitement ;
- conversion DST-aware des heures locales ;
- construction de la volatilité passée sans donnée de l'heure courante ;
- validation indépendante de certains événements extrêmes.

Les absences de données ne sont pas reconstruites artificiellement.

## Expériences produites

Le pipeline comporte cinq blocs principaux.

### 1. Dispersion inter-plateformes

Analyse horaire commune Coinbase / Bitstamp sur la période complète.

Artefacts principaux :

    artifacts/hourly_dispersion/

### 2. Revalidation des observations extrêmes

Les plus fortes dispersions horaires sont réexaminées à une granularité d'une minute.

Kraken est ajouté comme troisième source indépendante.

Artefacts principaux :

    artifacts/extreme_gap_validation/

### 3. Sensibilité à l'heure de valorisation

Comparaison des rendements quotidiens obtenus sous trois frontières :

    00:00 UTC
    16:00 Londres
    16:00 New York

Artefacts principaux :

    artifacts/valuation_boundary/

### 4. Dispersion et volatilité passée

Étude descriptive du lien entre la dispersion inter-plateformes et la volatilité réalisée sur les 24 heures calendaires strictement précédentes.

Artefacts principaux :

    artifacts/volatility_dispersion/

### 5. Assurance consolidée

Contrôle de cohérence du bundle de recherche final.

Artefacts principaux :

    artifacts/final_assurance/

## Figures de publication

Les figures finales sont générées dans :

    artifacts/publication_figures/

Le dossier contient les versions PNG et SVG.

Les figures couvrent :

1. l'évolution de la dispersion horaire inter-plateformes ;
2. la revalidation des écarts horaires extrêmes ;
3. un exemple de sensibilité du rendement à l'heure de valorisation ;
4. la comparaison de l'effet plateforme et de l'effet heure de valorisation ;
5. la relation descriptive entre volatilité passée et dispersion.

## Assurance de recherche

Le dépôt implémente un dispositif fail-closed.

La décision consolidée est enregistrée dans :

    artifacts/final_assurance/consolidated_decision.json

Le snapshot actuellement publié contient :

    16 contrôles requis
    16 contrôles validés
    0 contrôle en échec

Les domaines vérifiés couvrent notamment :

- capacité des sources historiques et récentes ;
- couverture des séries horaires ;
- cohérence de l'intersection Coinbase / Bitstamp ;
- cohérence du calcul de dispersion ;
- revalidation trois-sources des observations extrêmes ;
- validation à la minute ;
- couverture des dates de valorisation ;
- traitement du DST ;
- robustesse du calcul de volatilité sur 24 heures calendaires ;
- présence des artefacts contrôlés.

Le dépôt utilise également un registre SHA-256 des fichiers contrôlés :

    evidence/repository_evidence.json

## Couverture du coeur analytique

Le coeur analytique fait l'objet d'une mesure de couverture avec branches activées.

Seuils CI :

    couverture des lignes >= 85 %
    couverture des branches >= 75 %

Snapshot validé lors de la publication initiale :

    couverture des lignes : 97,94 %
    couverture des branches : 94,44 %

## Organisation du dépôt

    .
    ├── .github/
    │   └── workflows/
    │       └── research-assurance.yml
    ├── artifacts/
    │   ├── extreme_gap_validation/
    │   ├── final_assurance/
    │   ├── full_history_hourly/
    │   ├── gate3_validation/
    │   ├── hourly_dispersion/
    │   ├── publication_figures/
    │   ├── source_audit/
    │   ├── valuation_boundary/
    │   └── volatility_dispersion/
    ├── evidence/
    │   └── repository_evidence.json
    ├── scripts/
    │   └── research/
    ├── tests/
    ├── acquisition_protocol.json
    ├── research_contract.json
    ├── source_registry.json
    ├── DATA_NOTICE.md
    ├── REPRODUCIBILITY.md
    ├── RESEARCH_ASSURANCE.md
    ├── CITATION.cff
    ├── Makefile
    ├── LICENSE
    ├── NOTICE
    ├── pyproject.toml
    └── requirements-ci.txt

## Installation

Créer un environnement Python 3.12 :

    python3.12 -m venv .venv
    source .venv/bin/activate

Installer les dépendances contrôlées :

    python -m pip install --upgrade pip
    python -m pip install -r requirements-ci.txt
    python -m pip check

## Tests

Exécuter la suite complète :

    python -m pytest -q

Contrôler Ruff :

    python -m ruff format --check scripts tests
    python -m ruff check scripts tests

Contrôler la compilation :

    python -m compileall -q scripts tests

## Vérification du snapshot publié

Le snapshot publié peut être vérifié hors ligne sans redistribuer les données de marché brutes.

Exécuter :

    python -m scripts.research.verify_repository

Résultat attendu :

    REPOSITORY ASSURANCE: PASS

Cette vérification contrôle notamment :

- les empreintes SHA-256 ;
- les artefacts attendus ;
- la décision finale 16/16 ;
- l'absence de données brutes suivies par Git ;
- la présence de la licence Apache 2.0.

## Couverture analytique

Exécuter :

    make coverage

Résultat attendu :

    CORE COVERAGE GATE: PASS

## Assurance complète

Exécuter :

    make assurance

Cette commande regroupe :

- contrôle de format ;
- lint ;
- compilation ;
- tests ;
- vérification du snapshot ;
- couverture du coeur analytique.

## Reproduction complète

Une reproduction complète depuis les sources de données suit la séquence :

    python -m scripts.research.source_capability_probe
    python -m scripts.research.hourly_history
    python -m scripts.research.hourly_dispersion_analysis
    python -m scripts.research.extreme_gap_validation --top 40
    python -m scripts.research.valuation_boundary_analysis
    python -m scripts.research.volatility_dispersion_analysis
    python -m scripts.research.final_assurance
    python -m scripts.research.publication_figures

Voir :

    REPRODUCIBILITY.md

pour les détails du protocole.

## Données de marché

Les caches complets de données de marché tierces ne sont pas redistribués dans le dépôt public.

Le dépôt permet :

- la vérification exacte des artefacts dérivés publiés ;
- la reproduction méthodologique après nouvelle acquisition des données.

Les données tierces restent soumises aux droits et conditions de leurs fournisseurs respectifs.

Voir :

    DATA_NOTICE.md

## Limites d'interprétation

Cette expérience est descriptive.

Elle ne constitue pas :

- un modèle de prévision ;
- une stratégie d'investissement ;
- une preuve de causalité entre volatilité et dispersion ;
- une définition officielle d'un benchmark Bitcoin ;
- une démonstration de l'existence d'un prix unique de Bitcoin ;
- un conseil en investissement.

Les résultats sont conditionnels :

- aux plateformes étudiées ;
- à la période étudiée ;
- aux granularités utilisées ;
- aux conventions d'horodatage ;
- aux règles de construction définies dans le protocole.

## Documentation d'assurance

Documentation associée :

- `RESEARCH_ASSURANCE.md`
- `REPRODUCIBILITY.md`
- `DATA_NOTICE.md`
- `research_contract.json`
- `source_registry.json`
- `acquisition_protocol.json`
- `evidence/repository_evidence.json`

## Licence

Le code original, les tests, les scripts d'automatisation et la documentation originale sont publiés sous licence Apache 2.0.

Les données de marché tierces restent soumises aux conditions et droits applicables de leurs fournisseurs respectifs.

Voir :

    LICENSE
    NOTICE
    DATA_NOTICE.md

## Disclaimer

Ce dépôt est fourni à des fins de recherche quantitative et de pédagogie financière.

Il ne constitue ni un conseil en investissement, ni une recommandation, ni une prévision, ni une offre d'achat ou de vente d'un actif numérique ou d'un instrument financier.

Les résultats sont historiques et conditionnels aux conventions décrites dans le dépôt.
