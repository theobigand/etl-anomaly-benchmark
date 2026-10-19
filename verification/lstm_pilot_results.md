# Résultats du pilote LSTM-autoencodeur (issue 52)

Protocole : `lstm_pilot.md` (commit `8b4833e`, écrit avant toute exécution).
Code : `research/lstm_detector.py`, `research/lstm_pilot.py`,
`research/paired_bootstrap.py` ; tests : `research/tests/` (16 tests, sans GPU,
lancés avec l'environnement de `research/requirements-lstm.txt`, hors FAST).
Résultats et provenance : `evidence/lstm_pilot/` (jeu sha256 `76274b69...`,
PyTorch 2.14.1, numpy 2.4.6, CPU, macOS arm64, 10 coeurs, empreinte scientifique
`cecbed00`, arbre propre). Une seconde exécution complète donne les mêmes
résultats (hors durée) : les réglages de déterminisme tiennent sur ce matériel.

## Contrôle de faisabilité synthétique (porte du protocole)

Flux AR(1) de 24 000 lignes, 1 % d'anomalies qui retournent le signe de l'état
précédent (valeurs plausibles, enchaînement impossible). Test de 3 600 lignes :
LSTM PR-AUC 0,875, autoencodeur par ligne 0,006 ; différence 0,869, intervalle
[0,752 ; 0,992]. La porte est franchie : l'implémentation voit bien un contexte
séquentiel. L'entraînement a atteint le plafond de 20 époques sans arrêt anticipé.

## Credit Card, partition chronologique (test : 42 557 lignes, 52 fraudes)

| Graine | PR-AUC autoencodeur | PR-AUC LSTM | Différence LSTM - AE [IC 95 % par blocs] |
| --- | --- | --- | --- |
| 42 (principale) | 0,0091 | 0,0302 | +0,0212 [+0,0047 ; +0,0439] |
| 1 | 0,0248 | 0,0453 | +0,0204 [-0,0302 ; +0,0542] |
| 2 | 0,0237 | 0,0367 | +0,0130 [-0,0327 ; +0,0378] |
| 3 | 0,0278 | 0,0416 | +0,0138 [-0,0338 ; +0,0459] |
| 4 | 0,0350 | 0,0320 | -0,0031 [-0,0561 ; +0,0264] |

Moyennes sur les cinq graines : autoencodeur 0,0241 (écart type 0,0095), LSTM
0,0371 (0,0063) ; ROC-AUC 0,841 contre 0,926. La prévalence de test est 0,0012.

- **H1 (critère exploratoire) : satisfaite pour la graine principale** (intervalle
  de la différence excluant zéro), **non établie sur les quatre autres graines**
  (différence positive pour trois, négative pour une, intervalle contenant zéro).
  L'autoencodeur par ligne est très instable selon le sous-échantillon de 50 000
  lignes (PR-AUC de 0,009 à 0,035). Le critère reste exploratoire : 52 fraudes,
  une seule période, aucun test formel.
- **H2 (le LSTM reste sous Isolation Forest et Great Expectations) : non
  soutenue au sens strict.** Références du pilote 51 sur les mêmes lignes de test :
  Isolation Forest 0,0352, Great Expectations 0,0447. Le LSTM va de 0,0302 à
  0,0453 : il dépasse Isolation Forest sur trois graines sur cinq et Great
  Expectations sur une (de 0,0006), à des écarts bien inférieurs aux intervalles.
  Le LSTM est donc comparable à ces références, pas meilleur de façon établie.
- **Convergence : aucune exécution n'a convergé** au sens du protocole. Les cinq
  entraînements ont atteint le plafond de 20 époques, avec la meilleure époque à
  19 ou 20 : la perte de validation baissait encore. Les résultats sont ceux d'un
  budget épuisé (environ 20 s par entraînement), pas d'un modèle abouti.
- **Point de fonctionnement :** malgré un ROC-AUC de 0,92, le seuil fixé sur les
  scores d'entraînement ne détecte presque aucune fraude (rappel 0 à 0,019),
  comme Isolation Forest au pilote 51 : le classement des scores se transfère,
  pas le seuil.

## Ce que ce pilote ne dit pas

Pas d'identifiant de porteur : la fenêtre est le flux global des 10 lignes
précédentes, pas l'historique d'un client. Un budget de 20 époques non convergé,
une architecture unique choisie à l'avance, 52 fraudes en test et deux jours de
données : le gain observé est une indication, pas une conclusion. Un budget plus
large serait un nouveau protocole, à pré-enregistrer.
