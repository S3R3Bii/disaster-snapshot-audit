"""Original charts of fixed current-record probes and unresolved source geography."""

from pathlib import Path
from fractions import Fraction
import csv, json, hashlib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "figures"
out.mkdir(exist_ok=True)


def rows(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "svg.fonttype": "none",
        "svg.hashsalt": "disaster-snapshot-audit-v1",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.edgecolor": "#71818a",
        "text.color": "#172b36",
        "axes.labelcolor": "#172b36",
    }
)
blue = "#176b93"
gold = "#a65e00"
gray = "#71808a"
manifest = {}


def finish(fig, name, artists):
    for extension in ["svg", "png", "pdf"]:
        path = out / (name + "." + extension)
        metadata = (
            {"Date": None}
            if extension == "svg"
            else (
                {"CreationDate": None, "ModDate": None}
                if extension == "pdf"
                else {"Software": "Matplotlib"}
            )
        )
        fig.savefig(path, dpi=160, facecolor="white", metadata=metadata)
        if extension == "svg":
            path.write_bytes(
                b"\n".join(line.rstrip() for line in path.read_bytes().splitlines())
                + b"\n"
            )
    manifest[name] = dict(
        artists=artists,
        sha256={
            e: hashlib.sha256((out / (name + "." + e)).read_bytes()).hexdigest()
            for e in ["svg", "png", "pdf"]
        },
    )
    plt.close(fig)


metrics = [r for r in rows("results/probe_metrics.csv") if r["level"] == "DISASTER"]
totals = {
    r["disaster"]: r
    for r in rows("results/current_totals.csv")
    if r["level"] == "DISASTER"
}
cutoffs = json.loads((ROOT / "data/source_contract.json").read_bytes())["cutoffs"]
for name, field, title, subtitle in [
    (
        "current_record_probes",
        "record_fraction",
        "Current-record filters produce different slices",
        "Neither selector reconstructs historical county values.",
    ),
    (
        "current_dollar_probes",
        "reported_dollar_fraction",
        "Current reported dollars are not past totals",
        "Selected fractions use today's eligible grant field, not amounts observed at the earlier cutoffs.",
    ),
]:
    fig = plt.figure(figsize=(9.4, 4.5))
    artists = []
    for index, disaster in enumerate(["4332", "4339"]):
        ax = fig.add_axes([0.09 if index == 0 else 0.57, 0.28, 0.38, 0.50])
        ax.set_xlim(-0.6, 4.6)
        ax.set_ylim(0, 110)
        for selector, shift, color in [
            ("firstObligationDate", -0.16, gold),
            ("lastRefresh", 0.16, blue),
        ]:
            series = [
                next(
                    r
                    for r in metrics
                    if r["disaster"] == disaster
                    and r["cutoff"] == cut
                    and r["selector"] == selector
                )
                for cut in cutoffs
            ]
            for j, row in enumerate(series):
                value = float(Fraction(row[field]) * 100)
                assert (
                    0 <= value <= 100
                ), "fixed source percentage outside plotted support"
                bar = ax.bar([j + shift], [value], width=0.28, color=color, zorder=3)[0]
                key = name + "-" + disaster + "-" + selector + "-" + str(j)
                bar.set_gid(key)
                query = {
                    k: row[k]
                    for k in ["level", "disaster", "group_key", "cutoff", "selector"]
                }
                artists.append(
                    dict(
                        id=key,
                        kind="percent_bar",
                        query=query,
                        field=field,
                        artist_value=float(bar.get_height()),
                        panel=index,
                        category=j,
                        selector=selector,
                    )
                )
                if value == 0:
                    ax.text(
                        j + shift,
                        1.1,
                        "0",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                        color=color,
                    )
                elif j == 0 and selector == "firstObligationDate":
                    ax.text(
                        j + shift,
                        value + 1.5,
                        f"{value:.2f}%",
                        ha="center",
                        fontsize=8.5,
                    )
        ax.set_xticks(range(5), ["2018", "2020", "2022", "2024", "Oct 30\n2026"])
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.grid(axis="y", alpha=0.15)
        ax.set_axisbelow(True)
        ax.set_ylabel(
            (
                "Current records selected (%)"
                if field == "record_fraction"
                else "Current eligible dollars selected (%)"
            ),
            fontsize=9,
        )
        total = totals[disaster]
        context = (
            f"n = {int(total['current_records']):,}"
            if field == "record_fraction"
            else "current field = $"
            + f"{float(total['current_reported_federal_usd'])/1e9:.2f}bn"
        )
        ax.set_title(
            disaster + (" · TX" if index == 0 else " · PR") + " | " + context,
            fontsize=11,
            fontweight="bold",
        )
    fig.text(0.04, 0.96, title, fontsize=14, fontweight="bold", va="top")
    fig.text(0.04, 0.872, subtitle, fontsize=9)
    fig.text(
        0.5,
        0.172,
        "Authored cutoff probes; year labels mean December 31",
        ha="center",
        fontsize=9,
    )
    fig.legend(
        handles=[
            Patch(color=gold, label="First obligation (source calendar date)"),
            Patch(color=blue, label="lastRefresh (aware store timestamp)"),
        ],
        loc="lower center",
        bbox_to_anchor=(0.5, 0.064),
        ncol=2,
        frameon=False,
        fontsize=9,
    )
    footer = "Source: OpenFEMA v2, 31 Oct 2026 UTC. A zero is an empty current-record slice, not zero past funding."
    if field == "reported_dollar_fraction":
        footer = "Reported grant funding available to grantee; not cash payments or official federal financial reporting."
    fig.text(0.04, 0.018, footer, fontsize=8.5)
    finish(fig, name, artists)
catalog = json.loads((ROOT / "data/county_catalog.json").read_bytes())
total = len(catalog)
three = sum(len(x["county_code"]) == 3 and x["county_code"].isdigit() for x in catalog)
mixed = sum(
    any(s.lower() == "statewide" for s in x["county_names"])
    and len(x["county_names"]) > 1
    for x in catalog
)
values = [three, total - three, mixed, total - mixed]
labels = [
    "Three-digit source code",
    "Other source code format",
    "Named county + Statewide",
    "Other label sets",
]
fig = plt.figure(figsize=(9.4, 3.8))
ax = fig.add_axes([0.36, 0.24, 0.58, 0.58])
ax.set_xlim(0, 132)
ax.set_ylim(4.7, -0.7)
artists = []
for y, key, label, value, color in zip(
    [0, 1, 3, 4],
    ["three_digits", "other_format", "mixed_statewide", "other_labels"],
    labels,
    values,
    [blue, gray, gold, gray],
):
    bar = ax.barh([y], [value], height=0.55, color=color)[0]
    bar.set_gid(key)
    ax.text(value + 1.2, y, str(value), va="center", fontweight="bold")
    artists.append(
        dict(id=key, kind="count_bar", artist_value=float(bar.get_width()), row=y)
    )
ax.axhline(2, color="#b8c3c8", lw=0.7)
ax.set_yticks([0, 1, 3, 4], labels)
ax.set_xticks([0, 33, 66, 99, 132])
ax.set_xlabel("Raw source county-code/name groups (n = 132)")
ax.grid(axis="x", alpha=0.15)
ax.set_axisbelow(True)
fig.text(
    0.04,
    0.96,
    "Source county codes need geographic review",
    fontsize=14,
    fontweight="bold",
    va="top",
)
fig.text(
    0.04,
    0.865,
    "County means applicant location. These groups are not verified damaged-worksite counties.",
    fontsize=9,
)
fig.text(
    0.04,
    0.035,
    "Two separate partitions of 132 groups. Code format is not geographic validation; mixed labels remain unresolved.",
    fontsize=8.5,
)
finish(fig, "source_county_flags", artists)
(out / "manifest.json").write_bytes(
    (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
)
print(
    json.dumps(
        dict(
            status="CREATED",
            figures=3,
            source_bound_bars=sum(len(x["artists"]) for x in manifest.values()),
            assets=9,
        )
    )
)
