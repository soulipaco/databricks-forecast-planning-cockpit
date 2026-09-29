# `ai_forecast` v2 isolated runtime blocker

Observed 2026-09-29 in the existing Free Edition serverless SQL warehouse. No new forecast query was run during this diagnosis.

## Evidence

- The exact `version => '2'` synthetic smoke in `src/nyc311_forecast/platform/smoke.py` was attempted twice. Query IDs: `01f1bbf4-5e41-113f-9e16-3e59df808595` and `01f1bbf5-0528-1ec3-9706-3dc43987d4d9`. See `evidence/workspace_v2_smoke_20260929.json`.
- A read-only `get_statement` of the second query confirmed state `FAILED`, SQLSTATE `39000`, and `[ISOLATION_ENVIRONMENT_USER_ERROR.NO_MATCHING_DISTRIBUTION]`. The failed managed dependency was `onnxruntime==1.20.1`. Its installation log contains two `ConnectTimeoutError` messages for `https://pypi.org/simple/onnxruntime/`. The reported “no matching distribution” is downstream of those connection failures; this log alone does not establish a missing binary wheel.
- A read-only workspace Settings API metadata listing exposed `uc_udf_dependencies` and `ai_top_drivers`, both with effective value `true`. It did **not** expose a setting for “Enable networking for isolated workloads in Serverless SQL Warehouses.” The listing cannot establish whether that separate preview is unavailable, hidden from the current principal, or controlled outside the public Settings API.
- Ordinary SQL, tables, and views succeeded in the same warehouse, so the blocker is narrower than general warehouse access. There is no v2 forecast output, and preview eligibility after package installation remains unverified.

## Supported route to check

Databricks [documents `ai_forecast` v2](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_forecast) as requiring the Predictive AI Functions preview and a Pro or Serverless warehouse. Its [Unity Catalog Python UDF dependency documentation](https://docs.databricks.com/aws/en/udf/unity-catalog) says internet dependency installation on serverless SQL requires the separate **Enable networking for isolated workloads in Serverless SQL Warehouses** Public Preview. A workspace admin can inspect workspace **Previews** as [documented here](https://docs.databricks.com/aws/en/admin/workspace-settings/manage-previews). Enable that preview if offered and disabled, then allow its documented propagation time before one bounded rerun of the same pinned v2 smoke. This is a diagnosis and a possible supported remedy, not proof that `ai_forecast`'s managed dependencies use the same setting.

Databricks [Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations) explicitly restrict outbound internet access to trusted domains and say LinkedIn identity verification can unlock outbound internet access for eligible accounts. If the networking preview is absent or enabled yet PyPI still times out, the owner should inspect that account eligibility and the Free Edition egress limit. Neither changing the function version nor supplying a local wheel is an evidenced way to alter the managed `ai_forecast` runtime. Do not run the 2025 evaluation until a real v2 smoke returns 28 validated dates.

## Next bounded test

After a documented workspace setting or egress change, run **one** `uv run nyc311 smoke --config conf/local.yaml`; retain its query ID and 28-row validation result or new exact error. If there is no setting or entitlement path, record v2 as blocked in this workspace and keep the three-way benchmark unreleased.
