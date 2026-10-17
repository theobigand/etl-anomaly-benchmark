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

## Ce qui n'a pas été modifié

Les fichiers de sortie eux-mêmes (`to_csv`, `savefig`, `write_split_ids`) sont
écrits par du code compté dans l'empreinte scientifique (`src/` et
`experiments/*.py`). Les rendre atomiques sur place changerait l'empreinte de
toutes les exécutions archivées et obligerait à rejouer l'ensemble des
expériences sans changer un seul résultat. Les noms de sortie portent un
horodatage : un nouveau fichier n'en écrase pas un ancien, et la figure du
manuscrit, au nom fixe, est protégée par le protocole ci-dessus (une figure
tronquée est détectée par son empreinte). Si le propriétaire souhaite une
écriture atomique sur place, il faut le décider avec un rejeu complet planifié.

`extract.read_csv` charge un CSV réduit à son en-tête comme un tableau vide ;
le rejet intervient plus loin dans le protocole (voir `tests/test_robustness.py`).
Ce comportement n'est pas modifié pour la même raison (`src/` est compté dans
l'empreinte scientifique).

## Enregistrements antérieurs

Les 9 enregistrements archivés dans `verification/evidence/` datent d'avant
`output_sha256`. Ils n'ont pas été réécrits. Le protocole s'applique aux
prochaines exécutions ; l'outil d'archivage refuse un enregistrement sans
empreintes de sorties.
