"""Run seven authored requests against actual captured evidence types."""

from pathlib import Path
import argparse, json
from snapshot_guard import validate_comparison

ROOT = Path(__file__).resolve().parents[1]


def run(out):
    evidence = json.loads((ROOT / "data/exercise_evidence.json").read_bytes())
    requests = json.loads((ROOT / "data/exercise_inputs.json").read_bytes())
    rows = [
        dict(
            name=r["name"],
            request=r["request"],
            result=validate_comparison(r["request"], evidence),
        )
        for r in requests
    ]
    out.mkdir(parents=True, exist_ok=True)
    (out / "exercise.json").write_bytes(
        (json.dumps(rows, indent=2, sort_keys=True) + "\n").encode()
    )
    print(
        json.dumps(
            dict(
                status="PASS",
                examples=len(rows),
                accepted=sum(r["result"]["accepted"] for r in rows),
            )
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "results")
    run(p.parse_args().out)
