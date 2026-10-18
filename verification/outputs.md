# Sorties d'expérience : complétude et atomicité

## Protocole

Chaque script d'expérience écrit ses sorties (tableaux, notes, archives de
partitions, figures) puis, en dernier, l'enregistrement `run_*.json`
(`provenance.write_record`). L'enregistrement est le marqueur de fin :

- il liste les sorties (`outputs`) et leur empreinte sha256 (`output_sha256`) ;
- il n'est pas écrit si une sortie listée manque ou est vide (le script échoue) ;
- il est écrit dans un fichier temporaire du même dossier, vidé sur disque puis
  substitué par `os.replace` : une interruption laisse l'enregistrement
  précédent intact et aucun fichier partiel.

`verification/archive_evidence.py` refuse tout ce qui n'est pas prouvé complet
(`IncompleteRun`) : aucun enregistrement dans le dossier de résultats,
enregistrement sans `output_sha256`, sortie dont l'empreinte diffère de
l'enregistrement (fichier tronqué ou modifié), fichier plus récent qu'aucun
enregistrement ne liste. Les copies vers `evidence/` passent par des fichiers
temporaires puis `os.replace` ; si une copie échoue, l'archive précédente reste
telle quelle. Le manifeste est remplacé de la même façon.

## Publication atomique des fichiers de résultats

Chaque fichier de résultat (tableaux CSV, notes Markdown, archives de
partitions, figures du manuscrit, jeux générés ou téléchargés, rapports JSON de
vérification) passe par `etl_benchmark.atomic.atomic_path` : l'écrivain remplit
un fichier caché voisin (`.<nom>.partial-<pid><extension>`, qui garde
l'extension pour que pandas et matplotlib en déduisent le format), puis le
fichier est refusé s'il est vide, vidé sur disque (`fsync`) et substitué par
`os.replace`. Une erreur ou une interruption (y compris `KeyboardInterrupt`)
supprime le fichier partiel et laisse intact ce que la destination contenait,
par exemple la figure du manuscrit qui a un nom fixe.

Garanties testées (`tests/test_atomic_publication.py`) :

- injection de panne (disque plein simulé au milieu de l'écriture) dans chaque
  point d'entrée : `run_benchmark` (CSV, note, partitions), `run_synthetic_benchmark`
  (CSV, figure), `run_severity` (CSV, figure), `run_curves` (figure),
  `generate_synthetic` (CSV) : aucun fichier tronqué, aucun fichier caché
  restant, aucun enregistrement `run_*.json`, figure précédente intacte ;
- refus d'un écrivain qui ne produit rien ou produit un fichier vide ;
- renommage refusé : l'ancien fichier subsiste ;
- un test d'arbre syntaxique interdit tout `to_csv`, `savefig`, `write_text` ou
  `write_bytes` direct dans `src/etl_benchmark/` et `experiments/*.py` hors du
  gestionnaire.

Limites : l'atomicité vaut fichier par fichier. Un plantage entre deux fichiers
d'un même essai laisse les premiers complets, sans enregistrement ; c'est
l'enregistrement, écrit en dernier, qui marque l'essai terminé, et l'outil
d'archivage refuse un essai sans enregistrement. Un arrêt brutal (`SIGKILL`) peut
laisser un fichier `.partial-*` : il n'est jamais pris pour un résultat et fait
refuser l'archivage tant qu'il traîne. Les fichiers de scaling et de couverture
écrits par `verification/` ne sont pas concernés (hors du code scientifique).

Ce changement modifie `src/` et `experiments/*.py`, donc l'empreinte scientifique
(`44faa1f9` vers la nouvelle valeur portée par `evidence/run_*.json`). Les
enregistrements antérieurs n'ont pas été réécrits ni réestampillés ; les
archives de `evidence/` ont été remplacées par un rejeu complet depuis un commit
propre (voir `report.md`, « Rejeu du 18 octobre 2026 »). Les anciens
enregistrements restent dans l'historique git.

`extract.read_csv` charge un CSV réduit à son en-tête comme un tableau vide ;
le rejet intervient plus loin dans le protocole (voir `tests/test_robustness.py`).
Ce comportement n'est pas modifié : il ne concerne pas la publication des
sorties.

## Enregistrements antérieurs

Les 9 enregistrements archivés dans `verification/evidence/` datent d'avant
`output_sha256`. Ils n'ont pas été réécrits. Le protocole s'applique aux
prochaines exécutions ; l'outil d'archivage refuse un enregistrement sans
empreintes de sorties.
