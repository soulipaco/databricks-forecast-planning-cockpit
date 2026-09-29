# NYC 311 January 2023 ingestion probe

`jan-2023-20260929/` is a **single-month, real-data probe**, not the 2021–2025 benchmark snapshot. It must not be used to claim model performance or a completed series selection.

- Source: [NYC Open Data, 311 Service Requests from 2020 to Present (`erm2-nwe9`)](https://data.cityofnewyork.us/resource/erm2-nwe9.json), attributed by source metadata to NYC 311.
- Retrieved: 2026-09-29 10:04:33 UTC through the SODA2 API. The exact source-side aggregate query, source metadata version, schema hash and page size are in the partition manifest.
- Transformation: source-side `date_trunc_ymd(created_date)` × `borough` × `complaint_type` grouped `count(*)`. No request-level rows, addresses, coordinates, descriptions or personal details are stored here.
- Check: 13,013 aggregate rows over three pages; grouped count 242,173 equals a separate source count for the same half-open January range. A separate 2023-01-01 diagnostic returned `count(*) = 6,209` and `count(distinct unique_key) = 6,209`; this is a sampled uniqueness check only.
- Integrity: `aggregates.json` SHA-256 is `16942f7ad373b2e744c2befc3e1784ce9a1512f3446d289e8f760689e52f7ace`. The snapshot and partition manifests hold the canonical payload and schema hashes.
- Reuse: NYC Open Data's [FAQ](https://www.nyc.gov/opendata/get-started/FAQs) states there are no restrictions on use of Open Data; its [terms](https://data.cityofnewyork.us/stories/s/Terms-of-Use/k9k7-3cje/) disclaim data completeness and accuracy. This repository identifies the source, version and modification. The dataset metadata did not declare a separate license.

The source is revised over time. Re-extracting January later should create a new snapshot ID, and differing counts need not imply that this archived probe was wrong at retrieval time.
