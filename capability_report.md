# Capability report — 2026-09-29

## Local

- Working repository: `databricks-forecast-planning-cockpit`, newly initialized; source package is separate from the existing Prophet repository.
- Shell: PowerShell on Windows. Python installed: 3.11.9; `uv` 0.9.18 can resolve a Python 3.12 runtime. Git 2.47.1 and Databricks CLI 0.280.0 are installed.
- Project targets Python 3.12. Dependency resolution, tests and build are recorded in `PROJECT_STATE.md` after execution.

## Workspace

- Existing Databricks host appears in local CLI profiles. `databricks auth profiles` lists all saved profiles as `NO` for validity on this machine at this time. No authenticated workspace API call or SQL smoke test has succeeded.
- Workspace cloud/edition, permitted catalog/schema, warehouse ID, preview enrollment, table creation, bundle and dashboard rights, source egress and runtime versions remain unverified.
- Credential values are intentionally absent from this report and source configuration.

## NYC source probe

- A SODA2 January 2023 grouped extraction completed on 2026-09-29: 13,013 aggregate rows, three pages of 5,000 maximum, and 242,173 grouped requests equal to the independent source count. The payload SHA-256 is `16942f7ad373b2e744c2befc3e1784ce9a1512f3446d289e8f760689e52f7ace`.
- The source metadata labels `created_date` as `calendar_date`; the extractor preserves the source civil date. A sampled first-day check found 6,209 rows and 6,209 distinct `unique_key` values. This is diagnostic evidence, not a complete duplicate audit.
- SODA3 is implemented but unprobed because no application token was available. This one-month probe is not a complete 2021–2025 snapshot.

## Next workspace action

Authenticate the existing personal workspace with the supported Databricks CLI OAuth flow, then identify a permitted catalog/schema and SQL warehouse. The command and exact values can be added to a local, untracked configuration after authentication. Do not enable schedules or paid resources for this check.
