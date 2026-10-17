# État des vérifications

Le dépôt contient le pipeline Python (`src/etl_benchmark`), les expériences
(`experiments`) et le manuscrit. Les chiffres ci-dessous décrivent chacun une
exécution identifiée (révision, lieu, date) ; ils sont recopiés dans
`claims.json`, dont les preuves sont scellées sous `evidence/runs/`, et
`tests/test_claims_provenance.py` refuse un chiffre dont le code a changé
depuis. Les chiffres plus anciens sont marqués historiques.

Le statut de certification est **INCOMPLETE à distance** et **CERTIFIED en
local, non attesté** : toutes les preuves exigées par `release_policy.json`
existent pour le commit `ffa02b2f` sur la machine du chercheur, mais la preuve
REAL (jeux complets) ne peut pas être produite par un exécuteur hébergé et
aucun exécuteur autorisé n'est enregistré. Voir `certification.md` pour ce que
ce verdict prouve et ne prouve pas. Restent ouverts le modèle LSTM,
l'évaluation chronologique sur données réelles, l'étude de coût en environnement
contrôlé et les points de la section « Travail restant ».

## Point de départ et corrections

Au départ, 76 tests et Ruff tournaient dans la CI. Il n'y avait ni mesure de
couverture par branche, ni campagne de mutation, ni contrôle séparé des CSV
réels. Les fichiers de données étaient disponibles sur cette machine.

Les tests ajoutés ont mis en évidence plusieurs erreurs : une copie
synthétique pouvait se retrouver des deux côtés du découpage, la déduplication
regardait les données avant ce découpage, une série de stratification réordonnée
était utilisée par position, et un taux d'injection nul créait encore des
anomalies. Nous avons aussi corrigé la normalisation silencieuse des labels
manquants, les métriques non définies et l'acceptation de sorties de détecteur
mal alignées. Une colonne d'entraînement entièrement vide ou infinie pouvait
aussi produire des scores nuls dans les règles statistiques ; ces entrées sont
maintenant rejetées. Les cas de régression sont dans `tests/test_scientific_contracts.py`,
`test_split.py`, `test_dataset_contract.py`, `test_metric_contract.py` et
`test_detector_protocol.py` et `test_adverse_schemas.py`. Chaque correctif a été précédé d'un échec ciblé,
puis contrôlé avec le même test après modification.

Les expériences synthétiques ont été relancées après ces changements. Les
trois benchmarks réels ont ensuite été rejoués avec cinq graines chacun. Les
quatre tableaux principaux du manuscrit sont comparés aux CSV archivés par
`test_publication_tables.py` ; ce contrôle a révélé neuf arrondis à corriger.
Les figures et le PDF ont été reconstruits. Le découpage chronologique et le
suivi par fenêtres ont leurs propres tests ; ils ne changent pas les métriques
du benchmark stratifié.
Une comparaison supplémentaire emploie une contamination fixe de 0,02 pour
les détecteurs classiques sur les trois jeux réels. Elle réutilise les mêmes
partitions, mais demeure exploratoire : sa valeur a été fixée après lecture
des résultats du protocole principal. Les fichiers correspondants sont
archivés séparément et leurs chiffres sont rapprochés du manuscrit par un test.

## Résultats des commandes

Run local `local-ffa02b2` : commit `ffa02b2f`, macOS 27.0 arm64, Python 3.11.17
(environnement conda `etl-benchmark`, typage dans un venv avec mypy 2.4.0 et
pandas-stubs 3.0.5.260914), 17 octobre 2026. Résultats non attestés
indépendamment ; enveloppes de preuve scellées dans `evidence/runs/local-ffa02b2/`.

| Commande | Résultat | Détail |
| --- | --- | --- |
| `make verify-fast` | Réussite locale | 1 030 tests réussis, 3 tests réels et 23 essais de défauts exclus ; 1 576/1 576 lignes et 332/332 branches. |
| `make verify-tools` | Réussite locale | 1 566/1 566 lignes et 576/576 branches du code de `verification/`. |
| `make verify-types` | Réussite locale | mypy 2.4.0, `verification/` sans erreur, 17 erreurs connues du code scientifique, aucune nouvelle. |
| `make verify-deep` | Réussite locale | 4 707 mutants éliminés sur 4 815 (97,76 %) ; 108 survivants, dont 3 propres à macOS. |
| `make verify-faults` | Réussite locale | 23 défauts introduits dans une copie temporaire, tous détectés par un test prévu. |
| `make verify-real` | Réussite locale | 3 tests et contrôle des trois CSV requis ; échoue si l'un manque ou si le registre est vide. |
| `make verify-reproduce` | Réussite locale | cardio : archive, deux essais, environnement reconstruit depuis le verrou : numérique, écart 0,0 ; sensibilité à scikit-learn 1.8.0 mesurée. |
| `make verify-release` | CERTIFIED (local, non attesté) | les sept preuves de `release_policy.json` pour ce commit ; mesure de coût `LEGACY`. |

FAST mesure **1 576/1 576 lignes et 332/332 branches (100 % chacune)** ; le code
de vérification de `verification/` est mesuré à part (`make verify-tools`). La
mesure inclut les commandes lancées en sous-processus. Le détail par fichier
est dans le profil généré `verification/profile.json` et `coverage.json`. Aucune
ligne ni branche n'est exclue.

La campagne de mutation porte sur les modules de `src/etl_benchmark` qui
calculent un résultat et sur les dix scripts de `experiments/` (mutmut 3.8.0),
soit 28 fichiers dont 27 reçoivent des mutants (relevé indépendant dans
`mutation_scope.json`) : 4 815 mutants produits, 4 707 éliminés, 108 survivants,
aucun cas classé sans test, ignoré, expiré ou interrompu. Le taux mesuré est
**97,76 %**, dont 95,76 % sur le calcul scientifique seul (1 647/1 720) et
98,87 % sur l'orchestration et les scripts (3 060/3 095) ; voir
`mutation_notes.md`. La campagne avait commencé à 88,66 % sur `metrics.py` seul,
à 74,5 % une fois élargie à `src/` sans nouveaux tests et à 24,3 % sur les
scripts. `mutation_notes.md` classe les survivants par lecture des diffs
(valeurs par défaut de bibliothèques, noms internes) ; ce classement est une
hypothèse, pas une preuve. Le profil généré par FAST garde un champ de mutation
à zéro : il signifie « non lancé par FAST », pas un score nul.

Chiffres historiques, à ne pas confondre avec les précédents : 771 tests,
1 531 lignes et 320 branches, 732/218 pour le code de vérification, 4 643 sur
4 751 mutants (97,73 %) décrivaient le run local du commit `3779905` (16 octobre
2026), avant la remédiation des anomalies 38 à 49. Les mesures Linux de la CI
(run 38974460893, commit `292648a`) sont rapportées dans « Exécutions en CI ».

## Rejeu du 15 octobre 2026

Tous les essais archivés ont été rejoués sur le code courant (banc synthétique,
sévérité, courbes, trois jeux réels, trois calibrages fixes, étude de
croissance). Toutes les métriques de détection, les courbes, les scores par
type et les partitions exactes (contenu des archives décompressées) sont
identiques à l'archive précédente (écart inférieur à 1e-9). Seuls les temps de
calcul (`detect_s`) et l'allocation Python mesurée par l'étude de croissance
varient. Les enregistrements des essais gardent maintenant les détecteurs non exécutés avec leur raison (`not_run`) et les jeux
demandés mais absents (`skipped_datasets`). Les deux tableaux du manuscrit qui
affichent des temps et le paragraphe sur la montée en charge ont été mis à
jour ; les figures sont identiques octet pour octet.

## Rejeu du 16 octobre 2026

Les mêmes essais (banc synthétique, sévérité, courbes, trois jeux réels avec
calibrage sur la prévalence puis fixe, étude de croissance) ont été rejoués depuis
le commit propre `93b6fe8`, arbre de travail vierge avant et après. Le seul
écart par rapport à l'archive du 15 octobre concerne les temps : toutes les
mesures de détection, les courbes, les partitions et les figures sont
identiques (écart maximal 0,0 sur chaque CSV archivé). Les enregistrements
portent désormais la recette d'empreinte 2, `worktree_dirty: false` et le
condensé du verrou d'environnement. Les deux tableaux de temps et le paragraphe
de croissance du manuscrit ont été mis à jour avec les nouvelles mesures ; les
anciens enregistrements restent dans l'historique git (commit `7977dee`).

## Ce que les contrôles couvrent

Les tests unitaires, de contrat, d'intégration, de propriété et de CLI
utilisent de petits jeux construits dans des répertoires temporaires. FAST ne
lit pas les CSV de recherche et ne demande pas d'accès réseau. Les deux tests
sur données complètes sont marqués `real` et passent par `make verify-real`.
Les connexions réseau sont bloquées dans le processus pytest et, par un
module chargé au démarrage, dans les commandes Python qu'il lance.

Le vérificateur échoue lorsqu'un rapport de couverture manque, lorsqu'aucun
test n'a été exécuté ou lorsque les résultats de mutation sont incohérents.
Le test de filiation compare les fichiers archivés au manifeste et vérifie que
les enregistrements d'expérience correspondent au code scientifique courant.
Les essais de mutation ont conduit à renforcer les tests sur la dimension des
vecteurs, les longueurs incompatibles et l'absence de prédictions positives.
Un essai local de croissance sur 100, 300 et 900 lignes est décrit dans
`scaling.md`. Les tests contrôlent les étapes chronométrées et la taille des
entrées, sans seuil fixe sur la durée.

Des tests de panne d'écriture et de sorties incomplètes existent
(`tests/test_atomic_outputs.py`, `tests/test_robustness.py`, voir `outputs.md`) ;
des schémas extrêmes supplémentaires et le redémarrage d'une expérience
interrompue restent à faire. Le pipeline s'exécute séquentiellement ; il n'a ni
API, ni interface interactive, ni état partagé entre processus. Le typage est
contrôlé par `make verify-types` (mypy 2.4.0 et pandas-stubs épinglés dans
`release_policy.json`) : `verification/` sans erreur, le code scientifique sans
nouvelle erreur, 17 erreurs connues listées dans `typing_baseline.txt`. Les
seuils numériques des durées ne sont pas utilisés comme critères de
correction.

## Données, résultats et CI

Le contrôle local retrouve 283 726 lignes et 473 fraudes après déduplication
pour Credit Card Fraud, 3 276 lignes et 1 998 positives pour Water Quality,
1 822 lignes et 175 anomalies pour Cardio. Les sommes de contrôle et les
commandes de rejeu sont conservées dans `verification/evidence/manifest.json`.
Les CSV bruts ne sont pas archivés ici. Le CSV Water Quality correspond au
miroir annoncé, et la conversion du fichier ADBench reproduit le CSV Cardio.
`make verify-real` compare maintenant les copies locales aux valeurs attendues
du manifeste. Le fichier Credit Card a la taille de la version 3 de la fiche Kaggle
(mars 2018) ; son hash n'a pas pu être comparé à un nouveau téléchargement.
Cardio vient de l'UCI sous licence CC BY 4.0 (`data/README.md`).

## Exécutions en CI

Lues dans les artefacts et les journaux des exécutions, copiées sous
`evidence/ci/39041531141/` (enveloppes, liste des mutants, rapport de
certification, rapport de reproduction, `INDEX.json` avec les empreintes).
Aucune de ces exécutions n'est une attestation indépendante.

Run `ci` 39041531123 sur le commit `a8644e7` (PR n° 37) : `test` et `faults`
réussis (ruff, FAST, typage, couverture du code de vérification, défauts).

Run `verify-release` 39041531141, même commit (exécuteurs `ubuntu-latest`,
Python 3.11.17, commit de fusion `79ac4508` dont l'arbre est celui de
`a8644e7`) :

| Travail | Résultat | Détail |
| --- | --- | --- |
| `release-fast` | succès | 1 030 tests, 1 576/1 576 lignes, 332/332 branches |
| `release-static` | succès | code de vérification 1 566/1 566 lignes et 576/576 branches ; typage : 17 erreurs connues, aucune nouvelle (mypy 2.4.0, pandas-stubs 3.0.5.260914) |
| `release-faults` | succès | 23/23 défauts détectés |
| `release-deep` | succès | 4 710 mutants éliminés sur 4 815 (97,82 %), 105 survivants, aucun expiré |
| `release-reproduce` | succès | cardio sur Linux : archive macOS retrouvée statistiquement (écart 6,5e-5), deux essais et environnement reconstruit depuis le verrou à empreintes : écart 0,0 (voir `reproducibility.md`) |
| `release-real` | ignoré | aucun exécuteur auto-hébergé autorisé |
| `release-gate` | échec voulu | verdict **INCOMPLETE**, seule raison : « real evidence is missing » ; environnement `exact-environment` |

Les 105 survivants de Linux sont les 108 survivants locaux moins les trois
mutants de casse (voir `mutation_notes.md`). Chaque tentative précédente a
révélé un défaut corrigé avant celle-ci (`remediation.md`) : contexte
d'exécution omis par le constructeur FAST, comparaison des partitions par octets
compressés, couverture du module de typage dépendant du paquet installé.
Les règles de protection de `main` ne sont pas appliquées (voir
`branch_protection_proposal.md`).

## Travail restant

- Preuve REAL à distance : il faut un exécuteur auto-hébergé autorisé par le
  propriétaire (`real_evidence.md`).
- Rejeu indépendant sur d'autres jeux et dans l'environnement Linux verrouillé
  (`reproducibility.md`) ; seul cardio a été rejoué dans un environnement
  reconstruit.
- Revue des 108 survivants si un module change ; évaluation temporelle sur
  données réelles, détecteurs profonds, étude de coût plus large dans un
  environnement contrôlé.
- Protection de `main` en attente du propriétaire.

Le tableau de suivi `verification/issues.md` et `remediation.md` relient ces
travaux aux tickets. Aucun résultat de ce rapport ne valide une livraison
finale du mémoire.

## Reproduire les vérifications

```bash
conda env update -f environment.yml --prune
conda activate etl-benchmark
make verify-fast
python -m pip install -e '.[deep]'
make verify-deep
make verify-real
python experiments/run_synthetic_benchmark.py --seeds 42 1 2 3 4
python experiments/run_severity.py
python experiments/run_curves.py --seed 42
python experiments/run_benchmark.py --dataset credit_card
python experiments/run_benchmark.py --dataset water_quality
python experiments/run_benchmark.py --dataset cardio
make verify-scale
latexmk -pdf -interaction=nonstopmode -halt-on-error -output-directory=paper paper/main.tex
```

## Ajouts de la mission de renforcement (octobre 2026)

| Élément | Où |
| --- | --- |
| REAL échoue si les trois jeux requis ne passent pas tous | `experiments/verify_real.py` |
| La barrière de mutation refuse comptes invalides, campagne interrompue, mutants sans test ou ignorés | `experiments/check_mutation.py` |
| Enveloppe de preuve validée (FAST, DEEP, FAULTS, REAL, tools, types, reproduction) | `verification/evidence_schema.py` |
| Certification de version (`make verify-release`) selon une politique versionnée : CERTIFIED, INCOMPLETE ou REJECTED, rapport « local, non attesté » | `verification/release.py`, `release_policy.json`, `certification.md` |
| Empreinte scientifique v2, empreinte de la méthode de mesure et filiation des archives historiques | `experiments/provenance.py`, `verification/lineage.py`, `evidence/lineage.json` |
| Périmètre de mutation contrôlé par un relevé indépendant | `mutation_scope.py`, `mutation_scope.json` |
| Verrous d'environnement macOS (conda) et Linux (pip avec empreintes) | `verification/environment/`, `lock_environment.py` |
| Reproductibilité par niveaux, sortie en échec si un niveau obligatoire n'est pas `PASS` | `reproduce.py`, `reproducibility.md` |
| Preuve REAL à distance : exécuteur auto-hébergé, archives à liste blanche | `bundles.py`, `real_evidence.md` |
| Sorties complètes et écrites sans état partiel | `outputs.md` |
| Références du manuscrit vérifiées sur sources primaires | `references.md` |
| Chiffres cités par le manuscrit liés à un run scellé | `claims.json`, `claims.py`, `evidence/runs/` |
| Protection de `main` proposée, vérifiée, non appliquée | `branch_protection_proposal.md`, `protection.py` |

Le statut général reste **INCOMPLETE à distance** : la preuve REAL n'existe que
localement. Les archives des expériences viennent d'un rejeu propre sur le
commit `93b6fe8` (voir « Rejeu du 16 octobre 2026 »), avec l'empreinte
scientifique v2 `44faa1f9`.
