# Generateur multi-schemas : protocole et hypotheses (issue #67)

Ce document est ecrit et archive avant tout resultat. Un resultat qui contredit une hypothese est
rapporte tel quel.

## Question

Le jeu synthetique est une seule table de clients (12 360 lignes). La matrice methode par type
(`heatmap_synthetic`) peut dependre de ce schema. Les memes six types injectes dans d'autres
domaines donnent-ils le meme profil par methode ?

## Schemas

Le schema client et ses resultats publies ne changent pas (`src/etl_benchmark/synthetic.py`). Deux
schemas sont ajoutes dans `research/multi_schema.py`, hors du registre et de l'empreinte
scientifique, generes avec Faker et NumPy :

- **transactions** : montant, nombre d'articles (fortement correles), remise, score de risque du
  commercant, anciennete du compte, solde apres operation, date de l'operation, reference
  (`TX-` suivi de huit chiffres), devise ;
- **capteurs** : temperature et humidite (correlees negativement), pression, vibration, tension de
  batterie, force du signal, horodatage de la lecture, version du micrologiciel (`vX.Y.Z`),
  site.

Chaque schema a des champs numeriques, une date, une chaine au format controlable, une categorie
a domaine fini, et l'identifiant de ligne sert de groupe d'identite pour le decoupage.

## Injection

Memes six types, memes taux (3 % par type), meme logique que le jeu client, parametrees par un
descripteur de schema : valeur manquante (une ou deux cellules parmi les colonnes annulables),
doublon (copie exacte d'une ligne propre, ajoutee), aberrante univariee (une colonne numerique
multipliee par un facteur tire dans [15, 45]), aberrante multivariee (la paire de colonnes
correlees recoit des valeurs d'un quantile extreme chacune, chacune plausible isolement), derive
temporelle (dates dans les 80 derniers jours et trois colonnes multipliees par 1,5 environ),
format invalide (chaine mal formee, categorie hors domaine, valeur numerique impossible).
Severite 1.

## Protocole

Decoupage 70/15/15 par identite stratifie sur le type, cinq graines (42, 1, 2, 3, 4), jeu regenere
par graine (12 000 lignes propres avant injection), detecteurs du registre aux reglages par defaut
(zscore, iqr, great_expectations, isolation_forest, lof, ocsvm), la regle de deduplication, et le
detecteur de derive configure sur la colonne de date du schema et ses colonnes numeriques, ajustes
sur l'entrainement avec contamination egale a la prevalence d'entrainement. Rappel et precision par
type, negatifs restreints aux lignes propres. La matrice du schema client est celle de l'archive
publiee (`synthetic_recall.csv`), non recalculee ; la ligne `drift` du schema client y est
configuree par defaut et n'est donc pas comparable.

## Hypotheses

- **H1 (rangees structurelles)** : sur chaque schema, great_expectations a un rappel moyen d'au
  moins 0,9 sur les valeurs manquantes et la regle de deduplication d'au moins 0,9 sur les doublons.
- **H2 (multivarie)** : sur chaque schema, le rappel moyen de isolation_forest et de ocsvm sur
  l'aberrante multivariee est d'au moins 0,5, et celui de zscore et iqr est inferieur a 0,2.
- **H3 (derive)** : sur chaque schema, aucune methode n'atteint 0,6 de rappel moyen sur la derive
  temporelle.
- **H4 (stabilite)** : la correlation de rang de Spearman entre les matrices methode par type de
  deux schemas quelconques (client, transactions, capteurs ; lignes communes, sans `drift`) est d'au
  moins 0,7, en moyenne sur les couples.

## Limites annoncees

Trois schemas generes par le meme auteur et la meme logique d'injection : l'accord entre eux montre
que le profil ne depend pas du schema de la table, pas qu'il tient sur des donnees reelles (voir le
benchmark type sur 42 tables). Les ecarts d'un schema a l'autre peuvent venir de details de
construction (echelles, correlations) autant que du domaine. Cinq graines : ecarts-types
indicatifs.
