# Transactional coverage (C2b): sources, independence and fault applicability

Date 2026-11-21. Status: acquisition and readiness only; no detector experiment was run.

## Independence dimensions

| Dataset | Original producer | Publisher / curator | Data-generating system | Domain and mechanism | Schema family | Periods | Stage |
|---|---|---|---|---|---|---|---|
| Online Retail (UCI 352) | a UK online gift retailer | UCI repository | retail order system | retail purchase lines | invoice lines | 2010-12 to 2011-12 | acquired, no view yet |
| MHRA spending | MHRA (UK regulator) | data.gov.uk listing | MHRA ledger | public-sector payments over 25k pounds | GOV.UK spend template | 24 returns 2020-2024, not contiguous | experiment-ready |
| NHSBSA spending | NHSBSA (UK NHS body) | data.gov.uk listing | NHSBSA ledger | public-sector payments over 25k pounds | GOV.UK spend template | 24 monthly returns 2024-2026 | experiment-ready |
| Montréal contracts | Ville de Montréal | donnees.montreal.ca, OCP Data Registry (curator of the OCDS export) | municipal contract registry | municipal contract awards (award value, supplier, buyer) | OCDS compiled release | 2011-2025 | experiment-ready |
| Georgia SPA contracts | State Procurement Agency of Georgia | OCP Data Registry (curator of the export) | Georgian e-GP | national contract awards and contracts (GEL) | OCDS compiled release | 2010-2019 | experiment-ready (CC0 verified at the publisher) |
| Zambia ZPPA contracts | Zambia Public Procurement Authority | OCP Data Registry | Zambian e-GP | national awards and contracts (ZMW) | OCDS compiled release | 2017-2026 | experiment-ready (ODC-PDDL verified at the publisher) |
| Netherlands (TenderNed) | Dutch Ministry of Economic Affairs and Climate Policy | TenderNed, OCP Data Registry | TenderNed | national tender notices and awards | OCDS | 2016-2026 | acquired, rights unclear |
| Capital Bikeshare, Citi Bike Jersey City | Lyft operator for member jurisdictions | the systems' own data pages | bike-share rental systems | rental events (no monetary amount) | Lyft trip schema | Sep-Nov 2024 | experiment-ready, research_only |
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


## Update: procurement and trips (2026-11-21)

Similarity of the four OCDS sources (Montréal, Georgia, Zambia, and the unaccepted Netherlands):

| Aspect | Montréal | Georgia | Zambia |
|---|---|---|---|
| Original producer and system | municipal contract registry | national e-GP, Georgia | national e-GP, Zambia |
| Currency | CAD | GEL | ZMW |
| Lifecycle present | award only | tender, award, contract | planning, tender, award, contract |
| Awards in the view | 30551 | 18299 | 2999 |
| Contracts linked by awardID | none | 18299, 0 orphans | 1368, 7 orphans |
| Nested depth, paths, optional | 6, 24, 1 | 7, 46, 17 | 7, 72, 57 |
| Period | 2011-2025 | 2010-2019 | 2017-2026 |

Independence of observations: three separate producers and systems in three jurisdictions; no shared
records. Similarity of structure: one publication standard (OCDS compiled releases), one domain (public
procurement awards), award values not payments. The three therefore add producer and currency
diversity and a different lifecycle completeness, but one mechanism and one domain. For the
statistics they are separate groups; for coverage of mechanisms they are one repeated process. Capital
Bikeshare and Citi Bike share one operator and one trip schema, so they form one family with two
systems and one group. The conservative grouping is applied in the readiness records.

Domains in C2b now: retail purchases (Online Retail, no view), public-sector payments (two UK ledgers),
public procurement awards and contracts (three OCDS producers), bike-share rental events. Distinct
mechanisms: purchase lines, payments, contract awards, rental events. Still missing: card and bank
payments, utility or telecom usage events, subscription events, inventory movements, fare payments.

Procurement semantics that the views keep: contract award, contract value and payment are different;
an amendment is not a duplicate; each compiled release is the latest state of one contracting process,
so one row per process (releases are not repeated states; this was checked: every acquired export has
one release per ocid); missing fields can be valid under a publisher's policy; OCDS extensions differ
by publisher (Georgia 46 paths, Zambia 72, Montréal 24).

Fault applicability additions (I = injection valid, B = baseline, X = not measurable):

| Mechanism | OCDS awards and contracts | Bike-share trips |
|---|---|---|
| Invalid reference between contract and award | I on Georgia and Zambia (native awardID); B for 7 Zambia orphans; X for Montréal (no contracts) | X |
| Invalid reference to a supplier or buyer | I (party ids resolve completely today) | X (no parties) |
| Corrupted award or contract value | I | X |
| Currency or unit inconsistency | I (a unit or scale error on a single-currency source) | I on duration units |
| Broken relation between procurement stages | I (award, contract) | X |
| Invalid event ordering | I (contract signed before award date) | I (end before start: B, 63 natural cases) |
| Repeated releases or duplicated contract records | I (one row per process: an injected repeat is a clear fault) | I (repeated ride id) |
| Missing required attribute | I; B for 151 Georgia awards without amount | I; B for 23 percent of CaBi trips without a start station |
| Schema transformation error | I (nested path rename or type change) | I |
| Distribution shift, abnormal value pattern | I | I |
| Natural labels | none | none |
