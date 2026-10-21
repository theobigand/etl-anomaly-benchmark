# Pool de jeux de donnees (issue #66)

Ce document decrit le pool de jeux de donnees reels du benchmark : d'ou ils viennent, a quelles
conditions ils sont utilises, comment ils sont normalises et comment on verifie qu'ils n'ont pas
change. Les donnees brutes ne sont jamais versees dans le depot (`data/adbench/` et `data/pool/`
sont ignores) ; seuls les empreintes, les licences et les rapports sont archives.

## Sources et droits

- **ADBench** (commit `3dac8221`, 47 jeux tabulaires) : 36 jeux retenus. 35 ont une licence
  CC BY 4.0 lue sur la page UCI d'origine, 1 (Credit Card) est sous ODbL/DbCL d'apres Kaggle.
  11 sont exclus parce qu'aucune licence ouverte n'est etablie ou que les conditions interdisent
  l'usage (celeba, backdoor, mammography, ALOI, donors, Pima, Stamps, WBC, speech, vowels,
  mnist). La raison et la source de chaque decision sont dans
  `evidence/dataset_registry/inventory.json` (champ `underlying_terms`).
- **UCI** (689 jeux au catalogue) : 133 passent les filtres de metadonnees (lignes 300 a
  1 000 000, 4 a 300 variables, ni image, ni texte, ni sequence, classification ou regression,
  telechargement direct) et de licence (CC BY 4.0 ou CC0, lue sur la page du jeu). 17 sont retires
  a la curation avec une raison (doublons de version, jeux synthetiques ou etiquetes par regles,
  jeux de plateau), ce qui laisse 116 jeux (`uci_curated.json`).

## Roles

- **porteur** (116 jeux UCI) : table de caracteristiques propre, support de l'injection typee
  d'anomalies (issue #65).
- **etiquete** (36 jeux ADBench et 64 jeux UCI, soit 100 problemes) : anomalies deja etiquetees.
  Pour UCI la regle est fixee avant tout detecteur : la classe la plus rare (au moins 20 lignes)
  est l'anomalie, les autres classes sont normales ; si cette classe depasse 10 % des lignes elle
  est reechantillonnee a 10 % avec la graine 0 et le taux naturel est consigne. Dix-neuf sources
  apparaissent dans les deux listes avec une derivation differente.

## Panneaux

Chaque panneau repond a une question precise (`uci_curated.json`, champ `panels`) : valeurs
manquantes (29), types mixtes (34), ordre temporel (12), tres petits jeux (22), tres gros (4),
tres larges (4).

## Normalisation (`research/normalise.py`)

Une seule politique, appliquee dans cet ordre a chaque jeu : colonnes constantes ou manquantes a
plus de 50 % retirees ; categories encodees en one-hot jusqu'a 20 modalites, sinon retirees ;
doublons exacts supprimes, ainsi que les lignes dont les doublons ont des etiquettes differentes ;
decoupage stratifie 70/15/15 selon la graine ; imputation par la mediane et standardisation
calculees sur l'entrainement seulement. LOF est saute au-dela de 50 000 lignes d'entrainement et
OC-SVM au-dela de 20 000 (seuils fixes d'apres l'etude de couts, saut toujours consigne). Chaque
decision est comptee dans le rapport du jeu (`adbench_normalisation_report.json`, `uci_pool.json`).

Deux defauts connus des fichiers UCI sont repares a la lecture : lignes d'en-tete repetees quand
plusieurs fichiers ont ete concatenes (Occupancy Detection) et jetons `indice:valeur` de type
libsvm (Gas Sensor Array Drift).

## Verification des telechargements

`research/pool_check.py --build` ecrit `pool_manifest.json` (url, SHA-256, licence de chaque jeu
inclus). `--verify` retelecharge chaque fichier en memoire, compare l'empreinte et ne conserve
rien ; il reessaie avec une pause en cas d'echec transitoire et sort avec un code non nul si une
empreinte differe. Le resultat est archive dans `pool_verification.json`. Un job d'integration
continue pour cette verification sera ajoute avec la prochaine fusion qui reinitialise de toute
facon l'execution locale scellee.
