# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-29

First public release: the frozen protocol v1.0 benchmark and its evidence.

### Added

- **2025 final benchmark:** weekly seasonal naïve, tuned Prophet and Databricks `ai_forecast` v2 on 21 NYC 311 series, 12 monthly origins and a 28-day horizon. 756 of 756 cells are complete, with no SQL results served from the cache (`evidence/leaderboard.csv`).
- **Protocol freeze gate** (`nyc311 freeze`): refuses to freeze until every three-model development prerequisite exists, then hash-locks the protocol, config, series, tuning and development run. Every final stage re-verifies these hashes.
- **Native v2 adapter and runner** with a transient-only retry policy, cache-defeating query tags and query-history verification.
- **Delta persistence** of the final run with exact readback, SQL recomputation of the headline, and a code-managed AI/BI results dashboard.
- **Databricks Asset Bundle** with unscheduled, single-run serverless jobs (Silver reproduction, freeze gate).
- **Release evidence:** leaderboard, series scores, failures, runtime, prediction sample, release manifest, claims ledger, independent arithmetic checks and a repeatability check.

### Changed

- The v2 horizon is requested as `origin + 28 days`, because v2 returns the horizon date despite the documented exclusive boundary (`docs/adr/native_v2_horizon.md`).

### Notes

- Evidence files record the release ID `nyc311-benchmark-v1.0-rc1`, which was published unchanged as tag `v1.0.0`.

- `ai_forecast` v2 could not run in Databricks Free Edition. It ran in a trial workspace; see `docs/adr/native_v2_runtime_blocker.md`.
- Git history was rewritten before publication to remove a private workspace host and private working files (`docs/history_rewrite.md`).
