# Dashboard scaffold

`planning_dashboard.skeleton.json` is a **parseable design/query manifest**, not a Databricks dashboard export. Its SQL names the required run and origin parameters explicitly; the serving views in `sql/views.sql` retain forecast vintage keys. The `SYNTHETIC DEMO` label applies whenever fixtures are shown. The planning page must display “Illustrative capacity, not NYC staffing data” beside its chart.

Do not pass this file to a bundle `dashboard.file_path` or describe it as deployed. First create and export a minimal dashboard in the target workspace, inspect the actual `.lvdash.json` schema, map these datasets and labels into it, validate the bundle against the installed CLI, deploy, then inspect filters and values in the workspace. A JSON parse alone verifies only syntax.

Before production use, materialize and test the paired leaderboard calculation from `v_model_leaderboard_cells`, including the complete expected grid, 95% coverage gate and numerator/denominator preservation. Check one displayed metric against release score rows. The current manifest has no configured visualization widgets, SQL warehouse binding, or dashboard resource definition.
