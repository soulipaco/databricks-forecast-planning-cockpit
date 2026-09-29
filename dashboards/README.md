# Dashboards

All dashboards are Databricks AI/BI (Lakeview) definitions kept in code. They read stored Delta tables only and never invoke a model.

| File | Purpose | Deployed by | Evidence |
|---|---|---|---|
| `final_benchmark.lvdash.json` | **Final 2025 results**: leaderboard, series WAPE, WAPE and bias by origin, a featured forecast against actuals, run health | `scripts/deploy_final_dashboard.py` | [`evidence/trial/workspace_final_dashboard_v2_20260929.json`](../evidence/trial/workspace_final_dashboard_v2_20260929.json) |
| `development_readiness.lvdash.json` | 2021–2024 data readiness and data quality | `scripts/deploy_readiness_dashboard.py` | [`evidence/workspace_dashboard_quality_20260929.json`](../evidence/workspace_dashboard_quality_20260929.json) |
| `development_diagnostics.template.lvdash.json` | 2024 two-model development diagnostics (before native v2 was available) | `scripts/deploy_development_diagnostics.py` | [`evidence/workspace_dashboard_paired_scores_20260929.json`](../evidence/workspace_dashboard_paired_scores_20260929.json) |

Each deploy script runs every dataset query first and checks row counts and headline values against the stored evidence. It then creates or updates an **unpublished draft**, reads the stored definition back and compares it with the repository file. The final dashboard's datasets are bound to run `final-three-model-a8c5bcf1ed7d`.
