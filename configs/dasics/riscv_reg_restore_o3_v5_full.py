# SPDX-License-Identifier: BSD-3-Clause

"""Measure register restoration from controlled cache levels on v5_full."""

import argparse
import configparser
import json
from copy import deepcopy
from pathlib import Path

from dasics_platform import (
    _print_config,
    _xbar,
    configure_cpu_caches,
    configure_memory,
)
from riscv_dasics_o3_v5_full import PROFILE
from riscv_reg_protection_o3_v5_full import text_statistics_paths

import m5
from m5.objects import (
    AddrRange,
    Process,
    Root,
    SEWorkload,
    SrcClockDomain,
    System,
    SystemXBar,
    VoltageDomain,
)


def snapshot_sample_statistics(source, destination, index):
    """Freeze a sample before later preparation changes global statistics."""
    label = f"Register restore sample {index}"
    # Text::end() flushes the visitor before m5.stats.dump() returns.
    m5.stats.dump(message=label)
    content = source.read_text()
    begin = content.rfind(
        f"---------- Begin Simulation Statistics : {label} ----------"
    )
    end = content.find("---------- End Simulation Statistics", begin)
    if begin < 0 or end < 0:
        raise RuntimeError(f"Incomplete statistics for sample {index}")
    end = content.find("\n", end)
    destination.write_text(
        content[begin:] if end < 0 else content[begin : end + 1]
    )


def prepare_cache_state(system, source):
    """Drain at the guest guard, then prepare data caches synchronously."""
    before = int(system.cpu.totalInsts())
    m5.drain()
    committed = int(system.cpu.totalInsts()) - before
    # PREP is followed immediately by a serializing CSR guard. Drain may
    # commit PREP or the guard, but must not consume START or a target load.
    if not 0 <= committed <= 1:
        raise RuntimeError(
            f"Drain crossed the preparation guard: {committed} instructions"
        )
    caches = [system.cpu.dcache, *system.l2, *system.l3]
    # Functional writes preserve dirty data without timing requests. They
    # update existing lower-level blocks; they do not establish L2 residency.
    for cache in caches:
        cache.memWriteback()
    invalidate = caches if source == "dram" else caches[:1]
    if source != "l1":
        for cache in invalidate:
            cache.memInvalidate()
    return committed


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", choices=("l1", "l2", "dram"), required=True
    )
    parser.add_argument(
        "--vlen", type=int, choices=(128, 256, 512, 1024), default=128
    )
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=100_000_000_000,
        help="Total simulated tick budget, including cache preparation",
    )
    parser.add_argument(
        "binary", type=Path, help="Static RV64 restore benchmark"
    )
    parser.add_argument("program_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    binary = args.binary.resolve()
    outdir = Path(m5.options.outdir).resolve()
    if not binary.is_file():
        parser.error(f"Binary not found: {binary}")
    if not 0 < args.max_ticks <= m5.MaxTick:
        parser.error(
            "--max-ticks must be positive and no greater than MaxTick"
        )
    if len(args.program_args) != 3 or args.program_args[0] not in (
        "B",
        "G",
        "F",
        "V",
    ):
        parser.error("Guest arguments must be GROUP SAMPLES EXPECTED_VLEN")
    try:
        samples = int(args.program_args[1])
        expected_vlen = int(args.program_args[2])
    except ValueError:
        parser.error("SAMPLES and EXPECTED_VLEN must be integers")
    if samples <= 0 or expected_vlen != args.vlen:
        parser.error(
            "SAMPLES must be positive and EXPECTED_VLEN must match --vlen"
        )
    statistics = list(text_statistics_paths(outdir))
    if not statistics:
        parser.error("Measurement requires a text --stats-file output")
    for filename in statistics:
        if filename.parent.resolve() == outdir and filename.name.startswith(
            "sample-"
        ):
            parser.error(
                "Global statistics output must differ from sample files"
            )
    result_path = outdir / "restore.json"
    result_path.unlink(missing_ok=True)
    for index in range(samples):
        (outdir / f"sample-{index:03d}-stats.txt").unlink(missing_ok=True)

    profile = deepcopy(PROFILE)
    for level in ("l1d", "l2", "l3"):
        profile["caches"][level]["prefetch"] = "none"
    system = System(mem_mode="timing", cache_line_size=64)
    system.mem_ranges = [AddrRange(0x80000000, size="8GiB")]
    system.voltage_domain = VoltageDomain(voltage="1V")
    system.clk_domain = SrcClockDomain(
        clock="2GHz", voltage_domain=system.voltage_domain
    )
    system.membus = _xbar(SystemXBar)
    system.system_port = system.membus.cpu_side_ports
    system.workload = SEWorkload.init_compatible(str(binary))
    configure_cpu_caches(system, profile)
    configure_memory(system)
    system.cpu.isa[0].vlen = args.vlen
    system.exit_on_work_items = True
    system.cpu.workload = Process(
        executable=str(binary),
        cmd=[str(binary), *args.program_args],
        cwd=str(outdir),
        output=str(args.stdout.resolve()),
        errout=str(args.stderr.resolve()),
        env=["LC_ALL=C"],
    )
    root = Root(full_system=False, system=system, sim_quantum=0)
    m5.instantiate()
    _print_config(profile)
    config = configparser.ConfigParser(interpolation=None)
    config.read(outdir / m5.options.dump_config)
    clock = config["system.cpu"]["clk_domain"]
    period = int(config[clock]["clock"].split()[0])
    frequency = int(m5.ticks.fromSeconds(1.0))
    result = {
        "status": "FAIL",
        "source": args.source,
        "vlen_bits": args.vlen,
        "program_args": args.program_args,
        "sim_frequency": frequency,
        "cpu_frequency_hz": frequency / period,
        "cache_line_bytes": int(config["system"]["cache_line_size"]),
        "guest_exit_code": None,
        "exit_cause": None,
        "samples": [],
    }
    print(
        f"Restore source: {args.source}; data prefetchers: disabled; "
        f"samples: {samples}",
        flush=True,
    )
    deadline = min(m5.MaxTick, m5.curTick() + args.max_ticks)
    phase = "prepare"
    current = None
    try:
        while m5.curTick() < deadline:
            event = m5.simulate(deadline - m5.curTick())
            cause = event.getCause()
            code = event.getCode()
            result["exit_cause"] = cause
            if cause == "workbegin" and code == 1:
                if phase != "prepare" or len(result["samples"]) >= samples:
                    raise RuntimeError("Unexpected PREP marker")
                current = {
                    "index": len(result["samples"]),
                    "prepare_tick": m5.curTick(),
                    "start_tick": None,
                    "end_tick": None,
                    "clock_period_ticks": period,
                    "elapsed_cycles": None,
                    "stats_file": None,
                }
                result["samples"].append(current)
                current["drain_committed_instructions"] = prepare_cache_state(
                    system, args.source
                )
                current["prepared_tick"] = m5.curTick()
                phase = "start"
            elif cause == "workbegin" and code == 2:
                if phase != "start":
                    raise RuntimeError("Unexpected START marker")
                current["start_tick"] = m5.curTick()
                m5.stats.reset()
                phase = "end"
            elif cause == "workend" and code == 2:
                if phase != "end":
                    raise RuntimeError("Unexpected END marker")
                current["end_tick"] = m5.curTick()
                if current["end_tick"] <= current["start_tick"]:
                    raise RuntimeError("The restore ROI has no elapsed time")
                current["elapsed_cycles"] = (
                    current["end_tick"] - current["start_tick"]
                ) / period
                filename = f"sample-{current['index']:03d}-stats.txt"
                snapshot_sample_statistics(
                    statistics[0], outdir / filename, current["index"]
                )
                current["stats_file"] = filename
                phase = "prepare"
            elif cause == "exiting with last active thread context":
                result["guest_exit_code"] = code
                if code != 0:
                    raise RuntimeError(
                        "The guest exited with a nonzero status"
                    )
                if phase != "prepare" or len(result["samples"]) != samples:
                    raise RuntimeError(
                        "The guest did not complete all restore samples"
                    )
                result["status"] = "PASS"
                break
            else:
                raise RuntimeError(
                    f"Unexpected simulation exit: {cause}, code={code}"
                )
        else:
            raise RuntimeError(
                "The total simulation tick budget was exhausted"
            )
    except Exception as error:
        result["error"] = str(error)
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    completed = sum(s["end_tick"] is not None for s in result["samples"])
    print(
        f"Register restore: {result['status']}; "
        f"completed samples: {completed}",
        flush=True,
    )
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__m5_main__":
    run()
