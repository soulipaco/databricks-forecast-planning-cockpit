# Evidence, quality gates and release

## Evidence chain

Every public result must be traceable through:

`claim → chart/table cell → metric calculation → prediction rows → run manifest → code/config/protocol → source snapshot`.

The final handoff must say which checks ran locally and which ran in Databricks. A planned capability is not an implemented one; a successful fixture is not a real benchmark.

## Test requirements

| Area | Meaningful test |
|---|---|
| Pagination | Multiple pages and exact-page boundary; duplicate or missing pages fail reconciliation |
| Partition recovery | Retry a completed/partial month; output matches one clean run without double counts |
| Dates | Leap day, month boundary and source local-date preservation |
| Selection | Changing 2025 targets cannot change the frozen series manifest |
| Leakage | Sentinel future targets never enter adapters, tuning or scaling |
| Baseline | Lead 8–28 repeat last observed week, never evaluation actuals |
| Splits | All tuning forecasts precede final evaluation; expected 12 final origins and 28 dates |
| Metrics | Hand-calculated WAPE, bias sign, MASE seasonal scale and interval score; zero denominators return N/A |
| Forecast contract | Duplicate dates, missing leads, non-finite values and reversed bounds rejected |
| Failures | A failed candidate remains in expected denominator; no silent partial-population ranking |
| Vintage joins | Two runs/origins do not duplicate actuals in aggregate metrics |
| Idempotency | Replaying one logical cell produces no duplicate outputs; attempts remain auditable |
| Workspace integration | Actual v2 output names/date boundary; package fit; Delta writes; deployed dashboard |

Use small fixtures for edge cases. Keep network and cloud tests explicitly marked so ordinary CI is deterministic. Do not blanket mock every platform call and claim end-to-end verification.

## Release gates

### R0: data

- All core partitions reconciled; schema and timezone meaning recorded.
- Series manifest and deterministic alias map frozen from allowed development data.
- Current-snapshot and source aggregation limitations documented.
- Data attribution and intended redistribution reviewed against source terms.

### R1: methods

- Frozen cutoffs, features, tuning budget, postprocessing and metrics match the implementation.
- Primary comparison uses identical series, dates, horizon and history windows.
- No tuning on 2025 scores; parameter selection lineage is inspectable.
- Foundation-model pretraining overlap is marked unknown.
- Model inference actually used v2 and the intended Prophet adapter.

### R2: execution

- Every expected cell has success/failure status; all retry attempts retained.
- Paired evaluation coverage is displayed; incomplete comparisons are qualified.
- Runtime does not confuse cached retrieval with inference.
- Claims about money or engineering time have actual observations or are removed.

### R3: product

- Native dashboard inspected in the target workspace.
- Filters, denominator math and forecast-vintage joins verified.
- Capacity is explicitly illustrative; no unsupported staffing/savings statement.
- Interval totals are not misrepresented.
- Refresh reads stored results without refitting.

### R4: public release

- README tells readers the result, data, methods and limitations before a long architecture tour.
- Public evidence is accessible without credentials.
- Chart labels, numbers and captions agree with the same release run.
- No `[FILL]`, `<RUN_ID>`, synthetic values or draft status appears in publish-ready assets.
- No tokens, private workspace URLs, local personal paths or employer data leaked.
- Cross-link the existing Prophet repository and credit relevant source/software work.
- User has chosen publication; preparation does not automatically authorize posting or messages.

## Minimum release artifacts

| Artifact | Required content |
|---|---|
| `evidence/release_manifest.json` | Release ID, run IDs, source/config/code/protocol hashes, timestamp |
| `evidence/leaderboard.csv` | Paired measures, numerator/denominator fields, expected/observed counts |
| `evidence/series_scores.csv` | Per-series/per-origin results for independent inspection |
| `evidence/failures.csv` | Every failed cell and safe reason |
| `evidence/prediction_sample.csv` | Exact rows underlying the featured forecast plot |
| `evidence/runtime.csv` | Phase, model, batch, queue/compute/wall timing and repeat status |
| `evidence/engineering_log.csv` | Timestamp, task category, active minutes, reusable/new distinction |
| `evidence/claims.csv` | Claim ID, wording, evidence reference, reviewer and status |
| `evidence/validation_report.md` | Checks, commands, actual outcomes and blocked tests |
| `evidence/data_card.md` | Source, retrieval, aggregation, selection and limitations |
| `portfolio/` | Final charts, editable sources, captions, alt text and demo script |

Store full predictions and data externally/Delta if too large for Git; provide hashes and regeneration commands. A small derived aggregate dataset may be included when reuse terms permit. Make the distinction explicit.

## Claims ledger examples

| Claim | Evidence needed | Safe wording before evidence |
|---|---|---|
| Native SQL was within X% of Prophet | Paired primary metric calculation and population | “I am testing whether native SQL is competitive.” |
| Model B won on N series | Frozen win rule and full eligible-series table | No winner claim |
| SQL was faster | Comparable timing scope, repeats and queue/cache treatment | “Runtime is part of the evaluation.” |
| Less engineering work | Prospective task log and shared/model-specific boundary | “The project compares implementation responsibilities.” |
| Better staffing | Measured staffing assumptions and outcome evaluation | “Illustrative request-capacity planning.” |
| Production-ready | Appropriate operational evidence beyond this portfolio | “A reproducible portfolio reference.” |

## Visual reproducibility

Generate charts with code from the release tables. Never draw plausible benchmark bars or forecast curves manually. Save data files and chart scripts. Deterministically select featured series: median paired error difference, worst native-vs-Prophet difference, and a baseline-winning series if one exists. An editorial example can be added only if explicitly labelled and its selection rationale is stated.

Review exports at phone width and full resolution. Check clipping, legend, zero/axis decisions, readable units and source footer. Use matching populations when comparing bars. Do not use cropped axes to exaggerate small percentage-point changes.

## Independent review prompt

Ask a fresh reviewer or separate harness session to challenge the result using `12_HARNESS_PROMPTS.md`. It must inspect code and evidence, not only the README. Resolve substantive issues before launching. This is a methodological review, not proof of statistical certainty.

## Release sequencing

Freeze code and manifests → regenerate evidence → inspect dashboard and assets → validate claims → prepare tag/release text → owner publishes repository/release and posts. Keep a changelog for corrections. If a material issue emerges after launch, update the artifact and clearly correct the affected claim; do not silently rewrite the history of the experiment.
