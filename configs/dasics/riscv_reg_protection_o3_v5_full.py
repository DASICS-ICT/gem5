# SPDX-License-Identifier: BSD-3-Clause

"""Measure software register protection on the fixed v5_full O3 model."""

import argparse
import configparser
import json
from pathlib import Path
from urllib.parse import urlsplit

from dasics_platform import (
    _print_config,
    _xbar,
    configure_cpu_caches,
    configure_memory,
)
from riscv_dasics_o3_v5_full import PROFILE

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


def text_statistics_paths(outdir):
    """Locate existing text visitors without changing global outputs."""
    for output in m5.options.stats_file:
        parsed = urlsplit(output)
        if parsed.scheme in ("", "text"):
            filename = Path(parsed.netloc + parsed.path)
            yield filename if filename.is_absolute() else outdir / filename


def snapshot_roi_statistics(source, destination):
    """Freeze the ROI block before guest cleanup changes statistics."""
    # Text::end() flushes the stream before m5.stats.dump() returns.
    m5.stats.dump(message="Register protection ROI")
    content = source.read_text()
    begin = content.rfind(
        "---------- Begin Simulation Statistics : Register protection ROI "
        "----------"
    )
    end = content.find("---------- End Simulation Statistics", begin)
    if begin < 0 or end < 0:
        raise RuntimeError("The ROI statistics block is incomplete")
    end = content.find("\n", end)
    destination.write_text(
        content[begin:] if end < 0 else content[begin : end + 1]
    )


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vlen", type=int, choices=(128, 256, 512, 1024), default=128
    )
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=10_000_000_000,
        help="Total simulated tick budget, including warmup and verification",
    )
    parser.add_argument(
        "binary", type=Path, help="Static RV64 Linux benchmark"
    )
    parser.add_argument("program_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    binary = args.binary.resolve()
    outdir = Path(m5.options.outdir).resolve()
    workdir = args.workdir.resolve() if args.workdir else outdir
    if not binary.is_file():
        parser.error(f"Binary not found: {binary}")
    if not workdir.is_dir():
        parser.error(f"Work directory not found: {workdir}")
    if not 0 < args.max_ticks <= m5.MaxTick:
        parser.error(
            "--max-ticks must be positive and no greater than MaxTick"
        )
    if not args.program_args or args.program_args[0] not in (
        "verify",
        "measure",
    ):
        parser.error("The guest command must start with verify or measure")
    mode = args.program_args[0]
    stats_paths = list(text_statistics_paths(outdir))
    roi_stats = outdir / "roi-stats.txt"
    roi_result = outdir / "roi.json"
    if mode == "measure" and not stats_paths:
        parser.error("Measurement requires a text --stats-file output")
    if any(filename.resolve() == roi_stats for filename in stats_paths):
        parser.error(
            "The global statistics output must differ from roi-stats.txt"
        )
    # A failed run must not expose a previous run's ROI as current evidence.
    roi_stats.unlink(missing_ok=True)
    roi_result.unlink(missing_ok=True)

    system = System(mem_mode="timing", cache_line_size=64)
    system.mem_ranges = [AddrRange(0x80000000, size="8GiB")]
    system.voltage_domain = VoltageDomain(voltage="1V")
    system.clk_domain = SrcClockDomain(
        clock="2GHz", voltage_domain=system.voltage_domain
    )
    system.membus = _xbar(SystemXBar)
    system.system_port = system.membus.cpu_side_ports
    system.workload = SEWorkload.init_compatible(str(binary))
    configure_cpu_caches(system, PROFILE)
    configure_memory(system)
    system.cpu.isa[0].vlen = args.vlen
    system.exit_on_work_items = True
    system.cpu.workload = Process(
        executable=str(binary),
        cmd=[str(binary), *args.program_args],
        cwd=str(workdir),
        output=str(args.stdout.resolve()),
        errout=str(args.stderr.resolve()),
        env=["LC_ALL=C"],
    )
    root = Root(full_system=False, system=system)
    m5.instantiate()
    _print_config(PROFILE)
    config = configparser.ConfigParser(interpolation=None)
    config.read(outdir / m5.options.dump_config)
    clock = config["system.cpu"]["clk_domain"]
    period = int(config[clock]["clock"].split()[0])
    result = {
        "status": "FAIL",
        "mode": mode,
        "vlen_bits": args.vlen,
        "program_args": args.program_args,
        "start_tick": None,
        "end_tick": None,
        "clock_period_ticks": period,
        "elapsed_cycles": None,
        "guest_exit_code": None,
        "exit_cause": None,
    }
    deadline = min(m5.MaxTick, m5.curTick() + args.max_ticks)
    while m5.curTick() < deadline:
        event = m5.simulate(deadline - m5.curTick())
        cause = event.getCause()
        code = event.getCode()
        result["exit_cause"] = cause
        if cause == "workbegin":
            if mode != "measure" or result["start_tick"] is not None:
                result["error"] = "Unexpected or duplicate workbegin"
                break
            result["start_tick"] = m5.curTick()
            m5.stats.reset()
        elif cause == "workend":
            if (
                mode != "measure"
                or result["start_tick"] is None
                or result["end_tick"] is not None
            ):
                result["error"] = "Unexpected or duplicate workend"
                break
            result["end_tick"] = m5.curTick()
            result["elapsed_cycles"] = (
                result["end_tick"] - result["start_tick"]
            ) / period
            snapshot_roi_statistics(stats_paths[0], roi_stats)
        elif cause == "exiting with last active thread context":
            result["guest_exit_code"] = code
            if code != 0:
                result["error"] = "The guest exited with a nonzero status"
            elif mode == "measure" and result["end_tick"] is None:
                result["error"] = "The measurement has no complete ROI"
            else:
                result["status"] = "PASS"
            break
        else:
            result["error"] = f"Unexpected simulation exit: {cause}"
            break
    else:
        result["error"] = "The total simulation tick budget was exhausted"
    roi_result.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"Register protection {mode}: {result['status']}; "
        f"exit cause: {result['exit_cause']}; "
        f"ROI elapsed cycles: {result['elapsed_cycles']}",
        flush=True,
    )
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__m5_main__":
    run()
