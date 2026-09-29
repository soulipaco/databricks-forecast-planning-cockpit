# Source aggregates with missing group values

Date: 2026-09-29. Status: adopted for development extraction.

The first 2021-01 extraction attempt failed because the NYC grouped API omitted the `borough` property on some rows. A direct 5,000-row page probe showed examples such as `2021-01-01 / Dirty Conditions / count 2` with no borough key. Socrata's JSON representation omits the null group field.
The subsequently reconciled January 2021 payload contains 169 requests in groups with an omitted borough and none with an omitted complaint type.

The extractor now accepts missing `borough` or `complaint_type` as a distinct null aggregate key and includes its count in source reconciliation. The normalization layer quarantines those requests as `<MISSING_BOROUGH>` or `<MISSING_COMPLAINT_TYPE>`; they cannot enter a five-borough modelling series. The source payload is retained unchanged. Duplicate aggregate keys and dates outside the requested partition remain errors.

This amendment changes only validation and exclusion accounting. The five eligible borough definitions and the 2021–2023 selection window remain as specified. The failed first attempt produced no committed monthly partition. Tests cover the missing-key row and its quarantine.
