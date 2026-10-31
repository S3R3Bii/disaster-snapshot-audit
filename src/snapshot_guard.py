"""Retain evidence types and reject unsupported county-history comparisons."""

from datetime import datetime
import re

DEFINITION_FIELDS = [
    "endpoint",
    "version",
    "amount_field",
    "county_meaning",
    "population",
]


def aware(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp if stamp.tzinfo is not None else None
    except (AttributeError, ValueError, TypeError):
        return None


def validate_comparison(request, evidence):
    def reject(reason):
        return dict(accepted=False, reason=reason, comparison=None)

    if not isinstance(request, dict) or not isinstance(evidence, dict):
        return reject("INVALID_REQUEST_OR_EVIDENCE")
    mode = request.get("mode")
    if mode == "STABILITY_HORIZON":
        return reject("STABILITY_HORIZON_NOT_ESTABLISHED")
    if mode not in ["CURRENT_DESCRIPTION", "DATED_VALUE_COMPARISON"]:
        return reject("UNSUPPORTED_MODE")
    ids = request.get("evidence_ids", [])
    if not isinstance(ids, (list, tuple)) or any(
        not isinstance(x, str) or not x for x in ids
    ):
        return reject("INVALID_EVIDENCE_IDS")
    wanted = 1 if mode == "CURRENT_DESCRIPTION" else 2
    if len(ids) != wanted or len(set(ids)) != wanted:
        return reject("WRONG_NUMBER_OF_DISTINCT_SNAPSHOTS")
    if any(k not in evidence for k in ids):
        return reject("MISSING_EVIDENCE")
    rows = [evidence[k] for k in ids]
    if any(x.get("kind") != "COUNTY_VALUES" for x in rows):
        return reject("MISSING_ACTUAL_COUNTY_VALUES")
    for row in rows:
        if row.get("coverage_status") != "DECLARED_COUNTS_RECONCILED":
            return reject("INCOMPLETE_COVERAGE")
        digest = row.get("values_sha256")
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            return reject("MISSING_VALUES_HASH")
        if aware(row.get("capture_end_utc")) is None:
            return reject("AMBIGUOUS_CAPTURE_TIME")
        if any(row.get(k) is None for k in DEFINITION_FIELDS):
            return reject("UNKNOWN_SOURCE_DEFINITION")
        if any(request.get(k) != row[k] for k in DEFINITION_FIELDS):
            return reject("SOURCE_DEFINITION_MISMATCH")
    if mode == "DATED_VALUE_COMPARISON":
        if aware(rows[0]["capture_end_utc"]) >= aware(rows[1]["capture_end_utc"]):
            return reject("SNAPSHOTS_NOT_IN_TIME_ORDER")
        if any(rows[0][k] != rows[1][k] for k in DEFINITION_FIELDS):
            return reject("SOURCE_DEFINITION_MISMATCH")
    return dict(
        accepted=True,
        reason=(
            "QUALIFIED_CURRENT_DESCRIPTION"
            if mode == "CURRENT_DESCRIPTION"
            else "QUALIFIED_DATED_VALUE_COMPARISON"
        ),
        comparison=dict(
            mode=mode,
            evidence_ids=ids,
            definition={k: rows[0][k] for k in DEFINITION_FIELDS},
            qualification="Curated evidence and declared coverage only;not atomicity,original publication,damaged-work geography or a stability horizon.",
        ),
    )
