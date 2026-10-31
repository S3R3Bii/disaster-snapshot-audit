"""Audit current-record calendar probes; no historical funding values are reconstructed."""

from pathlib import Path
from datetime import datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from collections import defaultdict
import argparse, csv, json

ROOT = Path(__file__).resolve().parents[1]
COUNT_FIELDS = [
    "record_count",
    "eligible_money_records",
    "excluded_missing_key_records",
    "excluded_duplicate_key_records",
    "excluded_amount_records",
]


def load(name):
    return json.loads((ROOT / name).read_bytes())


def source_cells():
    with (ROOT / "data/county_date_cells.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row["disaster"] = int(row["disaster"])
        for field in COUNT_FIELDS:
            row[field] = int(row[field])
        row["money"] = (
            Decimal(row["eligible_federal_usd"])
            if row["eligible_federal_usd"]
            else Decimal(0)
        )
    return rows


def text(value):
    if value is None:
        return ""
    if value == 0:
        return "0"
    token = format(value, "f")
    return token.rstrip("0").rstrip(".") if "." in token else token


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ratio(numerator, denominator):
    return (
        Fraction(numerator) / Fraction(denominator)
        if denominator is not None and denominator != 0
        else None
    )


def selected(cell, selector, cutoff):
    token = (
        cell["first_obligation_day"]
        if selector == "firstObligationDate"
        else cell["last_refresh_utc"]
    )
    if token in ["__MISSING__", "__INVALID__"]:
        return None
    return (
        token <= cutoff[:10]
        if selector == "firstObligationDate"
        else stamp(token) <= stamp(cutoff)
    )


def sums(cells):
    return dict(
        records=sum(c["record_count"] for c in cells),
        eligible_money_records=sum(c["eligible_money_records"] for c in cells),
        amount=sum((c["money"] for c in cells), Decimal(0)),
        missing_key_records=sum(c["excluded_missing_key_records"] for c in cells),
        duplicate_key_records=sum(c["excluded_duplicate_key_records"] for c in cells),
        missing_amount_records=sum(c["excluded_amount_records"] for c in cells),
    )


def save_json(out, name, value):
    (out / name).write_bytes(
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    )


def save_csv(out, name, rows):
    with (out / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    cells = source_cells()
    contract = load("data/source_contract.json")
    groups = defaultdict(list)
    for cell in cells:
        groups[("COUNTY", cell["disaster"], cell["county_key"])].append(cell)
        groups[("DISASTER", cell["disaster"], "ALL_CURRENT_RECORDS")].append(cell)
    for disaster in contract["fixed_disasters"]:
        groups.setdefault(("DISASTER", disaster, "ALL_CURRENT_RECORDS"), [])
    current = []
    probes = []
    with localcontext() as context:
        context.prec = 80
        for (level, disaster, key), items in sorted(groups.items()):
            total = sums(items)
            money = total["amount"] if total["eligible_money_records"] else None
            current.append(
                dict(
                    level=level,
                    disaster=disaster,
                    group_key=key,
                    current_records=total["records"],
                    current_eligible_money_records=total["eligible_money_records"],
                    current_reported_federal_usd=text(money),
                    excluded_missing_key_records=total["missing_key_records"],
                    excluded_duplicate_key_records=total["duplicate_key_records"],
                    excluded_amount_records=total["missing_amount_records"],
                    unknown_first_obligation_records=sum(
                        c["record_count"]
                        for c in items
                        if c["first_obligation_day"].startswith("__")
                    ),
                    unknown_last_refresh_records=sum(
                        c["record_count"]
                        for c in items
                        if c["last_refresh_utc"].startswith("__")
                    ),
                )
            )
            for cutoff in contract["cutoffs"]:
                for selector in contract["date_fields"]:
                    yes = []
                    unknown = []
                    for cell in items:
                        choice = selected(cell, selector, cutoff)
                        if choice is None:
                            unknown.append(cell)
                        elif choice:
                            yes.append(cell)
                    a = sums(yes)
                    u = sums(unknown)
                    fraction = ratio(a["records"], total["records"])
                    dollar = ratio(a["amount"], money)
                    probes.append(
                        dict(
                            level=level,
                            disaster=disaster,
                            group_key=key,
                            cutoff=cutoff,
                            selector=selector,
                            current_records=total["records"],
                            current_eligible_money_records=total[
                                "eligible_money_records"
                            ],
                            current_reported_federal_usd=text(money),
                            selected_current_records=a["records"],
                            selected_eligible_money_records=a["eligible_money_records"],
                            selected_current_reported_federal_usd=text(
                                a["amount"] if money is not None else None
                            ),
                            unknown_date_records=u["records"],
                            unknown_date_eligible_money_records=u[
                                "eligible_money_records"
                            ],
                            unknown_date_reported_federal_usd=text(
                                u["amount"] if money is not None else None
                            ),
                            not_selected_known_date_records=total["records"]
                            - a["records"]
                            - u["records"],
                            record_fraction=(
                                str(fraction) if fraction is not None else ""
                            ),
                            reported_dollar_fraction=(
                                str(dollar) if dollar is not None else ""
                            ),
                            status="CURRENT_RECORD_FILTER_NOT_HISTORICAL_VALUES",
                        )
                    )
    snapshots = load("data/metadata_snapshots.json")
    a, b = snapshots
    metadata = dict(
        earlier_capture_utc=a["captured_utc"],
        later_capture_utc=b["captured_utc"],
        fields=[
            dict(
                field=k,
                earlier=a["fields"][k],
                later=b["fields"][k],
                equal=a["fields"][k] == b["fields"][k],
            )
            for k in a["fields"]
        ],
        native_payload_sha256_equal=a["source_sha256"] == b["source_sha256"],
        qualification="These captures contain metadata,not earlier county financial values. Equal indicators do not prove unchanged totals.",
    )
    summary = dict(
        fixed_disasters=contract["fixed_disasters"],
        current_records=sum(c["record_count"] for c in cells),
        county_groups=sum(r["level"] == "COUNTY" for r in current),
        source_sufficient_cells=len(cells),
        cutoffs=len(contract["cutoffs"]),
        selectors=contract["date_fields"],
        probe_rows=len(probes),
        current_summary_rows=len(current),
        metadata_captures=len(snapshots),
        current_county_value_captures=1,
        historical_county_value_captures=0,
        stability_horizon=None,
        county_meaning="applicant location;not necessarily damaged-work location",
        monetary_meaning="reported federal grant funding available to grantee;not paid cash or official financial reporting",
        qualification="Fixed source-informed current-record audit. No historical revision error,recovery effect,funding need,waiting period or national generalization.",
    )
    save_csv(out, "current_totals.csv", current)
    save_csv(out, "probe_metrics.csv", probes)
    save_json(out, "metadata_comparison.json", metadata)
    save_json(out, "summary.json", summary)
    print(
        json.dumps(
            dict(
                status="PASS",
                current_records=summary["current_records"],
                county_groups=summary["county_groups"],
                probe_rows=len(probes),
                historical_stability="UNESTABLISHED",
            )
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "results")
    run(p.parse_args().out)
