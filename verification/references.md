# Vérification des références externes

Contrôle du 17 octobre 2026 des douze entrées de `paper/references.bib` et de
chaque phrase de `paper/main.tex` qui s'y appuie. Source primaire = page de
l'éditeur, de l'archive ou du dépôt, ou texte intégral de l'article. Les
résultats expérimentaux de la thèse ne sont pas concernés.

| Clé | Source consultée | Ce qui a été vérifié | Écart et décision |
| --- | --- | --- | --- |
| `han2022adbench` | arXiv 2206.09426 (résumé) | Titre, auteurs, NeurIPS 2022 ; 30 algorithmes, 57 jeux de données, 98 436 expériences. | Aucun. Identifiant arXiv ajouté. Les énoncés sur les temps et les types d'anomalies viennent du texte de l'article (correction antérieure). |
| `zhao2019pyod` | JMLR 20(96):1-7 | Titre, auteurs, volume, pages. Le résumé parle d'« un large éventail » d'algorithmes sans les compter. | Le manuscrit dit « des dizaines de détecteurs », ce que la source ne chiffre pas : la phrase est reformulée sans nombre. Adresse ajoutée. |
| `goldstein2016comparative` | PLoS ONE 11(4):e0152173 | 19 algorithmes non supervisés, 10 jeux de données ; les méthodes locales donnent des faux positifs en présence d'anomalies globales ; le choix de l'algorithme dépend du type d'anomalie. | La citation était placée après « Great Expectations … ignore les valeurs aberrantes multivariées », que l'article ne traite pas. Elle est déplacée sur la phrase « différentes familles de détecteurs excellent sur différents types d'anomalies ». |
| `khatri2010data` | CACM 53(1):148-152 (DOI 10.1145/1629175.1629210) | Gouvernance des données : « données comme actif », cinq domaines de décision. L'article ne traite pas des pipelines ETL. | La phrase sur le rôle des pipelines ETL n'est plus attribuée à cet article ; il n'étaie que « les organisations gèrent de plus en plus les données comme un actif à gouverner ». DOI ajouté. |
| `dataqualitysurvey2024` | arXiv 2406.19614 | Auteurs réels : Zhou, Tu, Sha, Ding, Chen. L'étude présente Great Expectations, Deequ et Soda Core parmi 17 outils de qualité des données. | Auteurs corrigés (« Various Authors » supprimé). Elle devient la source des phrases sur Great Expectations, Deequ et Soda. |
| `pipelinetoolssurvey2024` | arXiv 2406.08335 | Auteurs réels : Mbata, Sripada, Zhong. Étude d'outils de pipelines (ingestion, orchestration, ML) ; texte intégral lu : aucune mention de Great Expectations, Deequ ni Soda. | Auteurs corrigés. Ne soutient plus les phrases sur les règles déclaratives ; citée seulement comme panorama des outils de pipelines. |
| `gopa2025aiaugmented` | IJCESEN 11(4):7920-7927, DOI 10.22399/ijcesen.4124 (texte intégral lu) | Article d'architecture ; le tableau 2 reprend des résultats agrégés « d'implémentations en entreprise [18][19] » (97 % de précision de détection, 2 % de faux positifs) ; pas de code. Le texte ne contient pas le chiffre de 12,9 M$. | Le chiffre de 12,9 M$ par an est retiré du manuscrit : il n'est pas dans l'article cité. Il est attribué à une enquête Gartner de 2020 auprès de 154 clients de fournisseurs (sources secondaires seulement, la page Gartner a répondu 403) ; il n'est donc pas réintroduit. Pages et DOI ajoutés. |
| `marupaka2024mlpredictive` | IJCTT 72(3):53-60, DOI 10.14445/22312803/IJCTT-V72I3P108 (page de l'éditeur) | Auteurs réels : Divya Marupaka et Sandeep Rangineni (le fichier disait Pavan et Srikanth). Le résumé annonce des gains de précision sans nommer de jeu de données ni de référence ; le texte intégral n'a pas été lu. | Auteurs, pages, DOI corrigés. Le manuscrit dit seulement que le résumé ne nomme ni jeu de données ni référence. |
| `sokkula2024implementing` | IJFMR 6(6), nov.-déc. 2024, DOI 10.36948/ijfmr.2024.v06i06.33504 (texte intégral lu) | Auteurs réels : Manohar Reddy Sokkula et Shiva Kumar Vuppala (le fichier disait Srinivasa Rao). AUC-ROC = 0,5094, rappel de la fraude 0,02, précision 0,97, F1 macro 0,35, exactitude 51 %. Isolation Forest avec contamination de 1 %, appris sur des données rééchantillonnées par SMOTE (562 964 normales, 5 666 anomalies détectées, soit 2 × 284 315). | La valeur 0,51 est exacte (arrondi de 0,5094). Le texte précise désormais le rééchantillonnage SMOTE et le rappel de 0,02 au lieu de « près du hasard » seul. |
| `mlgulbcredit` | Fiche Kaggle ULB | Existence et taille (voir `manuscript_check.md`) ; empreinte du fichier non recontrôlable sans compte. | Aucun. |
| `kadiwal2021water` | Fiche Kaggle | 3 276 échantillons, 9 variables ; comparés au fichier local (empreinte dans le manifeste). | Aucun. |
| `campos2000cardio` | UCI Cardiotocography, DOI 10.24432/C51S4N | Créateurs listés « D. Campos et J. Bernardes » ; 2 126 instances et 21 variables (le jeu ADBench utilisé en compte 1 831). | Aucun ; le manuscrit cite ADBench pour la version utilisée. |

## Limites

- Les textes intégraux de Marupaka et Rangineni et de Gartner n'ont pas été
  lus ; ce qui est écrit à leur sujet se limite à ce que les pages de
  l'éditeur montrent.
- La section « Related Work » reste une liste de sujets à rédiger ; ses
  citations ont été vérifiées comme les autres.
- Les chiffres propres à la thèse sont hors de ce contrôle.
