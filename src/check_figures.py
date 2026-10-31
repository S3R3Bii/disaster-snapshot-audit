"""Check actual SVG bar geometry and labels against source CSV/catalog values."""

from pathlib import Path
from fractions import Fraction
import csv, hashlib, json, math, re, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "results/probe_metrics.csv").open(encoding="utf-8", newline="") as stream:
    metrics = list(csv.DictReader(stream))
catalog = json.loads((ROOT / "data/county_catalog.json").read_bytes())
three = sum(len(r["county_code"]) == 3 and r["county_code"].isdigit() for r in catalog)
mixed = sum(
    any(n.lower() == "statewide" for n in r["county_names"])
    and len(r["county_names"]) > 1
    for r in catalog
)
counts = dict(
    three_digits=three,
    other_format=len(catalog) - three,
    mixed_statewide=mixed,
    other_labels=len(catalog) - mixed,
)
manifest = json.loads((ROOT / "figures/manifest.json").read_bytes())
n = 0
coordinates = 0
artists = 0


def require(ok, label):
    global n
    assert ok, label
    n += 1


for row in catalog:
    parts = json.loads(row["county_key"])
    require(
        parts[0] == row["disaster"] and parts[1] == row["state_code"],
        "native-verified group context",
    )
    require(
        (
            (parts[2] == "CODE" and parts[3] == row["county_code"])
            if row["county_code"]
            else (parts[2] == "NAME" and parts[3] in row["county_names"])
        ),
        "raw code/name matches native-verified key",
    )
    require(
        row["multiple_source_names"] == (len(row["county_names"]) > 1),
        "label flag matches retained names",
    )
    code = row["county_code"]
    shape = (
        "MISSING"
        if not code
        else (
            "ZERO"
            if code == "000"
            else "THREE_DIGITS" if len(code) == 3 and code.isdigit() else "OTHER"
        )
    )
    require(
        row["source_code_shape"] == shape, "code-shape flag matches raw source string"
    )
for name, info in manifest.items():
    for extension, sha in info["sha256"].items():
        require(
            hashlib.sha256(
                (ROOT / "figures" / (name + "." + extension)).read_bytes()
            ).hexdigest()
            == sha,
            "asset SHA",
        )
    tree = ET.fromstring((ROOT / "figures" / (name + ".svg")).read_bytes())
    ns = {"s": "http://www.w3.org/2000/svg"}
    groups = {g.attrib["id"]: g for g in tree.findall(".//s:g[@id]", ns)}
    texts = [t.text or "" for t in tree.findall(".//s:text", ns)]
    for a in info["artists"]:
        artists += 1
        require(a["id"] in groups, "actual SVG bar")
        path = groups[a["id"]].find(".//s:path", ns)
        require(path is not None, "bar path")
        numbers = [
            float(x)
            for x in re.findall(
                r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?", path.attrib["d"], re.I
            )
        ]
        xs, ys = numbers[0::2], numbers[1::2]
        if a["kind"] == "percent_bar":
            rows = [r for r in metrics if all(r[k] == v for k, v in a["query"].items())]
            require(len(rows) == 1, "unique source metric")
            value = float(Fraction(rows[0][a["field"]]) * 100)
            width = 676.8
            height = 324
            panel_left = 0.09 if a["panel"] == 0 else 0.57
            shift = -0.16 if a["selector"] == "firstObligationDate" else 0.16
            expected = [
                panel_left * width
                + (a["category"] + shift - 0.14 + 0.6) / 5.2 * 0.38 * width,
                0.28 / 5.2 * 0.38 * width,
                0.72 * height,
                value / 110 * 0.50 * height,
            ]
            actual = [min(xs), max(xs) - min(xs), max(ys), max(ys) - min(ys)]
            if value == 0:
                require("0" in texts, "zero current slice labelled")
            elif a["category"] == 0 and a["selector"] == "firstObligationDate":
                require(f"{value:.2f}%" in texts, "numeric current fraction label")
        else:
            value = counts[a["id"]]
            width = 676.8
            height = 273.6
            expected = [
                0.36 * width,
                value / 132 * 0.58 * width,
                0.18 * height + (a["row"] - 0.275 + 0.7) / 5.4 * 0.58 * height,
                0.55 / 5.4 * 0.58 * height,
            ]
            actual = [min(xs), max(xs) - min(xs), min(ys), max(ys) - min(ys)]
            require(str(value) in texts, "source flag count label")
        require(
            math.isclose(a["artist_value"], value, rel_tol=1e-13, abs_tol=1e-12),
            "artist source value",
        )
        for left, right in zip(actual, expected):
            require(abs(left - right) < 0.00002, "actual SVG source coordinate")
            coordinates += 1
require(artists == 44, "complete 20+20+4 source bars")
receipt = dict(
    status="PASS",
    finite_conditions=n,
    source_bound_artists=artists,
    svg_coordinate_conditions=coordinates,
    asset_hashes=9,
    scope="Actual SVG bars,source-derived extents,numeric labels,artist values and asset hashes. Visual review recorded separately;no geography or accessibility certification.",
)
(ROOT / "figures/verification.json").write_bytes(
    (json.dumps(receipt, indent=2) + "\n").encode()
)
print(json.dumps(receipt))
