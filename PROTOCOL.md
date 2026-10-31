# Fixed disaster snapshot-availability audit

## Decision, source-informed scope and original hold

Determine what a current county funding export supports before treating refresh metadata or filters on current records as a historical spending snapshot. Supply complete factual county summaries and a local comparison-readiness guard.

The original Study 12 stability-horizon analysis remains unexecuted. Its historical-snapshot gate remains unresolved. The original program protocol permits a data-availability study when historical snapshots cannot be established. This separate execution does not estimate a waiting period, revision error, recovery effect, funding need or benefit.

Official metadata and definitions were inspected before this plan: current v 2 funded-project scope, applicant-location county definition, daily reload metadata, first/last obligation and store refresh meanings, migration warning, financial units and terms. A real earlier metadata response was captured on 30 October 2026; a second was captured on 31 October 2026 UTC. These are metadata snapshots, not historical project-value snapshots. Selection is source informed, not blinded. No project-record financial outcomes have been requested.

## Fixed source cohort and capture

Use only the official PublicAssistanceFundedProjectsDetails v 2 endpoint. Retrieve every matching record for disasterNumber 4332 and 4339. The numbers are fixed before project capture; no replacements if a cohort is empty or unsuitable. Retain metadata count, all pages, exact URL/parameters, timestamps, native bytes/hashes and coverage diagnostics. Page size 10000, explicit order by gmProjectId, applicantId, pwNumber, metadata enabled and count requested. Duplicate/missing page coverage or changing source-count assertions fail the capture gate; at most one targeted repair of a demonstrated capture defect. Do not select a convenient subset after viewing money or retention results.

Requested fields are disasterNumber, declarationDate, gmProjectId, applicantId, pwNumber, county, countyCode, stateAbbreviation, stateNumberCode, federalShareObligated, firstObligationDate, lastRefresh. No individual-assistance records, names, contact blocks, project narratives, addresses, maps, applicant linkage or reidentification. Native project records remain private. Public sources are factual county/cutoff sufficient aggregates, capture metadata, exclusions and exact source hashes.

Read monetary tokens as exact decimals, retaining missing and invalid values. The studied amount is federalShareObligated in reported dollars, not paid cash, total project cost or an official financial-system measure. Do not add projectAmount, totalObligated or other overlapping measures. County means applicant location; no damaged-worksite or independently validated FIPS claim.

## Identity and eligibility before comparisons

Preserve all API records for row-count accounting. Prefer the documented GM project identifier within disaster when present and a strict nonnegative integer. Otherwise require the documented applicantId plus pwNumber within disaster. Missing or duplicated business keys are not silently deduplicated. Retain whole ambiguous key groups and exclusion reasons; exclude those groups from monetary totals. Row counts remain record counts; use project counts only if the source uniqueness checks support that description.

For money, require a singleton usable project key and a finite numeric source amount. Negative adjustments are retained with their sign. No missing amount becomes zero. Report eligible, missing/invalid and duplicate/unknown-key denominators for every disaster and county group. If supported totals cannot be formed, retain unavailable rather than zero. A current eligible-record sum is not a complete past-disaster funding total.

Group by disaster, stateNumberCode, countyCode when code is nonempty; retain all distinct source county names as labels and flag conflicting labels. For missing countyCode, use the exact trimmed county label (or MISSING) in a separate group. Do not force valid geography from a three-digit code or drop unspecified/tribal/territorial locations.

## Fixed availability comparisons

Use five authored UTC cutoffs:2018-12-31 T 23:59:59 Z, 2020-12-31 T 23:59:59 Z, 2022-12-31 T 23:59:59 Z, 2024-12-31 T 23:59:59 Z and 2026-10-30 T 23:59:59 Z. They are calendar probes, not tuned or actual dashboard deadlines.

For every disaster/county/cutoff, retain the full current record count and eligible current reported-dollar sum; count current records and sum eligible current amounts that satisfy each of:
1. current firstObligationDate <= cutoff;
2. current lastRefresh <= cutoff.
Keep missing/invalid dates as explicit unknowns. Report selected/current counts and amount shares with all denominators. A zero selected count is a property of the current-record filter, not evidence of zero historical obligations. Neither selector reconstructs prior record values, removed records, publication availability or the earlier population.

Compare the two actual metadata captures separately: endpoint/version, recordCount, modified, metadata lastRefresh, lastDataSetRefresh and source hash. Equal metadata or a completed reload does not establish unchanged county totals. Do not infer record changes from metadata lastRefresh or a stability horizon from two metadata observations.

All fixed cases and county groups remain in exports. No learned model, test of a national effect, fit, tuning, ranking, seed, calibration or optimized threshold.

## Implementation and independent verification

The local guard retains source version, financial field, county meaning, population specification, full-coverage status, capture timestamp and payload/aggregate hashes. A current descriptive result can be retained with those qualifications. A request for historical value comparison requires actual dated comparable county-value snapshots; metadata-only captures and current-record filters must fail closed. Different versions, county definitions, money fields or population specifications require explicit reconciliation and cannot produce a stability claim. Even two comparable dated values do not establish a waiting horizon without a prespecified repeated observation design.

Before comparisons, commit the complete source projection, county sufficient aggregates, identity/missingness exclusions and native coverage proof. Freeze source/method dependencies before the first comparison/summary command. Current source values are already visible during capture; workflow order is not blindness.

Independently reconcile native JSON fields and aggregate eligibility, keys, county assignments, dates and amounts. Reconstruct all counts/joins in SQLite and monetary sums/shares with exact Fraction or independent high-precision arithmetic, without production helpers. Authored fixtures cover metadata-vs-values, endpoint/version/population mismatch, UTC ambiguity, missing values, signed amounts, duplicate keys and empty denominators. Run two isolated saved-data Python replays; no claim that aggregate replay repeats private native source adjudication.

## Required release gates and stop rule

Require complete fixed case accounting, source rights/attribution, source/identity/amount/date correctness, independent recomputation, meaningful guard tests, two isolated replays, scoped privacy, original source-bound figures and a concise rendered independent manuscript, then exact candidate/main Linux CI, tested-tree identity, annotated tag and synchronized metadata. Grade 4 means these finite scoped gates pass; it does not establish a historical stability horizon, universal correctness, novelty, deployment or a policy benefit.

Native data and public aggregates are statistical research/reporting only, never individual-benefit eligibility or reidentification. Follow OpenFEMA terms and required disclaimer. Do not use FEMA/DHS seals. Formal-publication projects including Azure optimization remain private.

Preserve earlier failures and the original source-history hold. Keep at most 3 substantive review rounds, 45 active review minutes and 60 review-specific tool calls across original source discovery and this execution, excluding acquisition/coding/release execution. A persistent substantive failure after one targeted repair, unavailable required evidence or a cap leaves the affected gate incomplete; do not weaken it to count a release.
