# Implementation exercise: check the evidence before comparing counties

The task is to retain a qualified current description while rejecting claims that exceed the captured evidence.

~~~powershell
python src/exercise.py
python -m unittest discover -s tests -v
~~~

The [input requests](data/exercise_inputs.json) and [evidence types](data/exercise_evidence.json) describe actual captured sources plus authored conversion requests. Their [complete outcomes](results/exercise.json) accept one current description and reject metadata-as-history, current-filter-as-history, applicant-county-as-worksite, grant-field-as-cash, missing evidence and an unestablished stability horizon.

Call `validate_comparison(request, evidence)` from [snapshot_guard.py](src/snapshot_guard.py) for integration. The guard checks source endpoint/version, financial field, county meaning, population specification, declared coverage, actual value hashes and aware capture times. A historical value comparison requires two actual comparable value captures. Two metadata records are insufficient.

The mapping is curated input. The guard does not prove source assertions, resolve geographic code/name conflicts, certify another producer's completeness or infer a waiting horizon. An accepted two-value comparison in an authored fixture is an interface test, not an observed historical FEMA comparison.

The current 38 fixtures include whole duplicate-project-group quarantine, missing monetary values, retained signed amounts, calendar-versus-UTC differences, an exact microsecond cutoff boundary, invalid hashes, missing/ambiguous evidence and zero denominators. Two aggregation-boundary methods were added after the initial fixed-probe checks; source/probe rules and frozen dependencies remain unchanged.

All use is statistical research/reporting. No individual-benefit decisions, individual linkage, production deployment or measured saving.
