"""Independent native JSON/dateutil/SQLite/rational check of the county projection."""

from pathlib import Path
from fractions import Fraction
from datetime import timezone
from collections import Counter
import json, csv, hashlib, re, sqlite3
from dateutil.parser import isoparse
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--source-dir", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
rawdir = args.source_dir
checks = 0


def require(ok, detail):
    global checks
    assert ok, detail
    checks += 1


def unique_pairs(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate native JSON field")
        output[key] = value
    return output


def parse(path):
    return json.loads(
        path.read_bytes(),
        parse_float=str,
        parse_constant=str,
        object_pairs_hook=unique_pairs,
    )


class ExactSum:
    def __init__(self):
        self.value = Fraction(0)
        self.seen = False

    def step(self, value):
        if value is not None:
            self.value += Fraction(value)
            self.seen = True

    def finalize(self):
        return str(self.value) if self.seen else None


db = sqlite3.connect(":memory:")
db.create_aggregate("exact_sum", 1, ExactSum)
db.execute(
    "create table native(disaster integer,state text,code text,label text,abbreviation text,pkey text,first text,last text,money text)"
)
manifest = json.loads((root / "data/capture_manifest.json").read_bytes())
seen_fields = Counter()
native_count = 0
for receipt in manifest["requests"]:
    path = rawdir / receipt["file"]
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == receipt["sha256"], "native payload SHA")
    require(len(data) == receipt["bytes"], "native payload bytes")
    if "-page-" not in path.name:
        continue
    values = parse(path)["PublicAssistanceFundedProjectsDetails"]
    for row in values:
        native_count += 1
        seen_fields.update(row.keys())
        require(row["disasterNumber"] in [4332, 4339], "fixed native cohort")
        gm = row.get("gmProjectId")
        applicant = row.get("applicantId")
        pw = row.get("pwNumber")
        if type(gm) is int and gm >= 0:
            key = str(row["disasterNumber"]) + ":GM:" + str(gm)
        elif (
            isinstance(applicant, str)
            and applicant.strip()
            and type(pw) is int
            and pw >= 0
        ):
            key = json.dumps(
                [row["disasterNumber"], "PW", applicant.strip(), pw], ensure_ascii=False
            )
        else:
            key = None
        try:
            token = row.get("federalShareObligated")
            rational = (
                Fraction(str(token))
                if token is not None and type(token) is not bool
                else None
            )
        except (ValueError, ZeroDivisionError):
            rational = None
        first = "__MISSING__" if not row.get("firstObligationDate") else "__INVALID__"
        last = "__MISSING__" if not row.get("lastRefresh") else "__INVALID__"
        try:
            first = isoparse(row["firstObligationDate"]).date().isoformat()
        except (ValueError, TypeError):
            pass
        try:
            text = row["lastRefresh"]
            fraction = re.search(r"\.(\d+)", text)
            if fraction and len(fraction[1]) > 6:
                raise ValueError("unretained temporal precision")
            stamp = isoparse(text)
            if stamp.tzinfo is None:
                raise ValueError("unknown timezone")
            last = (
                stamp.astimezone(timezone.utc)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            )
        except (ValueError, TypeError):
            pass
        for field in ["stateNumberCode", "countyCode", "county"]:
            require(
                row[field] is None or isinstance(row[field], str),
                "native county field type",
            )
        db.execute(
            "insert into native values(?,?,?,?,?,?,?,?,?)",
            (
                row["disasterNumber"],
                (row["stateNumberCode"] or "").strip(),
                (row["countyCode"] or "").strip(),
                (row["county"] or "").strip(),
                row["stateAbbreviation"],
                key,
                first,
                last,
                str(rational) if rational is not None else None,
            ),
        )
db.executescript(
    """create view multiplicity as select pkey,count(*) n from native where pkey is not null group by pkey;
create view qualified as select r.*,
 json_array(disaster,state,case when code<>'' then 'CODE' else 'NAME' end,case when code<>'' then code when label<>'' then label else '__MISSING__' end) ck,
 case when pkey is null then 'MISSING_KEY' when n<>1 then 'DUPLICATE_KEY' when money is null then 'INVALID_AMOUNT' else 'ELIGIBLE' end reason
 from native r left join multiplicity using(pkey);"""
)
public = list(
    csv.DictReader(
        (root / "data/county_date_cells.csv").open(encoding="utf-8", newline="")
    )
)
expected = db.execute(
    """select disaster,ck,first,last,count(*),
 sum(reason='ELIGIBLE'),sum(reason='MISSING_KEY'),sum(reason='DUPLICATE_KEY'),sum(reason='INVALID_AMOUNT'),
 exact_sum(case when reason='ELIGIBLE' then money else null end)
 from qualified group by disaster,ck,first,last"""
).fetchall()
public_by_key = {
    (
        int(x["disaster"]),
        x["county_key"],
        x["first_obligation_day"],
        x["last_refresh_utc"],
    ): x
    for x in public
}
require(
    len(public_by_key) == len(public) == len(expected),
    "complete unique sufficient cells",
)
for row in expected:
    key = row[:4]
    require(key in public_by_key, "native county/date group retained")
    record = public_by_key[key]
    for name, number in zip(
        [
            "record_count",
            "eligible_money_records",
            "excluded_missing_key_records",
            "excluded_duplicate_key_records",
            "excluded_amount_records",
        ],
        row[4:9],
    ):
        require(int(record[name]) == number, "independent native count " + name)
    actual = (
        None
        if record["eligible_federal_usd"] == ""
        else Fraction(record["eligible_federal_usd"])
    )
    wanted = None if row[9] is None else Fraction(row[9])
    require(actual == wanted, "exact native rational amount")
catalog = json.loads((root / "data/county_catalog.json").read_bytes())
sql_catalog = db.execute(
    "select ck,disaster,state,code from qualified group by ck,disaster,state,code"
).fetchall()
require(len(catalog) == len(sql_catalog), "complete county catalog")
for item in catalog:
    rows = db.execute(
        "select distinct label,abbreviation from qualified where ck=?",
        (item["county_key"],),
    ).fetchall()
    require(
        item["county_names"] == sorted({x[0] or "__MISSING__" for x in rows}),
        "all source county names",
    )
    require(
        item["state_abbreviations"] == sorted({x[1] for x in rows}),
        "source state context",
    )
profile = json.loads((root / "data/projection_receipt.json").read_bytes())
require(profile["native_records"] == native_count == 17994, "native denominator")
require(
    sum(int(r["record_count"]) for r in public) == native_count, "public denominator"
)
for cohort in manifest["cohorts"]:
    count = db.execute(
        "select count(*) from native where disaster=?", (cohort["disaster"],)
    ).fetchone()[0]
    require(
        count == cohort["declared_count"] == cohort["captured_records"],
        "declared/current cohort coverage",
    )
receipt = dict(
    status="PASS",
    finite_conditions=checks,
    native_records=native_count,
    sufficient_cells=len(public),
    county_groups=len(catalog),
    method="Independent strict JSON tokens,dateutil calendar/UTC parser,SQLite grouping/key multiplicity and exact Fraction sums;no production projection imports.",
    source_sha256={
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in [
            "data/county_date_cells.csv",
            "data/county_catalog.json",
            "data/projection_receipt.json",
            "data/capture_manifest.json",
        ]
    },
    qualification="Current factual projection only;no prior county values,original publication or stability horizon established.",
)
(root / "data/native_verification.json").write_bytes(
    (json.dumps(receipt, indent=2) + "\n").encode()
)
print(
    json.dumps(
        {
            k: receipt[k]
            for k in [
                "status",
                "finite_conditions",
                "native_records",
                "sufficient_cells",
                "county_groups",
                "method",
            ]
        }
    )
)
