"""Verify actual PDF/TeX bindings, complete evidence qualifiers and scoped bytes."""

from pathlib import Path
from decimal import Decimal, localcontext
from fractions import Fraction
import csv, hashlib, json, re, unicodedata
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
read = lambda n: json.loads((ROOT / n).read_bytes())
n = 0


def require(ok, label):
    global n
    assert ok, label
    n += 1


def expected(binding):
    file = binding["file"]
    if file.endswith(".csv"):
        with (ROOT / file).open(encoding="utf-8", newline="") as stream:
            value = list(csv.DictReader(stream))
    else:
        value = read(file)
    if binding["query"]:
        matches = [
            r for r in value if all(r[k] == v for k, v in binding["query"].items())
        ]
        if binding["operation"] == "count":
            return str(len(matches))
        require(len(matches) == 1, "unique source row")
        value = matches[0]
    if binding["operation"] == "count":
        return str(len(value))
    for k in binding["field"] or []:
        value = value[k]
    op = binding["operation"]
    if op == "length":
        return str(len(value))
    if op == "commas":
        return format(int(value), ",")
    if op == "money2":
        return format(Decimal(value), ",.2f")
    if op == "percent2":
        exact = Fraction(value) * 100
        with localcontext() as context:
            context.prec = 80
            return format(Decimal(exact.numerator) / Decimal(exact.denominator), ".2f")
    if op == "date":
        return value[:10]
    if op == "join":
        return "; ".join(value)
    return str(value)


tex = (ROOT / "paper/main.tex").read_text(encoding="utf-8")
pdf = PdfReader(ROOT / "paper/manuscript.pdf")
text = (
    unicodedata.normalize("NFKC", "\n".join(p.extract_text() or "" for p in pdf.pages))
    .replace("\u2019", "'")
    .replace("\u2212", "-")
)
compact = re.sub(r"\s+", " ", text)
words = re.sub(r"([A-Za-z])-\s+([A-Za-z])", r"\1\2", text)
words = re.sub(r"\s+", " ", words)
require(len(pdf.pages) == 5, "five current manuscript pages")
bindings = read("paper/bindings.json")
require(
    len(bindings) == 61 and len({b["name"] for b in bindings}) == 61,
    "61 unique used bindings",
)
for b in bindings:
    value = expected(b)
    require(value == b["display"], "source value/format")
    require(
        "\\newcommand{\\" + b["name"] + "}{" + value + "}" in tex,
        "actual TeX definition",
    )
    require(
        len(re.findall(r"\\" + re.escape(b["name"]) + r"\b", tex)) >= 2,
        "binding used beyond definition",
    )
    require(value in compact, "actual PDF numeric/source text")
for phrase in [
    "Not peer reviewed",
    "not endorsed by FEMA",
    "not paid cash",
    "not a national sample",
    "not certified geographic units",
    "current record's first obligation date does not recover an earlier amount",
    "not an original publication time",
    "remains unexecuted",
    "not estimates of the amounts visible in2018",
    "not zero past funding",
    "curated definition tags",
    "not an observed historical comparison",
    "not redownload mutable native sources",
    "not intended for official federal reporting",
    "no deployment",
    "Azure optimization",
]:
    phrase = phrase.replace("in2018", "in 2018")
    require(phrase.lower() in words.lower(), ("scope qualification", phrase))
for code in ["15", "113", "201"]:
    require(code in compact, "raw code examples")
catalog = read("data/county_catalog.json")
mixed = [r for r in catalog if r["multiple_source_names"]]
require(
    len(mixed) == 22
    and all(any(x.lower() == "statewide" for x in r["county_names"]) for r in mixed),
    "mixed source labels claim",
)
require(
    read("results/verification.json")["authored_fixture_methods"] == 38,
    "current38 fixture methods",
)
for version in ["310", "312"]:
    replay = read("results/reproduction_cpython" + version + ".json")
    require(
        replay["status"] == "PASS" and replay["full_history"],
        "isolated full-history replay",
    )
    require(
        len(replay["reproduced_files"]) == 5 and replay["unchanged_source_files"] == 11,
        "five outputs/11 data files",
    )
    for name in replay["reproduced_files"]:
        require(
            hashlib.sha256((ROOT / "results" / name).read_bytes()).hexdigest()
            == read("results/verification.json")["result_sha256"][name],
            "current unchanged replay result",
        )
scope = read("paper/PUBLICATION_SCOPE.json")
require(
    scope["scope"] == "independent-program-study"
    and scope["formal_submission_target"] is False,
    "scoped independent publication",
)
require(len(scope["public_files"]) == 5, "five approved paper files")
for name, sha in scope["public_files"].items():
    require(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, "scoped bytes"
    )
for name in ["current_record_probes", "current_dollar_probes", "source_county_flags"]:
    require(
        (ROOT / "figures" / (name + ".pdf")).read_bytes()
        == (ROOT / "paper/images" / (name + ".pdf")).read_bytes(),
        "current figure copy",
    )
visual = read("paper/visual_review.json")
require(
    visual["manuscript_sha256"]
    == hashlib.sha256((ROOT / "paper/manuscript.pdf").read_bytes()).hexdigest(),
    "reviewed PDF version",
)
require(visual["pages_reviewed"] == [1, 2, 3, 4, 5], "all five current pages reviewed")
notice = (
    (ROOT / "DATA_RIGHTS.md")
    .read_text(encoding="utf-8")
    .split("Required notice:\n\n", 1)[1]
    .strip()
    .replace("\u2019", "'")
)
require(
    re.sub(r"\s+", " ", notice).lower() in words.lower(), "required FEMA notice words"
)
receipt = dict(
    status="PASS",
    finite_conditions=n,
    used_numeric_bindings=len(bindings),
    pages=5,
    scope_files=5,
    scope="Actual source-bound TeX use,PDF text,source qualifiers,complete examples,current replay hashes,required FEMA notice and reviewed publication scope. No geography,historical-stability or universal-correctness claim.",
)
(ROOT / "paper/verification.json").write_bytes(
    (json.dumps(receipt, indent=2) + "\n").encode()
)
print(json.dumps(receipt))
