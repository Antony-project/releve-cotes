# Relevé des cotes — simulateur « Toi contre Claude »

Ce dépôt relève automatiquement, trois fois par jour (vers 6 h 40, 12 h 40 et 17 h 40 à Paris l'hiver, souvent avec un peu de retard), les cotes « vainqueur du match » de
**Betclic**, Pinnacle, Unibet et Winamax via [The Odds API](https://the-odds-api.com), pour le
tennis masculin (Grands Chelems, Masters 1000, ATP 500) et le MMA (UFC).

- `data/latest.json` : dernier relevé (matchs, cotes par bookmaker, probabilités sans marge).
- `data/snapshots/` : historique des relevés (60 jours), pour retrouver la cote juste avant chaque match.
- `data/status.json` : état du dernier passage et crédits restants.

La clé de l'API est rangée dans les secrets GitHub (`ODDS_API_KEY`) et n'apparaît jamais ici.
Coût : 1 crédit par compétition et par relevé, soit environ 6 à 9 crédits par jour (quota gratuit : 500 par mois).

Les données sont lues par la tâche quotidienne de Claude, qui les reprend dans la page du simulateur.
