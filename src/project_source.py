"""Project native records into county/date sufficient aggregates without cutoff comparisons."""

from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, localcontext, InvalidOperation
from collections import Counter, defaultdict
import argparse, csv, hashlib, json

ROOT = Path(__file__).resolve().parents[1]
MISSING = "__MISSING__"
INVALID = "__INVALID__"


def read(path):
    return json.loads(path.read_bytes(), parse_float=Decimal, parse_constant=Decimal)


def calendar_day(value):
    if value is None or value == "":
        return MISSING
    if not isinstance(value, str):
        return INVALID
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return INVALID


def store_instant(value):
    if value is None or value == "":
        return MISSING
    if not isinstance(value, str):
        return INVALID
    try:
        fraction = (
            value.split(".", 1)[1].split("Z")[0].split("+")[0].split("-")[0]
            if "." in value
            else ""
        )
        if len(fraction) > 6:
            return INVALID
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return INVALID
        return (
            stamp.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    except (ValueError, TypeError):
        return INVALID


def project_key(row):
    gm = row.get("gmProjectId")
    if isinstance(gm, int) and not isinstance(gm, bool) and gm >= 0:
        return (row["disasterNumber"], "GM", gm)
    applicant = row.get("applicantId")
    pw = row.get("pwNumber")
    if (
        isinstance(applicant, str)
        and applicant.strip()
        and isinstance(pw, int)
        and not isinstance(pw, bool)
        and pw >= 0
    ):
        return (row["disasterNumber"], "PW", applicant.strip(), pw)
    return None


def amount(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def money_text(value):
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def county(row):
    for name in ["stateNumberCode", "countyCode", "county"]:
        assert row.get(name) is None or isinstance(row[name], str), (
            "unexpected county field type",
            name,
        )
    state = (row.get("stateNumberCode") or "").strip()
    code = (row.get("countyCode") or "").strip()
    label = (row.get("county") or "").strip()
    key = json.dumps(
        [
            row["disasterNumber"],
            state,
            "CODE" if code else "NAME",
            code if code else label or MISSING,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return key, state, code, label


def load_native(folder):
    manifest = json.loads((ROOT / "data/capture_manifest.json").read_bytes())
    rows = []
    for receipt in manifest["requests"]:
        assert Path(receipt["file"]).name == receipt["file"]
        native = folder / receipt["file"]
        raw = native.read_bytes()
        assert (
            hashlib.sha256(raw).hexdigest() == receipt["sha256"]
            and len(raw) == receipt["bytes"]
        )
        if "-page-" in receipt["file"]:
            rows += read(native)["PublicAssistanceFundedProjectsDetails"]
    for cohort in manifest["cohorts"]:
        assert (
            sum(row["disasterNumber"] == cohort["disaster"] for row in rows)
            == cohort["captured_records"]
            == cohort["declared_count"]
        )
    return rows


def run(folder):
    rows = load_native(folder)
    keys = [project_key(r) for r in rows]
    frequencies = Counter(k for k in keys if k is not None)
    grouped = {}
    catalog = {}
    profiles = {}
    with localcontext() as context:
        context.prec = 80
        for row, key in zip(rows, keys):
            disaster = row["disasterNumber"]
            ck, state, code, label = county(row)
            cat = catalog.setdefault(
                ck,
                dict(
                    county_key=ck,
                    disaster=disaster,
                    state_code=state,
                    county_code=code,
                    county_names=set(),
                    state_abbreviations=set(),
                ),
            )
            cat["county_names"].add(label or MISSING)
            cat["state_abbreviations"].add(row["stateAbbreviation"])
            temporal = (
                calendar_day(row.get("firstObligationDate")),
                store_instant(row.get("lastRefresh")),
            )
            cell = grouped.setdefault(
                (ck, *temporal),
                dict(
                    record_count=0,
                    eligible_money_records=0,
                    excluded_missing_key_records=0,
                    excluded_duplicate_key_records=0,
                    excluded_amount_records=0,
                    eligible_federal_usd=Decimal(0),
                ),
            )
            cell["record_count"] += 1
            value = amount(row.get("federalShareObligated"))
            if key is None:
                reason = "excluded_missing_key_records"
            elif frequencies[key] != 1:
                reason = "excluded_duplicate_key_records"
            elif value is None:
                reason = "excluded_amount_records"
            else:
                reason = None
            if reason:
                cell[reason] += 1
            else:
                cell["eligible_money_records"] += 1
                cell["eligible_federal_usd"] += value
            profile = profiles.setdefault(
                disaster,
                Counter(
                    {
                        name: 0
                        for name in [
                            "native_records",
                            "eligible_money_records",
                            "excluded_missing_key_records",
                            "excluded_duplicate_key_records",
                            "excluded_amount_records",
                            "negative_source_amount_records",
                            "unknown_first_obligation_records",
                            "unknown_last_refresh_records",
                        ]
                    }
                ),
            )
            profile["native_records"] += 1
            profile[reason or "eligible_money_records"] += 1
            profile["negative_source_amount_records"] += int(
                value is not None and value < 0
            )
            profile["unknown_first_obligation_records"] += int(
                temporal[0] in [MISSING, INVALID]
            )
            profile["unknown_last_refresh_records"] += int(
                temporal[1] in [MISSING, INVALID]
            )
    columns = [
        "disaster",
        "county_key",
        "first_obligation_day",
        "last_refresh_utc",
        "record_count",
        "eligible_money_records",
        "excluded_missing_key_records",
        "excluded_duplicate_key_records",
        "excluded_amount_records",
        "eligible_federal_usd",
    ]
    with (ROOT / "data/county_date_cells.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for (ck, first, last), cell in sorted(grouped.items()):
            counts = sum(
                cell[k]
                for k in [
                    "eligible_money_records",
                    "excluded_missing_key_records",
                    "excluded_duplicate_key_records",
                    "excluded_amount_records",
                ]
            )
            assert counts == cell["record_count"]
            item = dict(
                disaster=catalog[ck]["disaster"],
                county_key=ck,
                first_obligation_day=first,
                last_refresh_utc=last,
                **cell
            )
            item["eligible_federal_usd"] = (
                money_text(cell["eligible_federal_usd"])
                if cell["eligible_money_records"]
                else ""
            )
            writer.writerow(item)
    for item in catalog.values():
        item["county_names"] = sorted(item["county_names"])
        item["state_abbreviations"] = sorted(item["state_abbreviations"])
        code = item["county_code"]
        item["source_code_shape"] = (
            "MISSING"
            if not code
            else (
                "ZERO"
                if code == "000"
                else "THREE_DIGITS" if len(code) == 3 and code.isdigit() else "OTHER"
            )
        )
        item["multiple_source_names"] = len(item["county_names"]) > 1
        item["qualification"] = (
            "Applicant location;source code not independently validated geography."
        )
    (ROOT / "data/county_catalog.json").write_bytes(
        (
            json.dumps(
                sorted(catalog.values(), key=lambda r: r["county_key"]),
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        ).encode()
    )
    receipt = dict(
        status="SOURCE_PROJECTION_COMPLETE_NOT_YET_INDEPENDENTLY_VERIFIED",
        native_records=len(rows),
        sufficient_cells=len(grouped),
        county_groups=len(catalog),
        cohort_profiles={str(k): dict(v) for k, v in sorted(profiles.items())},
        source_precision="Exact source decimals accumulated at80-digit precision;independent rational verification required.",
        temporal_scope="Source first-obligation calendar dates and aware UTC store-update timestamps;not original publication availability.",
        public_microdata="No project/applicant identifier,names,narratives or addresses. County/date sufficient cells;no individual-assistance data or reidentification.",
        original_historical_stability="UNESTABLISHED",
        cutoff_comparisons_run=False,
    )
    (ROOT / "data/projection_receipt.json").write_bytes(
        (json.dumps(receipt, indent=2) + "\n").encode()
    )
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in [
                    "status",
                    "native_records",
                    "sufficient_cells",
                    "county_groups",
                    "cohort_profiles",
                    "cutoff_comparisons_run",
                ]
            }
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source-dir", type=Path, required=True)
    run(p.parse_args().source_dir)
