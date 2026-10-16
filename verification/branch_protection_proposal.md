# Proposition de protection de `main`

Proposition seulement : rien de ceci n'est appliqué. État vérifié le 16 octobre
2026 par lecture : `main` n'est pas protégée (HTTP 404), aucun ruleset, un seul
collaborateur (le propriétaire), dépôt privé, fusion par commit de fusion
(historique `Merge pull request #NN`).

## Contrôles obligatoires avant fusion

Les noms sont ceux des travaux de `.github/workflows/ci.yml`, tels que GitHub
les expose comme « checks » :

| Check requis | Ce qu'il garantit | Observé sur la PR #37 |
| --- | --- | --- |
| `test` | ruff, FAST (couverture ligne et branche à 100 %), couverture du code de vérification, typage | succès sous Linux |
| `faults` | les 23 défauts scientifiques sont détectés | succès sous Linux |

Pas requis à chaque PR : `verify-release` (DEEP dure plus d'une heure). Il
tourne sur une PR qui modifie son propre fichier et à la demande.

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
