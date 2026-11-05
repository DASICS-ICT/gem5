#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Plot paired register-protection costs from pressure.py summary records."""

import argparse
import csv
import json
import math
import os
import statistics
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

WORKING_SETS = (1024, 32768, 65536, 131072, 262144)
METRICS = (
    "baseline_cycles_per_call",
    "guard_cycles_per_call",
    "incremental_cycles_per_call",
    "relative_overhead_percent",
)


def read_rows(source, iterations):
    with source.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        all_rows = list(reader)
    rows = [row for row in all_rows if int(row["iterations"]) == iterations]
    expected = {(size, seed) for size in WORKING_SETS for seed in (0, 1, 2)}
    actual = [(int(row["working_set"]), int(row["seed"])) for row in rows]
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("Expected five working sets and seeds 0, 1, 2")
    for row in rows:
        if row["status"] != "PASS":
            raise ValueError(f"Cannot plot failed measurement: {row}")
        baseline = float(row["baseline_cycles"])
        guard = float(row["guard_cycles"])
        values = (
            baseline / iterations,
            guard / iterations,
            (guard - baseline) / iterations,
            100 * (guard - baseline) / baseline,
        )
        for metric, value in zip(METRICS, values):
            if not math.isclose(float(row[metric]), value, rel_tol=1e-10):
                raise ValueError(f"Inconsistent normalization: {metric}")
    rows.sort(key=lambda row: (int(row["working_set"]), int(row["seed"])))
    return fields, rows, len(all_rows) - len(rows)


def draw_metric(axis, rows, metric, label, color, marker, linestyle):
    groups = [
        [float(row[metric]) for row in rows if int(row["working_set"]) == size]
        for size in WORKING_SETS
    ]
    medians = [statistics.median(group) for group in groups]
    errors = [
        [median - min(group) for median, group in zip(medians, groups)],
        [max(group) - median for median, group in zip(medians, groups)],
    ]
    axis.errorbar(
        [size / 1024 for size in WORKING_SETS],
        medians,
        yerr=errors,
        label=label,
        color=color,
        marker=marker,
        markerfacecolor="white",
        markersize=6,
        linestyle=linestyle,
        linewidth=1.6,
        capsize=4,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=64)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    fields, rows, excluded = read_rows(args.summary, args.iterations)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    names = ("pressure.png", "pressure.pdf", "raw-data.csv", "provenance.json")
    if any((args.output_dir / name).exists() for name in names):
        parser.error("Output already exists; select a new output directory")

    matplotlib.use("Agg")
    with plt.rc_context(
        {
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    ):
        figure, axes = plt.subplots(
            3, 1, figsize=(9, 9), sharex=True, layout="constrained"
        )
        draw_metric(axes[0], rows, METRICS[0], "B", "#0072B2", "o", "-")
        draw_metric(axes[0], rows, METRICS[1], "GF_SCR", "#A34800", "s", "--")
        draw_metric(
            axes[1], rows, METRICS[2], "GF_SCR - B", "#6A3D9A", "D", "-"
        )
        draw_metric(
            axes[2],
            rows,
            METRICS[3],
            "100 (GF_SCR - B) / B",
            "#6A3D9A",
            "D",
            "-",
        )
        titles = (
            "(a) Total call cost",
            "(b) Added protection cost",
            "(c) Relative protection overhead",
        )
        labels = ("Cycles / call", "Added cycles / call", "Overhead (%)")
        for axis, title, label in zip(axes, titles, labels):
            axis.set(title=title, ylabel=label, xscale="log")
            axis.set_xscale("log", base=2)
            axis.axvline(64, color="#666666", linestyle=":", linewidth=1)
            axis.grid(axis="y", color="#DDDDDD", linewidth=0.7)
            axis.set_ylim(bottom=min(0, axis.get_ylim()[0]))
            axis.legend(loc="upper left", frameon=False)
        axes[0].yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        axes[0].text(
            64,
            0.97,
            "  L1D: 64 KiB",
            transform=axes[0].get_xaxis_transform(),
            va="top",
            color="#444444",
        )
        axes[2].set_xticks([size / 1024 for size in WORKING_SETS])
        axes[2].xaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
        axes[2].set_xlabel("Active working set (KiB; log2 scale)")
        figure.suptitle(
            "Register protection under dependent-load cache pressure\n"
            f"v5_full | 19 GPR + 24 FPR | 4096 loads/call | N = {args.iterations}"
        )
        figure.supxlabel(
            "Points: median of seeds 0, 1, 2; whiskers: min-max across seeds.\n"
            "Lines connect measured settings only; no smoothing. "
            "Ranges are not confidence intervals.",
            fontsize=9,
        )
        figure.savefig(args.output_dir / "pressure.png", dpi=200)
        figure.savefig(args.output_dir / "pressure.pdf")
        plt.close(figure)

    with (args.output_dir / "raw-data.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    provenance = {
        "source": os.path.relpath(args.summary, args.output_dir),
        "filter": {"iterations": args.iterations},
        "selected_rows": len(rows),
        "other_iteration_rows": excluded,
        "failed_rows_excluded": 0,
        "seeds": [0, 1, 2],
        "sample_unit": "deterministic pointer-chain permutation",
        "estimator": "median of each plotted metric across seeds",
        "interval": "minimum to maximum across seeds; not a confidence interval",
        "normalization": {
            "cycles_per_call": "total ROI cycles / iterations",
            "incremental_cycles_per_call": "(GF_SCR cycles - B cycles) / iterations",
            "relative_overhead_percent": "100 * (GF_SCR cycles - B cycles) / B cycles",
        },
        "x_axis": "working_set / 1024 KiB, log2 scale",
        "missing_data": "reject incomplete five-working-set, three-seed matrix",
        "smoothing": "none; lines connect observed settings",
        "figure_inches": [9, 9],
        "png_dpi": 200,
        "matplotlib": matplotlib.__version__,
        "description": (
            "Three aligned panels show total call cycles, added protection "
            "cycles, and relative overhead versus the callee working set. "
            "A vertical dotted line marks the configured 64 KiB L1D capacity. "
            "All selected paired observations are preserved in raw-data.csv."
        ),
    }
    (args.output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )
    print(
        f"Wrote {len(rows)} paired observations and figure to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
