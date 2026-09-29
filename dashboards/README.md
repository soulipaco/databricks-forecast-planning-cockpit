# Dashboard assets

`planning_dashboard.skeleton.json` is a **parseable design/query manifest**, not a Databricks dashboard export. Its SQL names the required run and origin parameters explicitly; the serving views in `sql/views.sql` retain forecast vintage keys. The four views have been deployed and queried in the project schema, but contain no forecast results yet. The `SYNTHETIC DEMO` label applies whenever fixtures are shown. The planning page must display “Illustrative capacity, not NYC staffing data” beside its chart.

Do not pass `planning_dashboard.skeleton.json` to a bundle `dashboard.file_path` or describe it as deployed. It remains the proposed four-page planning product.

`development_readiness.lvdash.json` is a **separate, limited draft** that queries only the verified development Silver table. It shows selected-series counts and states that there is no three-model benchmark or 2025 evaluation. `scripts/deploy_readiness_dashboard.py` checked the dataset against 21 series, 5,088,270 requests and 40 zero-filled days, created one draft dashboard, retrieved it, and compared a workspace export with the tracked definition. IDs and hashes are in `evidence/workspace_dashboard_draft_20260929.json`; the exported file is `evidence/development_readiness_export_20260929.lvdash.json`. The draft is not published. The Databricks console blocked automated browser viewing, so visual rendering and interaction remain unverified.

After persisted model results exist, expand the planning definition with run/origin filters and evaluate every displayed value. Validate the bundle against the installed CLI and inspect the final dashboard interactively before release.

Before production use, materialize and test the paired leaderboard calculation from `v_model_leaderboard_cells`, including the complete expected grid, 95% coverage gate and numerator/denominator preservation. Check one displayed metric against release score rows. The current manifest has no configured visualization widgets, SQL warehouse binding, or dashboard resource definition.
