"""Capture the two fixed official cohorts without calculating filter comparisons."""

from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, subprocess
import requests

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def capture(folder):
    assert (
        not folder.exists()
    ), "use a new private source directory;preserve earlier attempts"
    folder.mkdir(parents=True)
    contract = json.loads((ROOT / "data/source_contract.json").read_bytes())
    protocol_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    before = json.loads((ROOT / "data/metadata_snapshots.json").read_bytes())[-1][
        "fields"
    ]
    session = requests.Session()
    receipts = []
    cohorts = []

    def get(label, url, params):
        started = datetime.now(timezone.utc).isoformat()
        response = session.get(url, params=params, timeout=40)
        raw = response.content
        (folder / (label + ".json")).write_bytes(raw)
        receipt = dict(
            file=label + ".json",
            url=response.url,
            status=response.status_code,
            bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            captured_utc=datetime.now(timezone.utc).isoformat(),
            started_utc=started,
        )
        receipts.append(receipt)
        write(folder / "request-progress.json", receipts)
        assert response.status_code == 200, (
            label,
            "official source unavailable",
            response.status_code,
        )
        return response.json(), receipt

    try:
        for disaster in contract["fixed_disasters"]:
            params = {
                "$filter": "disasterNumber eq " + str(disaster),
                "$select": ",".join(contract["selected_fields"]),
                "$orderby": ",".join(contract["order_by"]),
                "$top": contract["page_size"],
                "$skip": 0,
                "$metadata": "true",
                "$count": "true",
                "$format": "json",
            }
            page = 0
            expected = None
            total = 0
            while expected is None or total < expected:
                assert page < 10, "predeclared100000-record cohort budget exceeded"
                params["$skip"] = total
                params["$count"] = "true" if page == 0 else "false"
                value, receipt = get(
                    str(disaster) + "-page-" + str(page).zfill(3),
                    contract["endpoint"],
                    params,
                )
                meta = value["metadata"]
                rows = value["PublicAssistanceFundedProjectsDetails"]
                if expected is None:
                    expected = meta["count"]
                    assert isinstance(expected, int) and 0 <= expected <= 100000
                assert meta["skip"] == total and meta["top"] == contract["page_size"]
                assert len(rows) == min(expected - total, contract["page_size"]), (
                    disaster,
                    "page coverage",
                    page,
                    len(rows),
                    expected,
                    total,
                )
                for row in rows:
                    assert row["disasterNumber"] == disaster
                    assert set(contract["selected_fields"]).issubset(row)
                    assert not (
                        set(row) - set(contract["selected_fields"]) - {"id", "hash"}
                    ), "API field selection unexpectedly widened"
                total += len(rows)
                page += 1
                print(
                    json.dumps(
                        dict(
                            disaster=disaster,
                            page=page,
                            records=len(rows),
                            captured=total,
                            declared_total=expected,
                        )
                    ),
                    flush=True,
                )
                if expected == 0:
                    break
            _, final = get(
                str(disaster) + "-final-count",
                contract["endpoint"],
                {
                    "$filter": "disasterNumber eq " + str(disaster),
                    "$select": "disasterNumber",
                    "$top": 1,
                    "$count": "true",
                    "$metadata": "true",
                    "$format": "json",
                },
            )
            final_value = json.loads((folder / final["file"]).read_bytes())
            assert (
                final_value["metadata"]["count"] == expected
            ), "source count changed during capture"
            cohorts.append(
                dict(
                    disaster=disaster,
                    declared_count=expected,
                    captured_records=total,
                    pages=page,
                    coverage="PASS_DECLARED_COUNTS",
                )
            )
        value, receipt = get(
            "final-dataset-metadata",
            contract["metadata_url"],
            {
                "$filter": "name eq 'PublicAssistanceFundedProjectsDetails'",
                "$format": "json",
            },
        )
        after = value["OpenFemaDataSets"][0]
        assert after["version"] == contract["version"]
        assert (
            after["lastDataSetRefresh"] == before["lastDataSetRefresh"]
        ), "declared dataset refresh changed during capture"
        manifest = dict(
            status="PASS_DECLARED_CAPTURE_COVERAGE",
            protocol_and_method_head=protocol_head,
            endpoint=contract["endpoint"],
            version=contract["version"],
            cohorts=cohorts,
            requests=receipts,
            before_dataset_refresh=before["lastDataSetRefresh"],
            after_dataset_refresh=after["lastDataSetRefresh"],
            qualification="Current multi-request capture. Count/refresh consistency does not prove atomicity,immutable history or unchanged past values. No filter comparisons run.",
        )
        write(folder / "capture-receipt.json", manifest)
        write(ROOT / "data/capture_manifest.json", manifest)
        print(
            "FIXED_SOURCE_CAPTURE_COMPLETE_NO_FILTER_COMPARISONS",
            sum(c["captured_records"] for c in cohorts),
            flush=True,
        )
    except Exception as error:
        write(
            folder / "capture-failure.json",
            dict(
                status="FAIL",
                error=str(error),
                protocol_and_method_head=protocol_head,
                requests_completed=len(receipts),
                comparisons_run=False,
            ),
        )
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source-dir", type=Path, required=True)
    capture(p.parse_args().source_dir.resolve())
