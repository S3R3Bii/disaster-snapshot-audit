"""Check frozen factual source accounting and lineage without redownloading records."""

from pathlib import Path
from collections import Counter
from fractions import Fraction
import csv, json, hashlib

ROOT = Path(__file__).resolve().parents[1]
read = lambda name: json.loads((ROOT / name).read_bytes())
n = 0


def require(ok, label):
    global n
    assert ok, label
    n += 1


cells = list(
    csv.DictReader(
        (ROOT / "data/county_date_cells.csv").open(encoding="utf-8", newline="")
    )
)
catalog = read("data/county_catalog.json")
keys = {r["county_key"] for r in catalog}
require(len(keys) == len(catalog) == 132, "unique county groups")
require(len(cells) == 9844, "complete sufficient cells")
require({int(c["disaster"]) for c in cells} == {4332, 4339}, "fixed source cohort")
counts = Counter()
for row in cells:
    require(row["county_key"] in keys, "county lineage")
    values = [
        int(row[k])
        for k in [
            "record_count",
            "eligible_money_records",
            "excluded_missing_key_records",
            "excluded_duplicate_key_records",
            "excluded_amount_records",
        ]
    ]
    require(values[0] == sum(values[1:]), "complete eligibility partition")
    require(all(v >= 0 for v in values), "nonnegative counts")
    require(
        (row["eligible_federal_usd"] != "") == bool(values[1]), "amount availability"
    )
    if row["eligible_federal_usd"]:
        Fraction(row["eligible_federal_usd"])
        n += 1
    counts[int(row["disaster"])] += values[0]
require(counts == Counter({4332: 6621, 4339: 11373}), "all declared native records")
native = read("data/native_verification.json")
require(
    native["status"] == "PASS" and native["finite_conditions"] == 141166,
    "retained independent native check",
)
for name, sha in native["source_sha256"].items():
    require(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha,
        "native-verified source bytes",
    )
contract = read("data/source_contract.json")
for name, row in read("data/exercise_evidence.json").items():
    require(
        row["endpoint"] == contract["endpoint"] and row["version"] == 2,
        "evidence source version",
    )
    if row["kind"] == "COUNTY_VALUES":
        require(
            row["values_sha256"]
            == hashlib.sha256(
                (ROOT / "data/county_date_cells.csv").read_bytes()
            ).hexdigest(),
            "actual county values hash",
        )
    else:
        require(
            row["values_sha256"] is None, "metadata/filter not invented county values"
        )
print(
    json.dumps(
        dict(
            status="PASS",
            finite_conditions=n,
            current_records=sum(counts.values()),
            scope="Saved sufficient-source accounting,eligibility,hash lineage and evidence kinds;native sources checked separately.",
        )
    )
)
