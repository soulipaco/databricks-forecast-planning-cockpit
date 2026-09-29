# `ai_forecast` v2 isolated runtime blocker

Observed 2026-09-29 in the existing Free Edition serverless SQL warehouse. No new forecast query was run during this diagnosis.

## Evidence

- The exact `version => '2'` synthetic smoke in `src/nyc311_forecast/platform/smoke.py` was attempted twice. Query IDs: `01f1bbf4-5e41-113f-9e16-3e59df808595` and `01f1bbf5-0528-1ec3-9706-3dc43987d4d9`. See `evidence/workspace_v2_smoke_20260929.json`.
- A read-only `get_statement` of the second query confirmed state `FAILED`, SQLSTATE `39000`, and `[ISOLATION_ENVIRONMENT_USER_ERROR.NO_MATCHING_DISTRIBUTION]`. The failed managed dependency was `onnxruntime==1.20.1`. Its installation log contains two `ConnectTimeoutError` messages for `https://pypi.org/simple/onnxruntime/`. The reported “no matching distribution” is downstream of those connection failures; this log alone does not establish a missing binary wheel.
- A read-only workspace Settings API metadata listing exposed `uc_udf_dependencies` and `ai_top_drivers`, both with effective value `true`. It did **not** expose a setting for “Enable networking for isolated workloads in Serverless SQL Warehouses.” The listing cannot establish whether that separate preview is unavailable, hidden from the current principal, or controlled outside the public Settings API.
- The owner manually checked **Settings → Previews** in this **Free Edition** workspace on 2026-09-29 and confirmed that “Enable networking for isolated workloads in Serverless SQL Warehouses” is not offered. Stop treating this preview as a pending admin toggle for this workspace.
- Ordinary SQL, tables, and views succeeded in the same warehouse, so the blocker is narrower than general warehouse access. There is no v2 forecast output, and preview eligibility after package installation remains unverified.

## Supported route to check

Databricks [documents `ai_forecast` v2](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_forecast) as requiring the Predictive AI Functions preview and a Pro or Serverless warehouse. Its [Unity Catalog Python UDF dependency documentation](https://docs.databricks.com/aws/en/udf/unity-catalog) says internet dependency installation for custom UDFs on serverless SQL requires the separate **Enable networking for isolated workloads in Serverless SQL Warehouses** Public Preview. That documentation is not proof that the managed `ai_forecast` dependency installation uses the same toggle. The owner confirmed the toggle is absent in this Free Edition workspace, so it is not an executable remediation here.

Databricks [Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations) explicitly restrict outbound internet access to trusted domains. The same page says eligible accounts may obtain outbound internet access after optional LinkedIn identity verification; this does **not** establish that the managed v2 package environment gains access. Free Edition also has no account console or private networking configuration. Neither changing the function version nor supplying a local wheel is an evidenced way to alter the managed `ai_forecast` runtime. Do not run the 2025 evaluation until a real v2 smoke returns 28 validated dates.

## Wheel workaround check

The owner asked whether `onnxruntime` could be uploaded as a wheel. [Unity Catalog UDF documentation](https://docs.databricks.com/aws/en/udf/unity-catalog) supports wheels in a volume when a **user-defined function** declares them in its `ENVIRONMENT dependencies`. The documented [`ai_forecast` v2 interface](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_forecast) has no dependency or wheel-path argument. Uploading a wheel would therefore make it available to functions we define, but provides no documented way to alter Databricks' managed `ai_forecast` environment. This is a limitation of the documented interface, not proof that Databricks has no internal remedy. We will not substitute a custom UDF or local model under the v2 name.

## Next bounded test

Treat native v2 as blocked in the current Free Edition workspace and keep the three-way benchmark unreleased. The owner need not install anything or keep searching for the absent preview. If an independently confirmed Free Edition entitlement/egress change later occurs, run **one** `uv run nyc311 smoke --config conf/local.yaml`; retain its query ID and 28-row validation result or new exact error. Optional LinkedIn identity verification is an owner choice, not a guaranteed fix or prerequisite to use the existing dashboard/data work.

## Independent re-check (2026-09-29, Claude Code session)

At the owner's request the blocker was re-verified from scratch rather than relying on the entries above. Details: `evidence/v2_independent_recheck_20260929.json`.

- A third warehouse smoke (`01f1bc22-fcda-1ec7-85de-f1cc214c89de`) failed identically. Its installation log shows pip connect timeouts to `pypi.org`, confirming a network cause.
- `ai_forecast` through serverless **job** compute (`spark.sql`) fails earlier with `UNSUPPORTED_FEATURE.AI_FUNCTION_PREVIEW`, so job environments, which can install PyPI packages, are not a route to v2.
- `version => '1'` succeeds on the same warehouse in 10 s with 28 rows. This is a feasibility fact for a possible protocol revision, not v2 evidence.
- Serverless job compute reaches arbitrary hosts (example.com, api.github.com, pypi.org), so the workspace already has the outbound access that LinkedIn verification grants; the owner sees no "Verify identity" button. That access does not extend to the SQL isolated environment. LinkedIn verification is therefore not a remaining remedy; the next route is a non-Free-Edition trial workspace.
