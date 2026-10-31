"""Reproduce saved current-record audits in a new output directory."""

from pathlib import Path
import argparse, hashlib, json, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]


def call(name, *args):
    subprocess.run(
        [sys.executable, str(ROOT / "src" / name), *map(str, args)],
        cwd=ROOT,
        check=True,
    )


def run(out, analysis_only):
    out = out.resolve()
    assert (
        out != ROOT / "results" and not out.exists()
    ), "use a new separate output directory"
    call("freeze.py")
    call("check_source.py")
    paths = [p for p in (ROOT / "data").iterdir() if p.is_file()]
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    call("analyze.py", "--out", out)
    call("exercise.py", "--out", out)
    names = [
        "current_totals.csv",
        "probe_metrics.csv",
        "metadata_comparison.json",
        "summary.json",
        "exercise.json",
    ]
    for name in names:
        assert (out / name).read_bytes() == (ROOT / "results" / name).read_bytes(), (
            "replay mismatch",
            name,
        )
    call("check_analysis.py")
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        check=True,
    )
    if not analysis_only:
        call("check_figures.py")
        call("check_paper.py")
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after, "source changed"
    receipt = dict(
        status="PASS",
        python=sys.version.split()[0],
        reproduced_files=names,
        unchanged_source_files=len(paths),
        native_redownload=False,
        scope="Saved county/date aggregate replay;not independent reacquisition of mutable native sources or historical values.",
    )
    (out / "REPLAY_RECEIPT.json").write_bytes(
        (json.dumps(receipt, indent=2) + "\n").encode()
    )
    print("PASS_SAVED_DATA_REPLAY", sys.version.split()[0], len(names), len(paths))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--analysis-only", action="store_true")
    a = p.parse_args()
    run(a.out, a.analysis_only)
