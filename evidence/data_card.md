# Data card — selection snapshot

**Status:** Real 2021–2023 selection and 2024 development extracts verified locally on 2026-09-29. No 2025 evaluation data are represented here.

## Provenance

- Source: NYC Open Data 311 Service Requests, dataset `erm2-nwe9`, SODA2 grouped endpoint. Source metadata and its update timestamp are preserved in `data/snapshots/selection-2021-2023-20260929/source_schema.json`.
- Retrieval period: 2026-09-29; exact UTC start and per-month extraction times are in the source and partition manifests.
- Snapshot ID: `selection-2021-2023-20260929`. Snapshot manifest SHA-256: `f22810dccdb2d3d71771914d639c72589528fdb6169753f5720cbce38508fb1d`.
- Development source ID: `development-2024-20260929`, 12/12 months and 3,456,769 requests over 164,439 aggregate rows; manifest SHA-256 `8095d1f296d152835f6920ee718dc517a9f46649312f9ae6529cc2e6136ebda4`.
- Combined development Silver ID: `development-silver-20260929`; 30,681 unique series-days, 40 verified zero-filled days and no null targets. Its manifest SHA-256 is `cacc015d81e3fa1050683ae58c07fdc0e8484eb16b47bf08d5e5d7a3fefe8e39`, and the daily payload SHA-256 is `31c0f35672c43dac090063318eaec8e7741d9da85b27ba5b926fcc14f4097eef`.
- Query/filter, page size, page counts, payload hashes and independent source counts are in each month's partition manifest. Each month is a half-open calendar interval.
- Source attribution: NYC Open Data. Redistribution terms review remains open before a public repository release.

## Meaning and transformations

- Source date field: `created_date`, reported by metadata as `calendar_date`; preserve its civil calendar date without UTC shifting. No reconstruction of historical publication state is claimed.
- Target: count of service-request records grouped by date, borough and original `complaint_type`. It is not total call/contact volume. A sampled 2023-01-01 raw-key check found 6,209 records and 6,209 distinct `unique_key` values; this is not a full duplicate audit.
- Mapping: exact complaint type, version `exact-complaint-type-v1`, no aliases.
- Aggregate extraction: 36/36 monthly partitions reconciled; 480,313 aggregate rows sum to 9,615,565 source requests. Unknown borough groups stay in the source payload and are quarantined in selection. Zero filling applies only after a complete partition is verified.
- Selection: the fixed 2021–2023 thresholds in `02_DATA_SPEC.md` selected 21 borough × family series in five families. The full candidate list and reasons are in `data/series_manifest/selection-v1.json` (SHA-256 `6a859a26fa3092f357e2757f6978a76061cd887ae9d5468b3df8e368a75e57b0`).

## Completeness and limitations

- Expected, returned and reconciled partitions: 36/36 selection and 12/12 development. Each monthly source count equals its grouped sum; totals are 9,615,565 and 3,456,769 respectively.
- Borough exclusions: 6,962 requests have no borough and 18,469 say `UNSPECIFIED`. They remain in source counts and cannot enter canonical borough series. Candidate series below density thresholds remain documented in the selection manifest.
- The source is a current retrospective extract; later revisions may differ from values visible at a 2021–2023 forecast origin. No 2025 evaluation data influenced the selection.
- These counts support an application backtest after later stages. They do not by themselves justify staffing, service-level or savings claims.
- All 21 selected series passed 1,095-day bounded-history checks at the two development origins and 2024-12-31 (63 checks). No 2025 records were used.

## Reproduction

- Extractor: `src/nyc311_forecast/ingest/`, config `conf/selection.yaml`. Command: `uv run nyc311 ingest --start 2021-01-01 --end 2024-01-01 --snapshot-id selection-2021-2023-20260929 --page-size 5000`.
- Selection command: `uv run nyc311 select-series --config conf/selection.yaml --snapshot-dir data/snapshots/selection-2021-2023-20260929 --output data/series_manifest/selection-v1.json`.
- Development extract: `uv run nyc311 ingest --start 2024-01-01 --end 2025-01-01 --snapshot-id development-2024-20260929 --page-size 5000`.
- Silver materialization: `uv run nyc311 materialize-development --selection-snapshot data/snapshots/selection-2021-2023-20260929 --development-snapshot data/snapshots/development-2024-20260929 --series-manifest data/series_manifest/selection-v1.json --snapshot-id development-silver-20260929`.
- Local checks: partition reconciliation, payload hashes, idempotent selection manifest and unit tests. Workspace checks: 30,681 Silver rows, 5,088,270 requests and 40 zero-filled days loaded and verified in Delta; 48 reconciled source partition records and 1,245 candidate-series decisions (21 selected) loaded and verified with zero missing or extra rows. The metadata load was repeated idempotently. Query IDs and payload hashes are in `evidence/workspace_silver_load_20260929.json`, `evidence/workspace_metadata_load_20260929.json` and `evidence/workspace_metadata_reload_20260929.json`.

## 2025 evaluation extract (after protocol freeze)

- Retrieved only after the protocol freeze (`evidence/freeze_manifest.json`, tag `protocol-v1.0-frozen`). Command: `uv run nyc311 ingest --start 2025-01-01 --end 2026-01-01 --snapshot-id evaluation-2025-20260929` (default page size 1000; about 13 minutes).
- 12/12 monthly partitions reconciled: 3,655,041 source requests in 164,706 aggregate rows. The snapshot manifest SHA-256 is `f5899994…`.
- Final Silver `evaluation-silver-20260929` covers 2021-01-01 to 2025-12-31: 38,346 series-days (21 × 1,826) with 40 zero-filled days, none in 2025. Payload SHA-256 is `1c59885b…`. Its 30,681 rows for 2021–2024 are identical to the development Silver. `materialize_evaluation` refuses to run without the frozen manifest.
- Borough exclusions across 2021–2025: 6,962 missing and 23,714 `UNSPECIFIED`.
- Loaded into the trial workspace Delta table with zero missing, extra or changed rows (`evidence/trial/workspace_evaluation_silver_load_20260929.json`).
