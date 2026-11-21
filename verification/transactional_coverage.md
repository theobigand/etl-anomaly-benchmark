# Transactional coverage (C2b): sources, independence and fault applicability

Date 2026-11-21. Status: acquisition and readiness only; no detector experiment was run.

## Independence dimensions

| Dataset | Original producer | Publisher / curator | Data-generating system | Domain and mechanism | Schema family | Periods | Stage |
|---|---|---|---|---|---|---|---|
| Online Retail (UCI 352) | a UK online gift retailer | UCI repository | retail order system | retail purchase lines | invoice lines | 2010-12 to 2011-12 | acquired, no view yet |
| MHRA spending | MHRA (UK regulator) | data.gov.uk listing | MHRA ledger | public-sector payments over 25k pounds | GOV.UK spend template | 24 returns 2020-2024, not contiguous | experiment-ready |
| NHSBSA spending | NHSBSA (UK NHS body) | data.gov.uk listing | NHSBSA ledger | public-sector payments over 25k pounds | GOV.UK spend template | 24 monthly returns 2024-2026 | experiment-ready |
| Montréal contracts | Ville de Montréal | donnees.montreal.ca, OCP Data Registry (curator of the OCDS export) | municipal contract registry | municipal contract awards (award value, supplier, buyer) | OCDS compiled release | 2011-2025 | experiment-ready |
| Georgia, Netherlands, Zambia contracts | national procurement bodies | OCP Data Registry | national procurement systems | national contract awards | OCDS | various | acquired only: original terms unread |
| USAspending | US federal agencies via FPDS | US Treasury | FPDS reporting | federal contract actions (obligations, not payments) | FPDS award record | FY2024 | blocked: TLS chain does not verify with the Python trust store |
| NYC TLC | NYC TLC | NYC Open Data | taxi technology providers | trips with fares | TLC trip record | not collected | candidate: agency terms page refused automated access |
| Instacart 2017 | Instacart | Instacart | order platform | grocery orders | orders and products | 2017 | rejected: no licence is granted |

Counting rules used: months of one organisation count once. MHRA and NHSBSA are two original
producers with two ledgers, so they count as two groups; they share a publication template, which is
reported as shared structural dependence and not as shared observations. Different OCDS publications
come from different producers and systems, but they share the OCDS schema; the schema is a common
standard, not a common pipeline. Montréal also has a nested view (C6) that is the same family.

Redundancy and diminishing return: of the five sources above that are ready or near ready, three
domains are distinct (retail purchases, public payments, municipal contract awards). A further UK
ledger adds a producer but no new mechanism, schema or domain; additional ledgers are therefore not a
priority. The domains that would add a different mechanism are card or bank payments, utility or
telecom usage events, transport fares and inventory movements. For none of them was an open source with
a verified licence found in this pass.

## Spreadsheet support

NICE and Ofsted ledgers are spreadsheets or banner-layout files. The project has no spreadsheet
dependency (`pyproject.toml` lists pandas only), and the two sources would add two more ledgers of the
same template and domain. A spreadsheet reader would also add a dependency and a resource-limit
surface. Decision: not implemented now; the sources stay documented as deferred. The OCDS registry
also offers spreadsheets, but its JSON-lines export is sufficient.

## Fault applicability for transactional sources

I = controlled injection is valid and measurable, B = natural property to baseline (not a fault),
X = not applicable or not measurable with the information available.

| Mechanism | MHRA | NHSBSA | Montréal awards | Online Retail |
|---|---|---|---|---|
| Univariate amount anomaly | I | I | I | I |
| Context-dependent amount (supplier or expense type) | I | I | I (supplier, buyer) | I (customer) |
| Multivariate field combination | I | I | I | I |
| Missing transactions | X: publication threshold censors the source | X | X: the sample keeps whole contracts but is a hash sample | X (not a full ledger) |
| Duplicate transaction records | I | I, B (multi-line payments share a number) | I | I |
| Multi-line payment inconsistency | X | I on the multi-line payments only | X | I (invoice lines) |
| Invalid transaction identifiers | I | I | I | I |
| Inconsistent supplier relationships | I | I | I (links to parties) | I |
| Invalid quantity or price | X: no quantity column | X | X | I |
| Impossible temporal sequence | I | I | I | I |
| Volume change | I | I | I | I |
| Amount distribution shift | I | I | I | I |
| Currency or unit transformation | I (amount scale) | I | I (CAD amounts; a scale or currency error is a plausible fault) | I |
| Verified natural anomalies | none | none | none | none |

Source properties that are not faults: MHRA returns are not contiguous months, so a missing month is
not a missing transaction or a pipeline failure; both UK ledgers publish only payments over 25000
pounds, a censored view of expenditure; NHSBSA has multi-line payments (35 percent of rows share a
number); the Montréal rows are contract awards, not payments, and the registry compiles releases;
credit notes appear as negative amounts in the UK ledgers (1.7 and 2.2 percent).

## Open transactional gaps

C2b has four families (one without a view), three of them experiment-ready, against a target of 30.
The strongest candidates still to resolve: other OCDS publications once their original terms are
read (Georgia, Netherlands, Zambia are already acquired), USAspending (needs a trust-store decision),
NYC TLC (terms), and a payments or telecom source, which was not found.
