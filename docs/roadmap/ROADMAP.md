# ETL Anomaly Benchmark: platform roadmap

GitHub issues are the authoritative backlog. This page is the readable index: it does not hold tasks of its own. Tracker: [#191](https://github.com/theobigand/etl-anomaly-benchmark/issues/191).

## Identity

The project is the **ETL Anomaly Benchmark**. "Thesis 01" to "Thesis 08" are historical milestone names of the remediation backlog ([T001-T415](../thesis-remediation/README.md)), not the name of the project. They are kept for traceability and are not renamed.

## Objectives

1. **Academic (mandatory):** a rigorous thesis on anomaly detection in ETL pipelines, using all 235 acquired provenance groups where scientifically meaningful.
2. **Engineering (extension):** a reproducible, local-first ETL/ELT, MLOps and observability platform.
3. **AIOps (separate exploratory extension):** operational telemetry as a data asset, with its own protocol.
4. **Portfolio (extension):** analytics, documentation and demonstrations built from real outputs.

Extensions never delay thesis completion. Technologies are adopted only for functionality they provide; each adoption is recorded in an architecture decision ([#141](https://github.com/theobigand/etl-anomaly-benchmark/issues/141)).

## Milestones

Existing milestones are preserved. Platform phases reuse the proposed numbering with a distinct prefix so they do not collide with the historical `Thesis NN` meanings. No dates are assigned.

| Platform phase | GitHub milestone | Notes |
| --- | --- | --- |
| 01 Research Foundation | Thesis 01 | Historical, unchanged |
| 02 Dataset Coverage and Experimental Engine | Platform 02 — Dataset Coverage and Experimental Engine | New |
| 03 Industrial ETL and ELT Integration | Platform 03 — Industrial ETL and ELT Integration | New |
| 04 Scientific Experiments and Statistical Analysis | Thesis 02, 03, 04, 05 | Existing milestones, unchanged |
| 05 MLOps, Logging and Data Observability | Platform 05 — MLOps, Professional Logging and Data Observability | New |
| 06 Intelligent Observability and AIOps | Platform 06 — Intelligent Observability and AIOps | New |
| 07 Analytics and Portfolio Experience | Platform 07 — Analytics and Portfolio Experience | New |
| 08 Thesis Publication and Certified Release | Thesis 06, 07 (Thesis 08 stays optional extensions) | Existing, unchanged |

Phase numbers describe organization, not a strict schedule.

## Dependencies and critical paths

- **Academic critical path:** #133 utilization ledger, #134 compatibility model, #152 and #153 pilot design and authorization package, then existing #131 (T423-T430), #93-#99, #100, #101. Original-study pilots are never delayed by optional platform work.
- **Engineering critical path:** logging audit and configuration (#155, #156, #157), technology decisions (#141), runtime profiles (#142), then engines, orchestration, observability stack and the end-to-end demonstration (#167).
- **AIOps path:** telemetry contract (#169), catalog and ground truth (#175), separate protocol (#176), leakage framework (#177), baselines, then fusion and diagnosis. It never blocks the thesis.

## Authorization gates

The experiment freeze is active. Engineering work uses synthetic fixtures and metadata only. These need explicit owner authorization and are never self-approved:

- running either variance pilot, or any confirmatory or exploratory detector experiment on benchmark data;
- approval of new unit definitions (event, relational, nested) and protocol amendments (#154);
- the AIOps protocol and any scientific AIOps evaluation (#176);
- lifting the freeze, equivalent-mutant approval, release certification, merging PR #132.

## Mandatory versus optional

Mandatory: Platform 02 and the scientific issues, plus the existing Thesis 01-07 backlog. Optional extensions: Platform 03, 05, 06, 07 and the Thesis 08 agentic issues. Platform items labelled `scope:engineering` or `scope:portfolio` are not release blockers for the thesis.

## Backlog

### Platform 02 — Dataset Coverage and Experimental Engine

Complete utilization of the acquired benchmark: registry-driven execution, category-specific experimental units, compatibility and data integrity. Phase label of the ETL Anomaly Benchmark platform roadmap; not a schedule.

| Issue | Title | Scope | Authorization | Blocked by |
| --- | --- | --- | --- | --- |
| [#133](https://github.com/theobigand/etl-anomaly-benchmark/issues/133) | Utilization ledger: seven-stage status of every provenance group | thesis | none | - |
| [#134](https://github.com/theobigand/etl-anomaly-benchmark/issues/134) | Registry-driven execution and compatibility model by category and protocol | thesis | frozen | #133 |
| [#135](https://github.com/theobigand/etl-anomaly-benchmark/issues/135) | Typed-injection execution coverage for all unit-level-compatible groups | thesis | frozen | #133, #134 |
| [#136](https://github.com/theobigand/etl-anomaly-benchmark/issues/136) | Numeric and temporal batch execution coverage | thesis | frozen | #133, #134 |
| [#137](https://github.com/theobigand/etl-anomaly-benchmark/issues/137) | Event-log experimental units (C4, P-SEQ) | thesis | approval | #134 |
| [#138](https://github.com/theobigand/etl-anomaly-benchmark/issues/138) | Relational experimental units and referential faults (C5, P-REL) | thesis | approval | #134 |
| [#139](https://github.com/theobigand/etl-anomaly-benchmark/issues/139) | Nested-document experimental units (C6, P-NEST) | thesis | approval | #134 |
| [#140](https://github.com/theobigand/etl-anomaly-benchmark/issues/140) | Authoritative dataset utilization and exclusion report | thesis | approval | #133, #135, #136, #137, #138, #139 |

### Platform 03 — Industrial ETL and ELT Integration

Production-oriented ingestion, transformation, orchestration, storage, data modeling and controlled pipeline fault injection (engineering extension).

| Issue | Title | Scope | Authorization | Blocked by |
| --- | --- | --- | --- | --- |
| [#141](https://github.com/theobigand/etl-anomaly-benchmark/issues/141) | Architecture decisions, technology selection and dependency isolation | engineering | none | - |
| [#142](https://github.com/theobigand/etl-anomaly-benchmark/issues/142) | Local runtime: Docker Compose profiles, free container runtime, resource limits | engineering | none | #141 |
| [#143](https://github.com/theobigand/etl-anomaly-benchmark/issues/143) | DuckDB, Arrow and Parquet: local ELT and storage strategy | engineering | frozen | #141 |
| [#144](https://github.com/theobigand/etl-anomaly-benchmark/issues/144) | PySpark ETL backend (local mode) | engineering | frozen | #141, #143 |
| [#145](https://github.com/theobigand/etl-anomaly-benchmark/issues/145) | PostgreSQL relational store and integrity experiments | engineering | frozen | #141, #142, #138 |
| [#146](https://github.com/theobigand/etl-anomaly-benchmark/issues/146) | dbt Core with dbt-duckdb: staging, intermediate and mart models | engineering | frozen | #141, #143 |
| [#147](https://github.com/theobigand/etl-anomaly-benchmark/issues/147) | Great Expectations in pipelines and fair declarative-versus-learned comparison | engineering | frozen | #141 |
| [#148](https://github.com/theobigand/etl-anomaly-benchmark/issues/148) | Apache Airflow orchestration (lightweight local deployment) | engineering | frozen | #141, #142, #143 |
| [#149](https://github.com/theobigand/etl-anomaly-benchmark/issues/149) | Fault injection into actual pipeline stages | engineering | frozen | #143, #148, #159 |
| [#150](https://github.com/theobigand/etl-anomaly-benchmark/issues/150) | Cross-engine scientific comparability | engineering | frozen | #143, #144 |
| [#151](https://github.com/theobigand/etl-anomaly-benchmark/issues/151) | Backend performance and resource measurement | engineering | frozen | #143, #144 |

### Platform 05 — MLOps, Professional Logging and Data Observability

Experiment tracking, structured logging, centralized logs, tracing, metrics, alerting and data observability (engineering extension).

| Issue | Title | Scope | Authorization | Blocked by |
| --- | --- | --- | --- | --- |
| [#155](https://github.com/theobigand/etl-anomaly-benchmark/issues/155) | Audit existing logging, telemetry and error handling | engineering | none | - |
| [#156](https://github.com/theobigand/etl-anomaly-benchmark/issues/156) | Central logging configuration (stdlib logging + structlog) | engineering | none | #155 |
| [#157](https://github.com/theobigand/etl-anomaly-benchmark/issues/157) | Versioned event schema and correlation identifiers | engineering | none | #156 |
| [#158](https://github.com/theobigand/etl-anomaly-benchmark/issues/158) | Error handling, failure classification and bounded retries | engineering | none | #156, #157 |
| [#159](https://github.com/theobigand/etl-anomaly-benchmark/issues/159) | Sensitive-data redaction and ground-truth isolation | engineering | none | #156 |
| [#160](https://github.com/theobigand/etl-anomaly-benchmark/issues/160) | Log lifecycle: rotation, retention and flushing | engineering | none | #156 |
| [#161](https://github.com/theobigand/etl-anomaly-benchmark/issues/161) | OpenTelemetry instrumentation and resilient export | engineering | none | #157 |
| [#162](https://github.com/theobigand/etl-anomaly-benchmark/issues/162) | Local observability stack: Alloy, Loki, Tempo, Prometheus, Grafana | engineering | none | #141, #142, #161 |
| [#163](https://github.com/theobigand/etl-anomaly-benchmark/issues/163) | Grafana dashboards and operational alerts as code | engineering | none | #162 |
| [#164](https://github.com/theobigand/etl-anomaly-benchmark/issues/164) | Telemetry integration of Airflow, Spark, dbt, databases, Great Expectations and the experimental engine | engineering | none | #157, #162, #146, #148 |
| [#165](https://github.com/theobigand/etl-anomaly-benchmark/issues/165) | Data observability metrics | engineering | none | #161, #147 |
| [#166](https://github.com/theobigand/etl-anomaly-benchmark/issues/166) | Instrumentation overhead experiment | engineering | frozen | #162 |
| [#167](https://github.com/theobigand/etl-anomaly-benchmark/issues/167) | Runbooks and end-to-end observability demonstration | engineering | frozen | #163, #164, #149, #168 |
| [#168](https://github.com/theobigand/etl-anomaly-benchmark/issues/168) | MLflow tracking with scientific-record linkage | engineering | none | #141, #157 |

### Platform 06 — Intelligent Observability and AIOps

Operational telemetry as a data asset: log analytics, NLP, operational anomaly detection, multimodal learning, incident analysis and conditional failure prediction (separate exploratory research extension).

| Issue | Title | Scope | Authorization | Blocked by |
| --- | --- | --- | --- | --- |
| [#169](https://github.com/theobigand/etl-anomaly-benchmark/issues/169) | Telemetry data contracts, ingestion and archival | engineering | frozen | #157, #159, #162 |
| [#170](https://github.com/theobigand/etl-anomaly-benchmark/issues/170) | Operational data models and analytical grains | engineering | frozen | #169, #146 |
| [#171](https://github.com/theobigand/etl-anomaly-benchmark/issues/171) | Log parsing and template extraction (Drain3 evaluation) | engineering | frozen | #169 |
| [#172](https://github.com/theobigand/etl-anomaly-benchmark/issues/172) | NLP pathway for error and incident text | engineering | exploratory | #171 |
| [#173](https://github.com/theobigand/etl-anomaly-benchmark/issues/173) | Operational feature engineering with point-in-time correctness | engineering | frozen | #170, #157 |
| [#174](https://github.com/theobigand/etl-anomaly-benchmark/issues/174) | Telemetry alignment and multimodal datasets | engineering | frozen | #173 |
| [#175](https://github.com/theobigand/etl-anomaly-benchmark/issues/175) | Incident and fault-scenario catalog with protected ground truth | engineering | frozen | #149, #159 |
| [#176](https://github.com/theobigand/etl-anomaly-benchmark/issues/176) | Separate AIOps scientific protocol | engineering | approval | #175 |
| [#177](https://github.com/theobigand/etl-anomaly-benchmark/issues/177) | Leakage-prevention framework and audit | engineering | frozen | #173, #175 |
| [#178](https://github.com/theobigand/etl-anomaly-benchmark/issues/178) | Operational baselines: statistical and classical ML | engineering | exploratory | #177, #176 |
| [#179](https://github.com/theobigand/etl-anomaly-benchmark/issues/179) | Sequence-based and deep models (conditional) | engineering | exploratory | #178 |
| [#180](https://github.com/theobigand/etl-anomaly-benchmark/issues/180) | Multimodal fusion and data-only vs telemetry vs hybrid comparison | engineering | exploratory | #174, #178, #177 |
| [#181](https://github.com/theobigand/etl-anomaly-benchmark/issues/181) | Incident correlation, deduplication and alert prioritization | engineering | exploratory | #175, #178 |
| [#182](https://github.com/theobigand/etl-anomaly-benchmark/issues/182) | Probable root-cause identification and diagnostic evaluation | engineering | exploratory | #174, #175 |
| [#183](https://github.com/theobigand/etl-anomaly-benchmark/issues/183) | Failure prediction feasibility | engineering | exploratory | #177, #178 |
| [#184](https://github.com/theobigand/etl-anomaly-benchmark/issues/184) | AIOps tracking, replayed inference demo and model documentation | engineering | frozen | #168, #178 |

### Platform 07 — Analytics and Portfolio Experience

Analytical data products, interactive dashboard, architecture documentation, operational demonstrations and portfolio presentation (portfolio extension).

| Issue | Title | Scope | Authorization | Blocked by |
| --- | --- | --- | --- | --- |
| [#185](https://github.com/theobigand/etl-anomaly-benchmark/issues/185) | Analytical models and KPIs | portfolio | none | #146 |
| [#186](https://github.com/theobigand/etl-anomaly-benchmark/issues/186) | Interactive scientific and analytical dashboard | portfolio | none | #185 |
| [#187](https://github.com/theobigand/etl-anomaly-benchmark/issues/187) | CI and local verification for optional services | engineering | none | #142 |
| [#188](https://github.com/theobigand/etl-anomaly-benchmark/issues/188) | Architecture and technical documentation | portfolio | none | #141 |
| [#189](https://github.com/theobigand/etl-anomaly-benchmark/issues/189) | End-to-end demonstration scenarios and incident investigation case study | portfolio | frozen | #167, #180, #182 |
| [#190](https://github.com/theobigand/etl-anomaly-benchmark/issues/190) | Portfolio case study | portfolio | none | #189 |

### Scientific preparation inside the Thesis milestones

| Issue | Title | Scope | Authorization | Blocked by |
| --- | --- | --- | --- | --- |
| [#152](https://github.com/theobigand/etl-anomaly-benchmark/issues/152) | Unit-level variance pilot: reconcile the 16-group design with the 235-group corpus | thesis | approval | - |

| Issue | Title | Scope | Authorization | Blocked by |
| --- | --- | --- | --- | --- |
| [#153](https://github.com/theobigand/etl-anomaly-benchmark/issues/153) | Pilot statistical design: estimands, budgets, identifiability and conservative sample size | thesis | approval | #152 |
| [#154](https://github.com/theobigand/etl-anomaly-benchmark/issues/154) | Protocol amendments for new execution pathways and category-specific units | thesis | approval | #137, #138, #139 |

## Existing coverage of the strategic requirements

Reused rather than duplicated: statistics and inference #93, thresholds #94, fair comparisons #95, fault fidelity #96, ablations #97, temporal and cost #98, IMRaD #99, reproducibility and release #100, publication #101, quality gates #103, batch-level study with T423-T430 and the batch pilot T424 #131, typed injection on ineligible tables #77, chronological studies #78, isolated timings #81, governance G01-G05 #109-#112, #116.

## Completion criteria

An issue is closed only when all its acceptance criteria hold with recorded evidence. A pull request alone never closes an issue. Coverage, mutation scores and certification are bounded software evidence, not proof of scientific validity.
