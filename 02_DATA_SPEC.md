# Data specification and ingestion

## Source and access

Use NYC Open Data `erm2-nwe9` for 2021–2025. The optional 2010–2019 source is `76ig-c548`. NYC's update explains the dataset split and that display-label changes leave API names unchanged. [NYC source update](https://www.nyc.gov/opendata/news/all-news/311-Service-Requests-Updates)

Relevant API fields to verify against live metadata: `created_date`, `borough`, `complaint_type`; use `agency` only for diagnostics and `unique_key` for sampled uniqueness checks. Do not ingest addresses, coordinates, descriptions or personal details for this benchmark.

The current query documentation describes SODA3 POST requests with an application token or authentication. Implement it as the preferred supported route after a probe; keep a tested SODA2 adapter where available. [Socrata query documentation](https://dev.socrata.com/docs/queries/)

Planning-session check: a SODA2 grouped request to `https://data.cityofnewyork.us/resource/erm2-nwe9.json` returned HTTP 200 on 17 September 2026. Two returned groups for 2025-01-01 were BRONX / Abandoned Vehicle / 12 and BRONX / Animal-Abuse / 1. This verifies the query shape only, not full dataset completeness, timezone interpretation or sustained access.

## Extraction design

Download daily aggregates, not all request rows. Retain the returned aggregate payloads as the Bronze source. Be explicit in the README that source-side aggregation reduces ingestion volume.

Illustrative SoQL selection, to validate before the full run:

```sql
SELECT date_trunc_ymd(created_date) AS request_date,
       borough, complaint_type, count(*) AS request_count
WHERE created_date >= '2021-01-01T00:00:00'
  AND created_date <  '2021-02-01T00:00:00'
GROUP BY request_date, borough, complaint_type
ORDER BY request_date, borough, complaint_type
```

For SODA2, send SELECT/WHERE/GROUP/ORDER in their separate query parameters. For SODA3, send the full query in the documented request body. Probe and record the endpoint version. Do not mix pagination formats between versions.

1. Save metadata/schema, retrieval timestamp and a schema hash before extraction.
2. Partition by calendar month, with half-open date ranges. Probe January 2023 first.
3. Set explicit page sizes, deterministic ordering and pagination; continue until exhaustion. A full page is never proof of completion.
4. Use bounded retry with jitter for transient failures and respect server retry guidance. Default maximum five attempts per partition and two in-flight requests; lower concurrency on throttling.
5. Reconcile the sum of grouped counts with a separate source count for identical filters. Check aggregate-key uniqueness across pages.
6. If reconciliation changes between reads, retry that partition and label it unstable if it still differs. Do not silently accept a partial extract.
7. Save partition hash, query/filter text, row count, total requests, page count, source metadata version if supplied, and completion status.
8. Promote a snapshot only after all partitions reconcile. Never append a partially re-extracted month to an already complete month.

A source aggregation cannot independently deduplicate raw requests. Compare `count(*)` with an appropriate unique-key check for sampled periods and inspect source definitions. If duplicates are found, resolve their meaning and change the aggregate strategy before proceeding. Do not present aggregate-key uniqueness as proof of raw-record uniqueness.

## Time semantics

The modelling grain is the calendar date represented by the source's request-creation field. Inspect its metadata: a floating local timestamp must not be interpreted as UTC and shifted into a different day. Confirm the intended NYC civil-date interpretation before freeze. Preserve a DATE for modelling. No hourly or daylight-saving interpolation is needed for a daily target. Record the verified interpretation, not an assumed conversion.

## Split extraction to avoid decision leakage

Extract/profile 2021–2023 first to select series. Retrieve 2024 for tuning/development. After the series manifest and benchmark protocol are frozen, retrieve/seal 2025 or keep an already retrieved 2025 partition inaccessible to tuning and profiling functions. Checks for extraction completeness on 2025 are allowed; choosing families or settings from its model performance is not.

## Series selection, frozen before results

Default `problem_family` is the normalized exact source `complaint_type` value. Avoid an LLM taxonomy. A versioned deterministic alias map may merge confirmed renames using only metadata and 2021–2023 inspection. Preserve both original and canonical values; require each original value to map to exactly one family.

Selection algorithm:

1. Keep the five canonical boroughs: BRONX, BROOKLYN, MANHATTAN, QUEENS, STATEN ISLAND. Quarantine unknown borough values with counts.
2. Over 2021–2023, rank families by total request count across those boroughs; break ties alphabetically.
3. Select the first five families that each have at least four borough-series meeting the rules below. This targets 20–25 series without promising a final count.
4. For each candidate borough/family: at least 90% of expected days have a positive count; median daily count at least 20; at least 730 days between first and last observed occurrence; no unresolved extraction gaps. These are project design thresholds, not facts about NYC.
5. Freeze `series_manifest` with rank, selection/exclusion reason, counts, mapping version and selection-data hash.

If fewer than three families qualify, stop series selection for a documented protocol revision based only on development data. Do not tune thresholds until a preferred model wins. Once frozen, no replacement of a series because it disappears or becomes difficult in 2025.

## Silver rules

- Grain: snapshot × series × request_date, unique.
- Target is a non-negative integer. Parse API numeric strings explicitly.
- Build a full daily spine for each selected series.
- A absent series/day aggregate may become zero only if the source partition is verified complete and the series is active under the frozen definition. Retain `is_zero_filled`.
- An unknown/incomplete day stays null with a data-quality reason; do not silently transform outages into zero demand.
- Never interpolate targets across the evaluation boundary. Unresolved training gaps block the affected attempt unless a predeclared train-only rule exists.
- Mapping edits create a new snapshot/config version. No silent historical rewrites.
- Inspect long zero runs, abrupt level shifts and rename boundaries. Report them without excluding hard cases post hoc.
- Reconcile source counts → normalized counts → selected-series counts, with explicit exclusions.

## Frozen and operational modes

The benchmark consumes an immutable snapshot ID. Today's source reflects later revisions: the evaluation is a retrospective backtest on a current snapshot, not a reconstruction of exactly what was published at every historical forecast origin.

Optional operational mode re-extracts a rolling 14-day window and checks older monthly partitions for revisions. Treat this window as an initial design setting, not a measured latency guarantee. Keep new snapshots separate. Forecast only through a configurable stable-date cutoff and show freshness. Never refresh benchmark truth in place.

## Data deliverables

`data_source_manifest.json`, `source_schema.json`, partition manifests, immutable aggregate files/Delta version, `problem_aliases.csv`, `series_manifest.csv`, reconciliation report, selected daily Parquet, and a data card with attribution and retrieval date. Keep complete payloads outside Git; publish small aggregate evidence only after checking source reuse terms. No assumption that the repository's code license covers source data.
