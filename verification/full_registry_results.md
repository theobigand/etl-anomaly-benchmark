# Resultats du registre complet de detecteurs

Protocole : `full_registry.md` (ecrit et archive avant tout run des nouveaux detecteurs, puis complete
avant les resultats par la section des ecarts a PyOD). Code : `research/full_registry.py`,
`research/full_registry_summary.py`, `research/labelled_benchmark.py --methods deep`,
`research/typed_run.py --methods deep`, `research/multi_schema.py --methods deep`. Preuves :
`evidence/full_registry/` (neuronaux), `evidence/labelled_pool/` et `evidence/typed_injection/`
(classiques rejoues), `evidence/*.csv` (benchmarks rejoues sur l'empreinte finale).

Les detecteurs deja presents redonnent exactement leurs anciens chiffres (ecart maximal 0,0 sur les
metriques, 576 couples methode-probleme du pool identiques) : l'environnement conda a change
(PyTorch ajoute) sans changer les resultats.

## Hypotheses

| | Enonce | Resultat | Valeurs |
| --- | --- | --- | --- |
| H1 | un nouveau detecteur classique depasse Isolation Forest sur le pool | soutenue | ECOD 0,240, HBOS 0,237, COPOD 0,216 contre 0,215 ; KNN 0,203, PCA 0,178 |
| H2 | aucun detecteur profond ne depasse le meilleur classique de plus de 0,02 | soutenue | DIF 0,226, VAE 0,216, AE1SVM 0,210 contre ECOD 0,240 |
| H3 | marges seules : rappel multivarie <= 0,20 et ecart d'au moins 0,50 avec Isolation Forest | non soutenue | ECOD 0,52, COPOD 0,51, HBOS 0,00 ; Isolation Forest 0,89 |
| H4 | PCA a moins de 0,10 de l'autoencodeur sur le multivarie | non soutenue | PCA 0,48, autoencodeur 0,83 |
| H5 | aucun nouveau detecteur ne depasse de plus de 0,10 le meilleur rappel de derive | non soutenue | LUNAR 0,65 contre LOF 0,50 ; les autres <= 0,41 |
| H6 | aucun detecteur profond n'echoue sur plus de 5 % des problemes | soutenue | 0 echec sur 100 problemes pour les six modeles |

H6 : AE1SVM avait plante sur deux problemes (`adbench:campaign`, `uci:176`) et sur une table injectee
avant le correctif du wrapper (dernier lot d'une ligne a l'ajustement et au score). Les deux problemes
du pool ont ete rejoues avec le code corrige, les tables injectees relancees ; les autres modeles ne
sont pas touches par le correctif (leurs scores par ligne sont identiques).

## Ce que les chiffres montrent

- Pool de 100 problemes : aucun detecteur ne domine. Chacun des dix-sept est premier sur au moins deux
  problemes, DIF au plus sur treize. Les modeles par colonne (ECOD, COPOD, HBOS) valent Isolation Forest.
- Matrice synthetique : LUNAR est le seul modele qui detecte la derive (0,65), mais il signale 41 % des
  lignes propres (autres modeles neuronaux : 9 % a 16 %). DIF et le VAE detectent les valeurs aberrantes
  multivariees comme Isolation Forest (1,00 et 0,92 contre 0,89).
- 42 tables injectees : meme profil que le synthetique pour LUNAR (multivarie 0,63, derive 0,78, 24 % des
  lignes propres signalees en mediane). La correlation de rang moyenne entre tables passe de 0,83 a 0,80
  avec les dix-sept detecteurs.
- Trois jeux reels : sur Credit Card, HBOS a la meilleure precision (0,34) et Deep SVDD le meilleur F1
  (0,35) ; sur Cardio, ECOD et COPOD egalent Isolation Forest (PR-AUC 0,69 contre 0,70) ; sur Water
  Quality, tous les modeles restent au niveau du hasard.
- Pilote chronologique (Credit Card) : rejoue avec ECOD, COPOD, HBOS et PCA ; les quatre lignes
  d'origine sont identiques. HBOS garde la meilleure precision moyenne chronologique (0,151).
- Schemas supplementaires : les hypotheses ecrites avant l'ajout ne changent pas (H1 et H4 soutenues,
  H2 et H3 non) ; la correlation de rang moyenne passe de 0,93 a 0,89 avec tous les detecteurs.

## Limites

Reglages par defaut de PyOD ; limite de 20 000 lignes d'ajustement pour les modeles neuronaux ; les
temps des runs neuronaux ont ete mesures en parallele et ne sont pas publies (la mesure de cout est
faite a part, machine au repos) ; les etudes de decisions sous derive ne contiennent que leurs quatre
detecteurs d'origine ; les intervalles a cinq graines sont indicatifs.
