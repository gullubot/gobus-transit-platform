# GoBus Kolkata Master Research Package — reviewed working package

## What I did
I combined the available V1/V2/V3 master information supplied in this conversation with additional current public route research from Kolkata Bus-O-Pedia and official West Bengal Transport Department context.

The package intentionally does NOT pretend to contain the unseen 8,950 detailed records claimed in the earlier Markdown report. That report contained representative snippets rather than the underlying complete CSV rows. I only materialized records that are actually present in the reviewed content or current public route research.

## Current materialized coverage
- Route/service catalogue rows: 198
- Distinct stop names represented: 296
- SD5 hero stops: 40

## Use
- `master_kolkata_route_catalogue.csv`: broad route/service research catalogue.
- `master_kolkata_stops.csv`: stop-name pool; many coordinates still require enrichment.
- `sd5_demo_route.csv`: exact Product Owner stop sequence.
- `sd5_demo_service.csv`: SD5 operating specification.
- `sd5_fare_stage_map.csv`: Product Owner fare progression by stop stage.
- `MASTER_KOLKATA_RESEARCH_PACKAGE.json`: same research package in one machine-readable file.
- `PRE_INGESTION_REVIEW.md`: safety checklist.

## Important
This is a HUMAN-REVIEW research package, not an assertion that every route is fully operationally verified. Secondary details may be incomplete and should be admin-configured or enriched before activation.

The SD5 specification is user-provided and separate from the generic Kolkata research pool.

## Fare
Do NOT convert SD5 into per-km pricing. Use the stop-stage progression to derive distance-slab boundaries once authoritative stored route distance is available.

## Build 3
No code or Build 3 systems were changed.
