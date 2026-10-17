# Proposition de protection de `main`

Statut : `AWAITING_OWNER_APPROVAL`. Rien de ceci n'est appliqué. État vérifié le
17 octobre 2026 par lecture : `main` n'est pas protégée (HTTP 404), aucun
ruleset (`[]`), un seul collaborateur (le propriétaire, administrateur), dépôt
privé, fusion par commit de fusion, squash et rebase autorisés. La PR #37 n'est
pas fusionnée.

## Contrôles obligatoires avant fusion

Les noms sont ceux des travaux de `.github/workflows/ci.yml`, tels que GitHub
les expose comme « checks ». Relevés sur la PR #37 au commit `292648a` (API
`commits/<sha>/check-runs`) : `test` et `faults` de `ci` en succès. Le travail
`faults` de `verify-release` portait le même nom ; les travaux de ce workflow
s'appellent maintenant `release-*` pour qu'un contexte requis désigne un seul
travail (`verification/protection.py` et son test contrôlent l'unicité) :

| Check requis | Ce qu'il garantit | Observé sur la PR #37 |
| --- | --- | --- |
| `test` | ruff, FAST (couverture ligne et branche à 100 %), couverture du code de vérification, typage | succès sous Linux |
| `faults` | les 23 défauts scientifiques sont détectés | succès sous Linux |

Pas requis à chaque PR : les travaux `release-*` de `verify-release` (DEEP dure
plus d'une heure). La certification d'une version reste séparée de la
possibilité de fusionner une PR : un verdict `INCOMPLETE` de `verify-release`
n'empêche pas une fusion, il empêche d'étiqueter une version.

## Réglages proposés

- Requérir une pull request, sans poussée directe sur `main`.
- Requérir `test` et `faults`, branche à jour avec `main` avant fusion.
- Relecture : 0 approbation tant que le propriétaire est le seul collaborateur
  (une approbation d'un autre compte ne peut pas exister) ; passer à 1 dès qu'un
  second relecteur existe, avec rejet des approbations périmées.
- Exiger la résolution des conversations.
- Interdire les poussées forcées et la suppression de `main`.
- Ne pas imposer l'historique linéaire (le dépôt fusionne par commit de fusion).
- Ne pas appliquer les règles aux administrateurs tant que les deux checks n'ont
  pas tourné sur plusieurs PR ; passer ensuite à « inclure les administrateurs ».

Charge utile pour `gh api -X PUT repos/theobigand/etl-anomaly-benchmark/branches/main/protection --input -` :

```json
{
  "required_status_checks": {"strict": true, "contexts": ["test", "faults"]},
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

## Vérification et retour arrière

- Avant : `python -m verification.protection print` affiche la charge utile ;
  les tests contrôlent qu'elle respecte le schéma de l'API (quatre clés
  obligatoires, `enforce_admins` booléen, contextes non vides) et qu'elle est
  identique au bloc ci-dessus.
- Après application par le propriétaire :
  `python -m verification.protection check` lit la protection (GET seulement)
  et signale tout écart avec la proposition.
- Retour arrière : `gh api -X DELETE repos/theobigand/etl-anomaly-benchmark/branches/main/protection`
  (la branche redevient non protégée, comme avant) ; vérifier ensuite par le
  GET, qui doit répondre 404. Si un contrôle requis bloque à tort une PR, on le
  retire de la liste plutôt que de supprimer toute la protection.
- Rien de ceci n'est exécuté sans l'autorisation explicite du propriétaire.

## Publication d'une version

1. Fusionner par PR, `test` et `faults` verts.
2. Lancer `verify-release` depuis `main` (`workflow_dispatch`). Sans exécuteur
   portant les trois CSV (`real_runner`), REAL est ignoré et le verdict est
   INCOMPLETE : c'est voulu, une version ne se certifie pas sans REAL.
3. Lancer `make verify-release` en local sur le même commit, avec les trois CSV :
   le résultat reste « local, non attesté ».
4. Étiqueter (`v*`) seulement un commit pour lequel les deux verdicts existent.
   Si un jour un ruleset d'étiquettes est voulu, restreindre `v*` au
   propriétaire.

Limites : les CSV de recherche ne sont pas dans le dépôt et ne doivent jamais
être envoyés ; aucun exécuteur auto-hébergé n'existe aujourd'hui.
