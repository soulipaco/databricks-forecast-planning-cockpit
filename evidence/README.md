# Evidence workspace

This directory is currently a **template area**. No benchmark result is recorded by the files added for P06. Do not interpret an empty CSV as a zero result or a passed gate.

For a release, trace each public claim through `claim → chart/table cell → metric calculation → prediction rows → run manifest → code/config/protocol → source snapshot`. The required artifacts and gates are defined in [08_EVIDENCE_RELEASE.md](../08_EVIDENCE_RELEASE.md). Only publish result assets after the release run and independent review have been completed.

## Claims ledger

`claims.csv` starts with headers only. Add one row for each discrete claim before using it in a README, chart, post or demo. Keep `status` as `draft` until the cited calculation has been reproduced and a reviewer has inspected the full population and limitations. Record the same claim ID in the asset source or caption. Unsupported claims stay out of public copy.

Fields: `claim_id`, `wording`, `claim_type`, `evidence_artifact`, `calculation_reference`, `release_id`, `run_id`, `population_and_denominator`, `limitations`, `reviewer`, `status`, `reviewed_at_utc`.

Examples of claims requiring evidence: relative WAPE differences, series wins, runtime comparisons, engineering effort, dashboard behavior and capacity effects. The [release guide](../08_EVIDENCE_RELEASE.md) gives safe pre-evidence wording.

## Data and validation records

`data_card.md` and `validation_report.md` have unfilled fields. Populate them from actual extraction and check logs. Mark checks `passed`, `failed` or `blocked` with exact evidence; never turn an unavailable workspace check into a pass. Keep private workspace URLs, tokens and account details out of these public files.
