"""Independent SQLite and exact Fraction reconstruction of every fixed probe."""

from pathlib import Path
from datetime import datetime, timezone
from fractions import Fraction
from collections import Counter
import csv, hashlib, json, sqlite3
from dateutil.parser import isoparse

ROOT = Path(__file__).resolve().parents[1]
read = lambda n: json.loads((ROOT / n).read_bytes())


def csvrows(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class ExactSum:
    def __init__(self):
        self.value = Fraction(0)
        self.seen = False

    def step(self, value):
        if value is not None:
            self.value += Fraction(value)
            self.seen = True

    def finalize(self):
        return str(self.value) if self.seen else None


def micros(value):
    stamp = isoparse(value).astimezone(timezone.utc) - datetime(
        1970, 1, 1, tzinfo=timezone.utc
    )
    return stamp.days * 86400000000 + stamp.seconds * 1000000 + stamp.microseconds


db = sqlite3.connect(":memory:")
db.create_aggregate("exact_sum", 1, ExactSum)
db.execute(
    "create table cells(disaster integer,county text,first integer,last integer,rc integer,eligible integer,missingkey integer,duplicatekey integer,missingmoney integer,money text)"
)
for row in csvrows("data/county_date_cells.csv"):
    first = (
        None
        if row["first_obligation_day"].startswith("__")
        else isoparse(row["first_obligation_day"]).date().toordinal()
    )
    last = (
        None
        if row["last_refresh_utc"].startswith("__")
        else micros(row["last_refresh_utc"])
    )
    db.execute(
        "insert into cells values(?,?,?,?,?,?,?,?,?,?)",
        (
            int(row["disaster"]),
            row["county_key"],
            first,
            last,
            *[
                int(row[k])
                for k in [
                    "record_count",
                    "eligible_money_records",
                    "excluded_missing_key_records",
                    "excluded_duplicate_key_records",
                    "excluded_amount_records",
                ]
            ],
            row["eligible_federal_usd"] or None,
        ),
    )
db.execute("create index group_index on cells(disaster,county)")
conditions = 0


def eq(a, b, label):
    global conditions
    assert a == b, (label, a, b)
    conditions += 1


def fraction(value):
    return Fraction(value) if value != "" and value is not None else None


def clause(row):
    return (
        ("disaster=?", [int(row["disaster"])])
        if row["level"] == "DISASTER"
        else ("disaster=? and county=?", [int(row["disaster"]), row["group_key"]])
    )


totals = csvrows("results/current_totals.csv")
expected_groups = {
    ("DISASTER", str(d), "ALL_CURRENT_RECORDS")
    for d in read("data/source_contract.json")["fixed_disasters"]
}
expected_groups |= {
    ("COUNTY", str(d), c)
    for d, c in db.execute("select distinct disaster,county from cells")
}
eq(
    {(r["level"], r["disaster"], r["group_key"]) for r in totals},
    expected_groups,
    "complete current groups",
)
for row in totals:
    where, args = clause(row)
    values = db.execute(
        "select coalesce(sum(rc),0),coalesce(sum(eligible),0),exact_sum(money),coalesce(sum(missingkey),0),coalesce(sum(duplicatekey),0),coalesce(sum(missingmoney),0),coalesce(sum(case when first is null then rc else 0 end),0),coalesce(sum(case when last is null then rc else 0 end),0) from cells where "
        + where,
        args,
    ).fetchone()
    for key, val in zip(
        ["current_records", "current_eligible_money_records"], values[:2]
    ):
        eq(int(row[key]), val, key)
    eq(
        fraction(row["current_reported_federal_usd"]),
        fraction(values[2]),
        "current exact amount",
    )
    for key, val in zip(
        [
            "excluded_missing_key_records",
            "excluded_duplicate_key_records",
            "excluded_amount_records",
            "unknown_first_obligation_records",
            "unknown_last_refresh_records",
        ],
        values[3:],
    ):
        eq(int(row[key]), val, key)
metrics = csvrows("results/probe_metrics.csv")
contract = read("data/source_contract.json")
expected_keys = {
    (level, d, key, cut, sel)
    for level, d, key in expected_groups
    for cut in contract["cutoffs"]
    for sel in contract["date_fields"]
}
eq(
    {
        tuple(r[k] for k in ["level", "disaster", "group_key", "cutoff", "selector"])
        for r in metrics
    },
    expected_keys,
    "all fixed group/cutoff/selector cases",
)
eq(len(metrics), len(expected_keys), "unique metric rows")
for row in metrics:
    where, args = clause(row)
    column = "first" if row["selector"] == "firstObligationDate" else "last"
    threshold = (
        isoparse(row["cutoff"]).date().toordinal()
        if column == "first"
        else micros(row["cutoff"])
    )
    q = f"""select coalesce(sum(rc),0),coalesce(sum(eligible),0),exact_sum(money),
      coalesce(sum(case when {column}<=:t then rc else 0 end),0),
      coalesce(sum(case when {column}<=:t then eligible else 0 end),0),
      exact_sum(case when {column}<=:t then money else null end),
      coalesce(sum(case when {column} is null then rc else 0 end),0),
      coalesce(sum(case when {column} is null then eligible else 0 end),0),
      exact_sum(case when {column} is null then money else null end)
      from cells where {where}"""
    # All parameters are positional so the threshold occurs before group filters.
    q = q.replace(":t", "?")
    values = db.execute(q, [threshold, threshold, threshold, *args]).fetchone()
    (
        current_n,
        eligible,
        current_money,
        selected_n,
        selected_e,
        selected_money,
        unknown_n,
        unknown_e,
        unknown_money,
    ) = values
    current_money = fraction(current_money)
    selected_money = Fraction(selected_money or 0) if eligible else None
    unknown_money = Fraction(unknown_money or 0) if eligible else None
    for key, value in [
        ("current_records", current_n),
        ("current_eligible_money_records", eligible),
        ("selected_current_records", selected_n),
        ("selected_eligible_money_records", selected_e),
        ("unknown_date_records", unknown_n),
        ("unknown_date_eligible_money_records", unknown_e),
        ("not_selected_known_date_records", current_n - selected_n - unknown_n),
    ]:
        eq(int(row[key]), value, key)
    for key, value in [
        ("current_reported_federal_usd", current_money),
        ("selected_current_reported_federal_usd", selected_money),
        ("unknown_date_reported_federal_usd", unknown_money),
    ]:
        eq(fraction(row[key]), value, key)
    eq(
        fraction(row["record_fraction"]),
        Fraction(selected_n, current_n) if current_n else None,
        "exact record fraction",
    )
    eq(
        fraction(row["reported_dollar_fraction"]),
        selected_money / current_money if current_money else None,
        "exact dollar fraction",
    )
    eq(row["status"], "CURRENT_RECORD_FILTER_NOT_HISTORICAL_VALUES", "filter scope")
metadata = read("results/metadata_comparison.json")
snapshots = read("data/metadata_snapshots.json")
for row in metadata["fields"]:
    a = snapshots[0]["fields"][row["field"]]
    b = snapshots[1]["fields"][row["field"]]
    eq(
        (row["earlier"], row["later"], row["equal"]),
        (a, b, a == b),
        "metadata source cell",
    )
summary = read("results/summary.json")
for k, wanted in [
    ("current_records", 17994),
    ("county_groups", 132),
    ("source_sufficient_cells", 9844),
    ("probe_rows", len(metrics)),
    ("current_summary_rows", len(totals)),
    ("metadata_captures", 2),
    ("current_county_value_captures", 1),
    ("historical_county_value_captures", 0),
    ("stability_horizon", None),
]:
    eq(summary[k], wanted, k)
expected = {
    "retain_current_description": (True, "QUALIFIED_CURRENT_DESCRIPTION"),
    "reject_metadata_as_history": (False, "MISSING_ACTUAL_COUNTY_VALUES"),
    "reject_current_filter_as_history": (False, "MISSING_ACTUAL_COUNTY_VALUES"),
    "reject_applicant_county_as_damage_location": (False, "SOURCE_DEFINITION_MISMATCH"),
    "reject_grant_field_as_paid_cash": (False, "SOURCE_DEFINITION_MISMATCH"),
    "reject_missing_evidence": (False, "MISSING_EVIDENCE"),
    "reject_stability_horizon": (False, "STABILITY_HORIZON_NOT_ESTABLISHED"),
}
for row in read("results/exercise.json"):
    eq(
        (row["result"]["accepted"], row["result"]["reason"]),
        expected[row["name"]],
        row["name"],
    )
    if not row["result"]["accepted"]:
        eq(row["result"]["comparison"], None, "no invented comparison")
print(
    json.dumps(
        dict(
            status="PASS",
            finite_conditions=conditions,
            compared_current_groups=len(totals),
            compared_probes=len(metrics),
            monetary_method="Exact Fraction sums/ratios;no floating monetary tolerance",
            date_method="Independent dateutil parsing and SQLite integer calendar/UTC-microsecond comparisons",
        )
    )
)
