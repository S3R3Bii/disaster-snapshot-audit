"""Authored time, provenance, identity and monetary boundary fixtures."""

from pathlib import Path
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import sys, unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snapshot_guard import validate_comparison
from project_source import (
    calendar_day,
    store_instant,
    project_key,
    amount,
    MISSING,
    INVALID,
)
from analyze import ratio, selected


class SnapshotGuardTests(unittest.TestCase):
    def setUp(self):
        # These are authored interface fixtures,not observed historical FEMA snapshots.
        self.definition = dict(
            endpoint="official-fixture-v2",
            version=2,
            amount_field="federalShareObligated",
            county_meaning="applicant_location",
            population="obligated_v2",
        )
        self.a = dict(
            kind="COUNTY_VALUES",
            capture_end_utc="2024-02-29T00:00:00Z",
            coverage_status="DECLARED_COUNTS_RECONCILED",
            values_sha256="1" * 64,
            **self.definition
        )
        self.b = dict(
            self.a, capture_end_utc="2024-03-01T00:00:00Z", values_sha256="2" * 64
        )
        self.evidence = {"a": self.a, "b": self.b}
        self.request = dict(
            mode="CURRENT_DESCRIPTION", evidence_ids=["a"], **self.definition
        )

    def verdict(self):
        return validate_comparison(self.request, self.evidence)

    def test_current_description(self):
        self.assertTrue(self.verdict()["accepted"])

    def test_two_authored_comparable_values(self):
        self.request.update(mode="DATED_VALUE_COMPARISON", evidence_ids=["a", "b"])
        self.assertTrue(self.verdict()["accepted"])

    def test_metadata_has_no_county_values(self):
        self.a["kind"] = "METADATA_ONLY"
        self.assertEqual(self.verdict()["reason"], "MISSING_ACTUAL_COUNTY_VALUES")

    def test_current_filter_is_not_historical(self):
        self.a["kind"] = "CURRENT_FILTER"
        self.assertFalse(self.verdict()["accepted"])

    def test_version_mismatch(self):
        self.request["version"] = 1
        self.assertEqual(self.verdict()["reason"], "SOURCE_DEFINITION_MISMATCH")

    def test_endpoint_mismatch(self):
        self.request["endpoint"] = "different-source"
        self.assertFalse(self.verdict()["accepted"])

    def test_population_mismatch(self):
        self.request["population"] = "includes_preobligation"
        self.assertFalse(self.verdict()["accepted"])

    def test_applicant_location_not_damage_location(self):
        self.request["county_meaning"] = "damaged_worksite"
        self.assertFalse(self.verdict()["accepted"])

    def test_obligated_field_not_cash(self):
        self.request["amount_field"] = "paid_cash"
        self.assertFalse(self.verdict()["accepted"])

    def test_incomplete_coverage(self):
        self.a["coverage_status"] = "PARTIAL"
        self.assertEqual(self.verdict()["reason"], "INCOMPLETE_COVERAGE")

    def test_missing_values_hash(self):
        self.a["values_sha256"] = None
        self.assertEqual(self.verdict()["reason"], "MISSING_VALUES_HASH")

    def test_opaque_metadata_hash_not_payload_hash(self):
        self.a["values_sha256"] = "a" * 40
        self.assertFalse(self.verdict()["accepted"])

    def test_naive_capture_time(self):
        self.a["capture_end_utc"] = "2024-02-29T00:00:00"
        self.assertEqual(self.verdict()["reason"], "AMBIGUOUS_CAPTURE_TIME")

    def test_reversed_observation_order(self):
        self.request.update(mode="DATED_VALUE_COMPARISON", evidence_ids=["b", "a"])
        self.assertEqual(self.verdict()["reason"], "SNAPSHOTS_NOT_IN_TIME_ORDER")

    def test_same_snapshot_twice(self):
        self.request.update(mode="DATED_VALUE_COMPARISON", evidence_ids=["a", "a"])
        self.assertFalse(self.verdict()["accepted"])

    def test_horizon_not_established_by_two_points(self):
        self.request.update(mode="STABILITY_HORIZON", evidence_ids=["a", "b"])
        self.assertEqual(self.verdict()["reason"], "STABILITY_HORIZON_NOT_ESTABLISHED")

    def test_missing_evidence(self):
        self.request["evidence_ids"] = ["absent"]
        self.assertEqual(self.verdict()["reason"], "MISSING_EVIDENCE")

    def test_invalid_request(self):
        self.assertFalse(validate_comparison(None, self.evidence)["accepted"])

    def test_invalid_id_list(self):
        self.request["evidence_ids"] = None
        self.assertEqual(self.verdict()["reason"], "INVALID_EVIDENCE_IDS")

    def test_unknown_definition(self):
        self.a["population"] = None
        self.assertEqual(self.verdict()["reason"], "UNKNOWN_SOURCE_DEFINITION")


class SourceBoundaryTests(unittest.TestCase):
    def test_source_calendar_is_not_utc_instant(self):
        self.assertEqual(calendar_day("2018-12-31T23:30:00-08:00"), "2018-12-31")
        self.assertEqual(
            store_instant("2018-12-31T23:30:00-08:00"), "2019-01-01T07:30:00.000000Z"
        )

    def test_store_requires_timezone(self):
        self.assertEqual(store_instant("2024-02-29T00:00:00"), INVALID)

    def test_invalid_leap_day(self):
        self.assertEqual(calendar_day("2023-02-29T00:00:00Z"), INVALID)

    def test_missing_date_unknown(self):
        self.assertEqual(store_instant(None), MISSING)

    def test_excess_precision_not_silently_truncated(self):
        self.assertEqual(store_instant("2024-01-01T00:00:00.1234567Z"), INVALID)

    def test_exact_utc_cutoff_boundary(self):
        row = dict(
            first_obligation_day="2018-12-31",
            last_refresh_utc="2018-12-31T23:59:59.000001Z",
        )
        self.assertTrue(selected(row, "firstObligationDate", "2018-12-31T23:59:59Z"))
        self.assertFalse(selected(row, "lastRefresh", "2018-12-31T23:59:59Z"))

    def test_unknown_date_not_future(self):
        self.assertIsNone(
            selected(
                dict(first_obligation_day=MISSING),
                "firstObligationDate",
                "2018-12-31T23:59:59Z",
            )
        )

    def test_signed_amount_retained(self):
        self.assertEqual(amount("-12.34"), Decimal("-12.34"))

    def test_nonfinite_amount_unknown(self):
        self.assertIsNone(amount("NaN"))
        self.assertIsNone(amount("Infinity"))

    def test_missing_amount_not_zero(self):
        self.assertIsNone(amount(None))
        self.assertEqual(amount(0), Decimal(0))

    def test_boolean_not_money(self):
        self.assertIsNone(amount(True))

    def test_zero_monetary_denominator_unavailable(self):
        self.assertIsNone(ratio(0, 0))
        self.assertEqual(ratio(0, 10), Fraction(0))

    def test_signed_fraction_not_clamped(self):
        self.assertEqual(ratio(15, 10), Fraction(3, 2))
        self.assertEqual(ratio(-2, 10), Fraction(-1, 5))

    def test_documented_legacy_project_identity(self):
        self.assertEqual(
            project_key(
                dict(
                    disasterNumber=4332,
                    gmProjectId=None,
                    applicantId=" ORG ",
                    pwNumber=7,
                )
            ),
            (4332, "PW", "ORG", 7),
        )

    def test_missing_project_key(self):
        self.assertIsNone(
            project_key(
                dict(
                    disasterNumber=4332,
                    gmProjectId=None,
                    applicantId=None,
                    pwNumber=None,
                )
            )
        )

    def test_boolean_identifier_not_integer(self):
        self.assertIsNone(
            project_key(
                dict(
                    disasterNumber=4332,
                    gmProjectId=True,
                    applicantId=None,
                    pwNumber=None,
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
