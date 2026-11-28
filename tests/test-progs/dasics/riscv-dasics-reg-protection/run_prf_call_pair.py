# SPDX-License-Identifier: BSD-3-Clause
"""Pair complete cold gate calls while varying the ROB or integer PRF size."""

import argparse
import configparser
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from measure import (
    REPO,
    TEST_DIR,
    require,
    write_json,
)
from prf_pressure_analyze import (
    analyze,
    save,
)
from prf_pressure_call_window import extract_call
from prf_pressure_pair_layout import inspect_pair
from run_prf_pressure import (
    cache_path,
    check_config,
    run_simulation,
)

COUNTS = (0, 12)
MODES = ("hw", "sw")
ROB_KEY = "system.cpu.numROBEntries"
INT_KEY = "system.cpu.numPhysIntRegs"


def model(path, elf, rob_entries, int_regs):
    check_config(path, rob_entries=rob_entries, int_regs=int_regs)
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    with path.open() as source:
        config.read_file(source)
    period = int(config[config["system.cpu"]["clk_domain"]]["clock"])
    # These two fields must identify this exact variant in *both* ROB runs.
    # Remove them before comparing alternate gate ELFs at a fixed ROB size.
    for section, key in (
        ("system.workload", "bootloader"),
        ("system.workload.semihosting", "cmd_line"),
    ):
        require(Path(config[section][key]) == elf, f"{path}: unexpected ELF")
        del config[section][key]
    return period, {
        f"{section}.{key}": value
        for section in config.sections()
        for key, value in config[section].items()
    }


def read_case(
    directory, elf, labels, k, mode, rob_entries, int_regs, archived
):
    simulation = json.loads((directory / "simulation.json").read_text())
    require(
        simulation["process_exit_code"] == 0
        and not simulation["timed_out"]
        and Path(simulation["command"][0])
        == REPO / "build/RISCV_DASICS/gem5.opt",
        f"{directory}: simulator identity or exit mismatch",
    )
    require(
        "[OK] DASICS register protection: PRF pressure"
        in (directory / "run.log").read_text().splitlines(),
        f"{directory}: missing successful guest checks",
    )
    path = directory / "m5out/config.ini"
    period, config = model(path, elf, rob_entries, int_regs)
    trace = directory / "m5out/debug.trace.gz"
    call = extract_call(
        trace, labels, labels["caller_transfer"], k, mode, period
    )
    cache = cache_path(
        trace, labels, call["load_send_tick"], call["load_response_tick"]
    )
    if not archived:
        write_json(directory / "cache-evidence.json", cache)
    if mode == "hw":
        if archived:
            pressure = json.loads((directory / "result.json").read_text())
        else:
            pressure = analyze(
                trace, elf, path, k, rob_entries=rob_entries, int_regs=int_regs
            )
            pressure.update(
                guest_exit_code=0,
                dram_command_ticks=cache["dram_command_ticks"],
            )
            save(pressure, directory)
        require(
            pressure["clobber"] == k and pressure["guest_exit_code"] == 0,
            f"{directory}: wrong hardware clobber workload",
        )
        for field in ("load_send_tick", "load_response_tick", "cold_addr"):
            require(
                call[field] == pressure[field], f"{directory}: {field} differs"
            )
    return call, config


def summarize(cases):
    rows = []
    for k in COUNTS:
        left, right = cases[f"sw-k{k}"], cases[f"hw-k{k}"]
        require(
            left["retired_instructions"] - right["retired_instructions"] == 34,
            f"k{k}: unexpected gate instruction delta",
        )
        saving = left["cycles"] - right["cycles"]
        rows.append(
            dict(
                clobbered=k,
                sw_cycles=left["cycles"],
                hw_cycles=right["cycles"],
                saved_cycles=saving,
                saved_percent=100 * saving / left["cycles"],
            )
        )
    return dict(
        status="PASS",
        cases=cases,
        calls=rows,
        savings_lost_cycles=rows[0]["saved_cycles"] - rows[1]["saved_cycles"],
    )


def collect(directories, elfs, symbols, rob_entries, archived, int_regs=128):
    cases = {}
    models = {}
    for (mode, k), directory in directories.items():
        tag = f"{mode}-k{k}"
        cases[tag], models[tag] = read_case(
            directory,
            elfs[mode][k],
            symbols[mode][k],
            k,
            mode,
            rob_entries,
            int_regs,
            directory in archived,
        )
    require(
        all(cfg == models["hw-k0"] for cfg in models.values()),
        f"ROB={rob_entries} configurations differ beyond the workload ELF",
    )
    return summarize(cases), models


def archive_directories(hw_batch, sw_batch):
    return {
        (mode, k): (
            hw_batch / f"k{k}" if mode == "hw" else sw_batch / f"sw-k{k}"
        )
        for mode in MODES
        for k in COUNTS
    }


def full_directories(batch):
    return {
        (mode, k): batch / f"{mode}-k{k}" for mode in MODES for k in COUNTS
    }


def compare_configs(previous, current, output, key, before, after):
    differences = {}
    for tag, cfg in current.items():
        old = previous[tag]
        differences[tag] = {
            key: {"before": old.get(key), "after": cfg.get(key)}
            for key in sorted(old.keys() | cfg.keys())
            if old.get(key) != cfg.get(key)
        }
    write_json(output, differences)
    require(
        all(
            diff == {key: {"before": str(before), "after": str(after)}}
            for diff in differences.values()
        ),
        f"Unexpected model change; see {output}",
    )


def pool_windows(directories, symbols, cases, int_regs):
    from prf_pressure_pool import pressure_window

    pools = {}
    for (mode, k), directory in directories.items():
        tag = f"{mode}-k{k}"
        pools[tag] = pressure_window(
            directory / "m5out/debug.trace.gz",
            symbols[mode][k],
            cases[tag],
            int_regs,
        )
        if mode == "hw":
            detail = json.loads((directory / "result.json").read_text())
            require(
                all(
                    pools[tag][field] == detail[field]
                    for field in (
                        "min_free",
                        "free_at_send",
                        "free_before_response",
                        "integer_rejects_in_wait",
                    )
                )
                and pools[tag]["younger_writes_in_wait"]
                == detail["younger_writes"]["in_wait"],
                f"{directory}: pool trace disagrees with hardware protection analysis",
            )
    return pools


def run(archive, batch, *, replay=False, rob96_pair=None, int128_pair=None):
    if archive is not None:
        require(
            json.loads((archive / "summary.json").read_text())["status"]
            == "PASS",
            "Expected a passing ROB=96 hardware batch",
        )
    build = TEST_DIR / "build/prf-pressure"
    elfs = {
        "hw": {k: build / f"k{k}.elf" for k in COUNTS},
        "sw": {k: build / "software" / f"k{k}.elf" for k in COUNTS},
    }
    symbols = inspect_pair(elfs["hw"], elfs["sw"])
    batch.mkdir(parents=True, exist_ok=True)
    int_regs = 160 if int128_pair is not None else 128
    if int128_pair is None and rob96_pair is None:
        rob_entries = 96
        directories = archive_directories(archive, batch)
        archived = {directories["hw", k] for k in COUNTS}
    else:
        rob_entries = 128
        if int128_pair is not None:
            old_dirs = full_directories(int128_pair)
            previous_batch, old_rob = int128_pair, 128
        else:
            old_dirs = archive_directories(archive, rob96_pair)
            previous_batch, old_rob = rob96_pair, 96
        baseline, old_configs = collect(
            old_dirs, elfs, symbols, old_rob, set(old_dirs.values())
        )
        saved = json.loads((previous_batch / "summary.json").read_text())
        require(
            all(value == saved.get(key) for key, value in baseline.items()),
            f"{previous_batch}: replay disagrees with archived complete call windows",
        )
        directories = full_directories(batch)
        archived = set()

    runs = {case: d for case, d in directories.items() if d not in archived}
    if not replay:
        require(
            all(not d.exists() for d in runs.values()),
            "Use fresh simulation directories",
        )
        with ThreadPoolExecutor(max_workers=len(runs)) as pool:
            jobs = [
                pool.submit(
                    run_simulation,
                    d,
                    elfs[mode][k],
                    rob_entries=rob_entries,
                    int_regs=int_regs,
                )
                for (mode, k), d in runs.items()
            ]
            for job in jobs:
                job.result()
    report, configs = collect(
        directories, elfs, symbols, rob_entries, archived, int_regs
    )
    if rob96_pair is not None:
        compare_configs(
            old_configs, configs, batch / "config-diff.json", ROB_KEY, 96, 128
        )
        report["rob_entries"] = rob_entries
        report["rob96_calls"] = baseline["calls"]
        report["rob96_savings_lost_cycles"] = baseline["savings_lost_cycles"]
        report["increase_in_savings_lost_cycles"] = (
            report["savings_lost_cycles"] - baseline["savings_lost_cycles"]
        )
    elif int128_pair is not None:
        compare_configs(
            old_configs, configs, batch / "config-diff.json", INT_KEY, 128, 160
        )
        report.update(
            rob_entries=rob_entries,
            num_phys_int_regs=int_regs,
            int128_calls=baseline["calls"],
            int128_savings_lost_cycles=baseline["savings_lost_cycles"],
            recovered_savings_cycles=baseline["savings_lost_cycles"]
            - report["savings_lost_cycles"],
            int128_pool_windows=pool_windows(
                old_dirs, symbols, baseline["cases"], 128
            ),
            pool_windows=pool_windows(
                directories, symbols, report["cases"], int_regs
            ),
        )
    write_json(batch / "summary.json", report)
    rows = report["calls"]
    print(
        f"PASS ROB={rob_entries}/INT={int_regs}: savings change from {rows[0]['saved_cycles']} "
        f"to {rows[1]['saved_cycles']} cycles.",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    reference = parser.add_mutually_exclusive_group(required=True)
    reference.add_argument(
        "--hw-batch",
        type=Path,
        help="Original ROB=96 hardware trace batch",
    )
    reference.add_argument(
        "--int128-pair",
        type=Path,
        help="Existing ROB=128, INT=128 comparison; run all four gates with INT=160",
    )
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument(
        "--rob96-pair",
        type=Path,
        help="Existing complete ROB=96 comparison; run all four gates with ROB=128",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Rebuild the comparison from existing traces",
    )
    args = parser.parse_args()
    if args.int128_pair and args.rob96_pair:
        parser.error("--rob96-pair requires --hw-batch")
    run(
        args.hw_batch.resolve() if args.hw_batch else None,
        args.batch.resolve(),
        replay=args.replay,
        rob96_pair=args.rob96_pair.resolve() if args.rob96_pair else None,
        int128_pair=args.int128_pair.resolve() if args.int128_pair else None,
    )
