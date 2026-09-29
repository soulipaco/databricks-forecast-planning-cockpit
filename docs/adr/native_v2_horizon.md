# `ai_forecast` v2 horizon boundary

Observed 2026-09-29 in a non-Free-Edition trial workspace (serverless PRO warehouse).

The reference page describes `horizon` as right-exclusive. The same synthetic 2024 series returned:

| Horizon | Version | Rows | Last date | Query ID |
|---|---|---|---|---|
| `2025-01-29` | 1 (Free Edition) | 28 | 2025-01-28 | `01f1bc23-f43a-1595-9c07-b369ca050e9f` |
| `2025-01-29` | 2 | 29 | 2025-01-29 | `01f1bc2e-5b2d-1f19-97a5-ded33f80c0fa` |
| `2025-01-28` | 2 | 28 | 2025-01-28 | `01f1bc2e-6d67-19c6-bd51-d84859efde3b` |

The 28 shared v2 rows were identical across both horizons, so the extra row is appended rather than changing earlier leads.

Decision: v2 SQL requests `horizon = origin + 28 days`. `ForecastResult` still requires exactly leads 1–28, so if Databricks changes v2 to the documented exclusive boundary, the adapter fails visibly with 27 rows instead of silently shifting or truncating output. Do not drop surplus rows in the adapter.
