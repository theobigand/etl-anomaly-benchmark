# Suivi temporel

Le benchmark principal mélange les lignes pour conserver la proportion de
chaque classe. Ses mesures décrivent des anomalies **par ligne**. Elles ne
mesurent pas le délai de détection d'un changement de distribution.

Pour ce second problème, `chronological_split` ordonne les événements par
date. Une même date reste dans une seule partition ; la dernière date du
train précède la première de validation, et celle de validation précède le
test. Le suivi est ajusté uniquement sur le train. Ses paramètres de fenêtre
et de seuil doivent être choisis avant de consulter le test final.

`WindowDriftMonitor` garde cette référence fixe. Il rassemble les événements
futurs en fenêtres non chevauchantes d'au moins `window_size` lignes, sans
couper un groupe de dates identiques. Une fin incomplète n'est pas évaluée.
Le score est le plus grand déplacement absolu d'une moyenne de colonne,
exprimé en écarts types de la référence. Une colonne constante utilise une
échelle de 1 dans son unité d'origine. L'alerte vaut `score > threshold`.
Le contrôle refuse une date passée ou égale à la fin de la référence.

`event_metrics` calcule le délai entre un changement connu et la première
alerte à partir de ce changement. Le taux de fausses alertes utilise les
fenêtres terminées avant le changement comme dénominateur. Sans fenêtre
antérieure, ce taux est indéfini. Ces mesures portent sur des fenêtres : on
ne les ajoute pas aux rappels par ligne de la carte synthétique.

Les tests couvrent un état stable, un saut, une hausse graduelle, une colonne
constante, les dates dupliquées ou désordonnées, les dates invalides, une
fenêtre trop courte et le refus d'une référence qui regarderait le futur.
Le seuil fixe n'est pas calibré pour une saisonnalité ou une référence qui
change dans le temps. Ces scénarios demandent des expériences séparées avant
toute conclusion sur les fausses alertes en production.
