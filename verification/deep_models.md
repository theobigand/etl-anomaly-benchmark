# Modèles appris et séquences

Ce protocole s'applique à l'autoencodeur actuel et à l'autoencodeur LSTM prévu.
Aucun résultat de ces modèles n'est dans les tableaux du manuscrit.

## Contrat commun

Tout détecteur du registre (`ALL_NAMES` et `DEEP_NAMES`) passe
`tests/test_registry_contract.py` : sortie alignée sur l'index d'entrée,
drapeaux booléens, scores flottants finis, deux ajustements identiques donnent
les mêmes scores, le score d'une ligne ne dépend pas des autres lignes du lot,
une valeur aberrante évidente score plus haut qu'une ligne typique, colonnes
constantes et valeurs manquantes donnent des scores finis. Les exceptions
(détecteur de dérive, qui lit une fenêtre) sont listées dans le test avec leur
raison et ne peuvent pas s'étendre sans modifier ce fichier.

## Autoencodeur

`AutoencoderDetector` entraîne un perceptron multicouche de `scikit-learn` à
reconstruire les variables standardisées à travers un goulot. Le score est
l'erreur quadratique moyenne de reconstruction. Imputation médiane, échelle et
seuil (quantile `1 - contamination` des scores d'entraînement) sont appris sur
les lignes d'ajustement seulement ; la contamination suit la même politique que
les détecteurs ML (prévalence du train ou valeur fixe). Il tourne sur CPU,
sans dépendance supplémentaire. `settings()` renvoie la graine, le budget
d'itérations, le nombre d'itérations réalisées, l'indicateur de convergence,
l'architecture et les versions des bibliothèques ; un résultat publié doit
enregistrer ces valeurs avec la provenance de l'essai. Un budget épuisé est
signalé par `converged = False` et non par un avertissement masqué.

## Règles d'arrêt et de réglage

Un arrêt anticipé, un taux d'apprentissage ou une architecture ne se décident
qu'avec le train et la validation. Ni les labels du test ni les scores publiés
sur le test n'entrent dans ces choix. L'arrêt anticipé intégré à
`scikit-learn` découpe lui-même une partie du train ; il est désactivé pour
l'instant (budget fixe). La partition de validation n'est utilisée par aucun
détecteur actuel.

## Séquences (LSTM)

`quality/windows.py` fixe les règles que le futur modèle séquentiel doit
reprendre. La fenêtre de l'événement `k` contient les lignes `k - taille + 1`
à `k` en ordre chronologique, complétées au début par la première ligne ; elle
ne contient jamais de ligne plus récente. Les fenêtres sont construites une
partition à la fois, donc une fenêtre de test ne contient aucune ligne du
train. Le score de la fenêtre revient à l'événement qui la ferme, et la série
renvoyée porte l'index d'origine quel que soit l'ordre d'entrée. Les
horodatages égaux gardent leur ordre d'entrée. Tests : `test_sequence_windows.py`.

## Avant d'inscrire un résultat dans un tableau

1. Le contrat commun du registre passe.
2. Mêmes partitions, même éligibilité des jeux et mêmes métriques que les
   autres méthodes (comparaison à protocole égal, pas à temps d'entraînement
   égal).
3. Les paramètres et la graine sont enregistrés avec l'essai.
4. Les essais longs ou avec entraînement conséquent sont lancés en DEEP ou
   REAL_ENVIRONMENT, pas en FAST, avec le matériel et la durée déclarés.
5. Les archives et le manuscrit sont régénérés ensemble.

## Limites

Le modèle LSTM n'est pas implémenté ; seuls ses contrôles d'entrée le sont. Un
modèle entraîné par descente de gradient sur GPU peut ne pas être
déterministe ; ses réglages de déterminisme devront être consignés avant tout
résultat. L'autoencodeur actuel n'est pas comparé aux autres détecteurs dans
une expérience.
