"""Additional aggregation boundaries after first probe checks; no source/probe rule changed."""

from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import csv, hashlib, json, sys, unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import project_source


class MonetaryAggregationTests(unittest.TestCase):
    def run_source_fixture(self, rows):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            native = root / "native"
            native.mkdir()
            raw = (
                json.dumps({"PublicAssistanceFundedProjectsDetails": rows}) + "\n"
            ).encode()
            (native / "4332-page-000.json").write_bytes(raw)
            manifest = dict(
                requests=[
                    dict(
                        file="4332-page-000.json",
                        sha256=hashlib.sha256(raw).hexdigest(),
                        bytes=len(raw),
                    )
                ],
                cohorts=[
                    dict(
                        disaster=4332,
                        captured_records=len(rows),
                        declared_count=len(rows),
                    )
                ],
            )
            (root / "data/capture_manifest.json").write_bytes(
                json.dumps(manifest).encode()
            )
            with patch.object(project_source, "ROOT", root), redirect_stdout(
                StringIO()
            ):
                project_source.run(native)
            with (root / "data/county_date_cells.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                return list(csv.DictReader(stream))

    def row(self, gm, value, **changes):
        row = dict(
            disasterNumber=4332,
            gmProjectId=gm,
            applicantId="SYNTHETIC_ORG",
            pwNumber=1,
            county="Fixture County",
            countyCode="001",
            stateNumberCode="48",
            stateAbbreviation="TX",
            firstObligationDate="2018-01-01T00:00:00Z",
            lastRefresh="2026-01-01T00:00:00Z",
            federalShareObligated=value,
        )
        row.update(changes)
        return row

    def test_whole_duplicate_group_and_missing_inputs_excluded(self):
        rows = [
            self.row(7, 100),
            self.row(7, 200),
            self.row(8, -12.34),
            self.row(9, None),
            self.row(None, 99, applicantId=None, pwNumber=None),
        ]
        output = self.run_source_fixture(rows)
        self.assertEqual(len(output), 1)
        cell = output[0]
        self.assertEqual(
            [
                cell[k]
                for k in [
                    "record_count",
                    "eligible_money_records",
                    "excluded_duplicate_key_records",
                    "excluded_missing_key_records",
                    "excluded_amount_records",
                ]
            ],
            ["5", "1", "2", "1", "1"],
        )
        self.assertEqual(cell["eligible_federal_usd"], "-12.34")

    def test_all_ineligible_money_is_unavailable_not_zero(self):
        output = self.run_source_fixture(
            [self.row(1, None), self.row(2, None), self.row(3, None)]
        )
        self.assertEqual(output[0]["record_count"], "3")
        self.assertEqual(output[0]["eligible_money_records"], "0")
        self.assertEqual(output[0]["eligible_federal_usd"], "")


if __name__ == "__main__":
    unittest.main()
