# Pre-Ingestion Review

### Ready to carry forward
- broad route identities and variants
- current public-route research
- source/provenance references
- SD5 exact 40-stop specification

### Must be enriched/validated
- missing stop coordinates
- complete stop sequences for most routes
- route geometry
- cumulative distance_from_start
- exact schedules
- service-specific fares where unavailable
- fleet assignments

### Do not fabricate
- official schedules
- official fares
- vehicle registration numbers
- missing route identities
- road distances from straight-line coordinates

### Recommended import tiers
TIER 1: route/service + usable geometry/stops -> active
TIER 2: real route identity but incomplete metadata -> incomplete/inactive until configured
TIER 3: conflicts/uncertain/historical -> hold for review
