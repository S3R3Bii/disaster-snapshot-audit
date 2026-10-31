"""Freeze actual source/method bytes before current-record cutoff comparisons."""

from pathlib import Path
import argparse, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "PLAN_FREEZE.json"


def digest(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()


def run(write=False):
    if write:
        assert not target.exists(), "freeze exists;do not silently replace"
        methods = [
            "capture_source.py",
            "project_source.py",
            "check_native.py",
            "analyze.py",
            "snapshot_guard.py",
            "exercise.py",
            "check_source.py",
            "check_analysis.py",
            "freeze.py",
            "replay.py",
        ]
        paths = (
            [ROOT / "src" / n for n in methods]
            + list((ROOT / "data").glob("*"))
            + list((ROOT / "tests").glob("*.py"))
        )
        paths += [
            ROOT / n
            for n in [
                "PROTOCOL.md",
                "DATA_RIGHTS.md",
                "SOURCE_HISTORY.md",
                "requirements.txt",
                "requirements-source.txt",
            ]
        ]
        value = dict(
            source_checkpoint=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            qualification="Source-informed/current values visible during capture. Fixed before first cutoff comparisons,not blinded and not historical values.",
            dependencies={
                str(f.relative_to(ROOT)).replace("\\", "/"): digest(f)
                for f in sorted(paths)
                if f.is_file()
            },
        )
        target.write_bytes(
            (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        )
    value = json.loads(target.read_bytes())
    for name, sha in value["dependencies"].items():
        assert digest(ROOT / name) == sha, ("changed frozen input", name)
    print(
        json.dumps(
            dict(
                status="PASS",
                dependencies=len(value["dependencies"]),
                freeze_sha256=digest(target),
                source_checkpoint=value["source_checkpoint"],
            )
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    run(p.parse_args().write)
