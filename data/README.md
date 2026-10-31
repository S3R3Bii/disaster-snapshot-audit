# Read the source groups before using the amounts

The public CSV contains county/date sufficient aggregates of the current capture, with no project or applicant identifiers. Native payloads and exact source hashes are retained separately. Source counts, identities, dates and exact amounts were independently reconstructed before cutoff comparisons.

In the result files, level **COUNTY** denotes a raw source county-code/name group as specified in PROTOCOL.md. It is not certification of a physical county or a county spending estimate. FEMA defines its county field as applicant location. Some source groups contain multiple labels, including Statewide and a named county. Those names are retained in county_catalog.json; their amounts must not be assigned to a physical county without separate geographic reconciliation. Code shape alone does not establish correct or incorrect geography.

The studied amount is **federalShareObligated**, reported dollars available to the grantee. It is not paid cash, total project cost, official federal financial reporting or a measure of recovery. All fixed rows remain in count accounting. Monetary eligibility follows the prespecified identity/finite-value rules; missing values are never filled with zero.

county_date_cells.csv retains the source first-obligation calendar day and normalized aware store-update timestamp. Aggregating these cells permits fixed current-record filters. The resulting selected/current fractions are fractions of the **current capture**, not historical totals, publication vintages or revision errors. A zero selected amount can be the known sum of an empty current-record slice; it does not establish zero past funding. Empty or zero monetary denominators produce unavailable fractions.

metadata_snapshots.json contains two actual metadata observations. It does not contain two county financial-value snapshots. Equal metadata fields and a completed dataset reload cannot establish unchanged county totals or a waiting horizon.

The local guard checks curated definition tags, evidence kind, coverage, hashes and time order. It does not independently certify geographic mappings, source assertions or the completeness of another producer's evidence. The inspected package has one current county-value capture and no established historical county-value series.

Source: OpenFEMA PublicAssistanceFundedProjectsDetails v2. Exact retrieval times, URLs and hashes are in capture_manifest.json; required terms and attribution are in DATA_RIGHTS.md.
