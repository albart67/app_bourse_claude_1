# Bourse – analyse technique, fondamentale, ETF et portefeuille

## Onglet ETF
Catalogue d'ETF courants (Monde, USA, Europe, émergents, obligations, or), filtrable par catégorie et éligibilité PEA.
Pour chaque ETF : perf. sur la période, perf. annualisée, volatilité, perte max, ratio rendement/risque (tri par colonne).
Coche des ETF pour les comparer en base 100 ; « Ajouter » accepte n'importe quel symbole Yahoo. Le catalogue est la liste `ETFS` dans `app.py`.
L'onglet Fondamental affiche frais, encours, répartition sectorielle et principales lignes quand le symbole est un ETF.

## Lancer en local
    pip install -r requirements.txt
    uvicorn app:app --reload
Puis ouvrir http://localhost:8000

## Déployer
Le `Dockerfile` fonctionne tel quel sur Render, Railway, Fly.io ou Google Cloud Run (variable `PORT` gérée).

## Données
Yahoo Finance via `yfinance` (gratuit, sans clé, non officiel, délai possible).
Symboles : `AAPL`, `AIR.PA`, `MC.PA`, `^FCHI`…
Pour une API officielle (Alpha Vantage, FMP, Twelve Data), remplacer `history()` et `fundamentals()` dans `app.py`.

## Avertissement
Outil d'information uniquement, pas un conseil en investissement.
