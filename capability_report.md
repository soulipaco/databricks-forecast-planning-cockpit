# Capability report — 2026-09-29

## Local

- Working repository: `databricks-forecast-planning-cockpit`, newly initialized; source package is separate from the existing Prophet repository.
- Shell: PowerShell on Windows. Python installed: 3.11.9; `uv` 0.9.18 can resolve a Python 3.12 runtime. Git 2.47.1 and Databricks CLI 0.280.0 are installed.
- Project targets Python 3.12. Dependency resolution, tests and build are recorded in `PROJECT_STATE.md` after execution.

## Workspace

- The `nyc311` CLI profile authenticated to `<workspace-host>`. The existing serverless SQL warehouse `c3f37b7054223373` executed ordinary SQL successfully (`01f1bbf5-163e-1852-b191-b298959a9eb2`). The dedicated schema is `mlops_dev.nyc311_forecast`.
- All ten contract v1 Delta tables were created and listed in the catalog. Their query IDs are in `evidence/workspace_table_deploy_20260929.json`. A managed `artifacts` volume was created in the same schema.
- The development Silver JSONL was uploaded to the volume. A `read_files` query (`01f1bbf5-df47-1dd0-9f62-2513dd91bb0d`) parsed 30,681 rows, 5,088,270 requests and 40 zero-filled rows, equal to the local snapshot. A keyed Delta merge loaded `daily_requests`; both the first load and a repeat run had no missing, extra or changed rows. Query IDs and checks are in `evidence/workspace_silver_load_20260929.json` and `evidence/workspace_silver_reload_20260929.json`.
- The pinned `ai_forecast` v2 SQL was accepted for execution but failed during runtime environment setup. The first attempt (`01f1bbf4-5e41-113f-9e16-3e59df808595`) and retry (`01f1bbf5-0528-1ec3-9706-3dc43987d4d9`) reported `[ISOLATION_ENVIRONMENT_USER_ERROR.NO_MATCHING_DISTRIBUTION]` for `onnxruntime==1.20.1`; installation logs show repeated `pypi.org` connection timeouts. This does not establish whether the preview is available after the dependency issue is resolved. No v2 result exists.
- Bundle and AI/BI dashboard deployment rights remain unverified. No paid resource or schedule was created.
- Credential values are intentionally absent from this report and source configuration.

## NYC source probe

- A SODA2 January 2023 grouped extraction completed on 2026-09-29: 13,013 aggregate rows, three pages of 5,000 maximum, and 242,173 grouped requests equal to the independent source count. The payload SHA-256 is `16942f7ad373b2e744c2befc3e1784ce9a1512f3446d289e8f760689e52f7ace`.
- The source metadata labels `created_date` as `calendar_date`; the extractor preserves the source civil date. A sampled first-day check found 6,209 rows and 6,209 distinct `unique_key` values. This is diagnostic evidence, not a complete duplicate audit.
- SODA3 is implemented but unprobed because no application token was available. This one-month probe is not a complete 2021–2025 snapshot.
- After the probe, the same SODA2 adapter reconciled all 36 months of 2021–2023 and all 12 months of 2024. The versioned selection manifest contains 21 eligible series. Details and hashes are in `evidence/data_card.md`; 2025 remains unextracted.

## Next workspace action

Resolve or diagnose the workspace runtime's access to the pinned `ai_forecast` v2 dependency, then rerun `uv run nyc311 smoke --config conf/local.yaml`. The local `conf/local.yaml` is ignored by Git and contains no credentials. Keep the 2025 holdout untouched until the protocol is frozen.
