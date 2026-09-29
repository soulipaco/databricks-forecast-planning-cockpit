# Sources, decisions and verification boundary

Prepared 17 September 2026. Recheck product access and API behavior at implementation time. Sources support platform/data facts; experimental thresholds, schedules and success targets are project design choices.

## Verified primary sources

| Source | What it supports | Project consequence |
|---|---|---|
| [Databricks ai_forecast](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_forecast) | Versioned function, requirements, syntax and limitations | Use the explicit v2 smoke check and record actual capability |
| [Azure reference](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/functions/ai_forecast) | Corresponding Azure documentation | Follow the owner's actual workspace cloud, not a hard-coded assumption |
| [Free Edition limits](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations) | Serverless/quota/egress constraints | Bound jobs, checkpoint and support local extraction |
| [Bundle dashboard resource](https://docs.databricks.com/aws/en/dev-tools/bundles/resources#dashboard) | Dashboard resource and serialized-file support | Store definition and deployment configuration as code |
| [NYC dataset update](https://www.nyc.gov/opendata/news/all-news/311-Service-Requests-Updates) | Current/archive split and unchanged backend field names | Core 2021–2025; explicit optional archive |
| [Current NYC 311 data](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9) | Authoritative current dataset location | Source ID `erm2-nwe9` |
| [Historical NYC 311 data](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-2019/76ig-c548/about_data) | Archive dataset reached from official update | Source ID `76ig-c548`, stretch only |
| [Socrata queries](https://dev.socrata.com/docs/queries/) | Current query/auth/pagination guidance | Probe the supported endpoint and page explicitly |
| [Prophet diagnostics](https://facebook.github.io/prophet/docs/diagnostics.html) | Time-cutoff cross-validation and tuning concepts | Use the project's explicit non-random cutoffs |
| [Owner's Prophet repository](https://github.com/soulipaco/prophet-forecasting-mlops) | Existing implementation's stated structure and limitations | Inspect code and pin a commit before adapter work |

Official pages were inspected; external third-party claims are not needed for the core specification. This task did not independently establish current market novelty or prove that no comparable project exists. Do not describe it as “the first.”

## Direct probe completed during planning

A small real aggregate query against the current NYC endpoint returned HTTP 200 and rows with `request_date`, `borough`, `complaint_type` and `request_count`. The query grouped 2025-01-01 and requested two results. The response confirms basic endpoint/field compatibility from the planning environment. The probe did not access the owner's workspace or execute model inference.

## Decisions versus facts

| Choice | Status and rationale |
|---|---|
| Existing workspace, Free Edition first | Owner confirmed workspace availability; live feature checks remain |
| Separate companion repository | Preserves existing Prophet work and differentiates this product |
| 2021–2025 core | Design choice to limit extraction and avoid archive stitching in v1 |
| Daily borough × family | Design choice aligned with multi-series operational demand |
| Approximately 20–25 series | Target from selection rules; actual eligible count unknown |
| 1,095 training days and 28-day horizon | Fixed design choices for comparison and tractable execution |
| 2025 final evaluation | Historical evaluation, not prospectively collected outcomes |
| 20 Prophet trials per series | Bounded tuning budget; adequacy discussed as a limitation |
| 5% relative-error tolerance | Illustrative practical margin, not a business SLA |
| No weather in core | Feature parity and scope control |
| Aggregate-first ingestion | Avoid unnecessary raw volume and irrelevant sensitive fields |
| Static public evidence plus native dashboard | Removes audience login dependency without building another app |
| 35–50-hour effort allowance | Estimate including communication and audit, not measured effort |
| Launch targets | Stretch goals based on owner baseline, not predicted outcomes |

## Claims corrected from the initial discussion

- The interesting comparison is managed native inference versus a tuned forecasting pipeline; Prophet is not a foundation model.
- Existing BI products can offer forecasting. Do not launch with “BI tools cannot forecast.”
- A SQL function does not remove shared ingestion, validation, monitoring or reporting obligations.
- NYC service-request counts are not all 311 contacts and do not establish staffing requirements.
- An existing workspace makes deployment feasible; it does not itself prove that a specific preview is enabled.
- No model has won this benchmark yet.

## Checks deliberately left to implementation

Workspace preview availability; authentication and deploy permissions; source timestamp semantics from metadata; full-period counts and duplicate behavior; final eligible families; actual imports and assumptions of the pinned Prophet package; supported dashboard chart formats; execution duration, quotas and monetary usage visibility; current data redistribution terms; personal LinkedIn metric availability and comparable historical windows.

These checks have concrete backlog owners and do not require another broad discovery discussion before coding.

## Change record template

For every material decision amendment, create `docs/adr/YYYYMMDD-short-name.md` with context, previous rule, new rule, reason, data already inspected, affected experiment IDs and whether the final evaluation must be rerun. Changes prompted by final outcomes must be labelled exploratory rather than retrospectively preregistered.
