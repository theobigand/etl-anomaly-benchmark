# Proposition de protection de `main`

Statut : `AWAITING_OWNER_APPROVAL`. Rien de ceci n'est appliqué. État vérifié le
18 octobre 2026 par lecture : `main` n'est pas protégée (HTTP 404), aucun
ruleset (`[]`), un seul collaborateur (le propriétaire, administrateur), dépôt
**public**, fusion par commit de fusion, squash et rebase autorisés. La PR #37
n'est pas fusionnée.

Stratégie de fusion : **commit de fusion** (« Create a merge commit »). Le squash
et le rebase sont à éviter pour cette PR : ils réécrivent les SHA, et la
filiation vérifiée par `claims.py` (la révision d'un run scellé doit être un
ancêtre de `HEAD`) comme les ancres de `evidence/lineage.json` cesseraient d'être
des ancêtres de `main`.

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

## Application autorisée (à faire par le propriétaire)

```
python -m verification.protection print | gh api -X PUT \
  repos/theobigand/etl-anomaly-benchmark/branches/main/protection --input -
python -m verification.protection check
```

Les contextes `test` et `faults` sont ceux des seuls travaux de `ci.yml` ; ceux
de `verify-release` s'appellent `release-*`, donc chaque contexte requis désigne
un seul travail. Le `check` doit afficher « the applied protection matches the
proposal ».

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

1. Fusionner par PR (commit de fusion), `test` et `faults` verts.
2. Lancer `verify-release` depuis `main` (`gh workflow run verify-release.yml
   --ref main`, sans entrée). Le job hébergé `release-real-hosted` télécharge les
   trois jeux publics, vérifie leur sha256 contre le manifeste et exécute REAL ;
   le verdict attendu est CERTIFIED avec l'étiquette
   `ci-run:<id> (not independently attested)`. Un exécuteur privé n'est requis
   que si ce chemin devient indisponible (`real_evidence.md`, option B).
3. Lire le rapport et les artefacts du run (révision, empreintes), pas seulement
   la couleur du travail. Ne pas ajouter de commit sur `main` pour archiver le
   rapport : une preuve est liée à une révision. Les artefacts du run, ses liens
   et leurs condensés sont consignés dans l'issue 49.
4. Étiqueter (`v*`) seulement le commit certifié, avec l'autorisation du
   propriétaire. Si un ruleset d'étiquettes est voulu, restreindre `v*` au
   propriétaire.

Limites : l'exécution REAL hébergée repose sur des sources publiques dont le
sha256 est contrôlé avant usage ; elle n'est pas une attestation indépendante.
Les téléchargements suivent la liste d'hôtes de `real_acquire.py`, y compris à
chaque redirection (https et hôte listé, dix sauts au plus ; issue 50) ; en plus,
tout contenu différent est refusé par le contrôle du sha256 avant d'être écrit
(aucun secret n'existe dans ces jobs).
