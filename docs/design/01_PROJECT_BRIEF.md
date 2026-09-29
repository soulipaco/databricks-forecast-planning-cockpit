# Project brief

## Intended decision

For a BI or analytics engineering team already using Databricks, when is the native SQL forecasting route accurate and reliable enough to justify replacing custom model fitting and tuning code?

The product helps an operational planner examine upcoming service-request demand, compare it with an explicitly assumed processing capacity, and see forecast reliability. It also helps an engineer inspect the accuracy, runtime and maintenance trade-offs behind the selected model.

**This is an independent public-data portfolio project, not work commissioned by NYC or a deployed NYC staffing system.** Service requests are not a count of every 311 call or contact. Count forecasts alone cannot infer staffing, handling time, service levels or actual labour savings.

## Hypotheses to test

1. Native SQL forecasting may achieve comparable error to a tuned Prophet pipeline for sufficiently dense daily workloads.
2. Winners may differ by series and forecast horizon.
3. The SQL route may reduce model-specific implementation work, while the shared data and operational work remains.
4. A simple weekly baseline may be difficult to beat on some series.

All four are hypotheses. The release remains valuable if native SQL loses or produces mixed results.

## Release scope

| Deliverable | What done means |
|---|---|
| Reproducible data snapshot | Versioned daily aggregates, source metadata, reconciliation and series manifest |
| Forecast adapters | Three candidates produce the same typed output contract |
| Evaluation | Frozen 2025 protocol, auditable scores, failures, intervals and runtime |
| Planning product | Native AI/BI dashboard reading materialized tables; labelled capacity illustration |
| Deployment as code | Bundle jobs, SQL, dashboard definition, configuration and supported permissions |
| External evidence | Public README, score tables, methodology, real charts and short demo |
| Communication campaign | Run outside this repository in the owner's publication workflow; this repository supplies the evidence, claims ledger and figures it cites |

## Scope cuts

Exclude weather, hourly queues, staffing optimisation, real-time streaming, retraining triggers, a model registry per series, custom web application, paid promotion, multi-cloud deployment and 84-day forecasts from the first release. Metric views are optional; ordinary governed SQL views are sufficient. Do not add Genie merely for a longer stack list.

Use five common problem families across five boroughs, subject to predeclared density checks. Agency is diagnostic metadata, not another grouping dimension. The final number of eligible series can be below 25; report the actual count and exclusions.

## Vertical slice before scale

Use three eligible series, one development cutoff and 28 days. Complete ingestion, naïve forecasts, the pinned Prophet adapter, native SQL execution, output validation, metrics and one dashboard chart. Only then expand extraction and tuning. This exposes access and adapter issues before the full experiment consumes quota.

## Milestones and estimated effort

| Milestone | Effort estimate | Exit artifact |
|---|---:|---|
| M0 Access and contracts | 2–3 h | Capability report and frozen interface v1 |
| M1 Real-data vertical slice | 6–9 h | Three models and score table for three series |
| M2 Benchmark hardening | 10–14 h | Snapshot, protocol lock, full evaluation and audit |
| M3 Dashboard and operations | 7–10 h | Deployed pages, retry checks and runbook |
| M4 Evidence and campaign | 10–14 h | Reproducible public release and launch package |

M3 scaffolding and M4 narrative/visual planning run alongside M1/M2. The totals overlap in calendar time but still consume effort. If time runs short, reduce optional pages and media formats before reducing benchmark validity.

## Success criteria

Technical success means the benchmark is fair and reproducible, every model attempt is accounted for, and the dashboard leads to a correctly qualified planning interpretation. It does not require a particular winner.

Portfolio success means an unfamiliar reader can understand the decision in 30 seconds, inspect the evidence in five minutes, and identify how to reproduce it.

## Principal risks and responses

| Risk | Response |
|---|---|
| v2 preview unavailable | Record smoke-test failure; finish other work; obtain access before a three-model release |
| Free Edition quotas | Batch by origin; checkpoint; cap concurrency; resume rather than rerun |
| API changes or mutable history | Inspect schema; freeze aggregates and hashes; report retrospective-snapshot limitation |
| Foundation-model prior exposure | Acknowledge unknown pretraining overlap with public data; avoid strict out-of-sample claims about pretraining |
| Existing Prophet assumptions differ | Audit weekday handling, targets, horizon and regressors before reuse |
| Attractive but invalid capacity result | Use requests/day as a declared assumption; no actual staffing or savings claims |
| Weak distribution | Make the result immediately visible, provide reusable evidence and target relevant communities |

## Open decisions with safe defaults

Use the existing allowed catalog and a dedicated project schema; currency costs stay unavailable unless actually measurable; public code can use MIT if the owner chooses and third-party terms allow, while data retains separate attribution. A local static evidence page is optional, not a blocking dependency. No calendar launch date is set until results pass review.
