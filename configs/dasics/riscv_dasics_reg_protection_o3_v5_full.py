# Copyright (c) 2026 The Regents of the University of California
# Copyright (c) 2026 zengsy99
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Measure DASICS register protection on the fixed v5_full FS platform."""

import argparse
import configparser
import json
from pathlib import Path

from dasics_platform import (
    _print_config,
    _xbar,
    configure_cpu_caches,
    configure_memory,
)
from riscv_dasics_o3_v5_full import PROFILE
from riscv_reg_protection_o3_v5_full import (
    snapshot_roi_statistics,
    text_statistics_paths,
)

import m5
from m5.objects import (
    AddrRange,
    Bridge,
    HiFive,
    IOXBar,
    PMAChecker,
    RiscvBareMetal,
    RiscvRTC,
    RiscvSemihosting,
    RiscvSystem,
    Root,
    SimpleMemory,
    SrcClockDomain,
    SystemXBar,
    VoltageDomain,
)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="RV64 bare-metal ROI ELF")
    parser.add_argument(
        "--mode",
        choices=(
            "boundary",
            "save",
            "restore",
            "software",
            "proreg",
            "standard_ref",
            "standard_guard",
            "variant_ref",
            "variant_guard",
        ),
        required=True,
    )
    parser.add_argument(
        "--workload", choices=("empty", "compute"), required=True
    )
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument("--clobber-count", type=int, choices=(0, 1, 6, 12))
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=10_000_000_000,
        help="Total simulated tick budget, including warmup and verification",
    )
    parser.add_argument(
        "--vlen", type=int, choices=(128, 256, 512, 1024), default=128
    )
    args = parser.parse_args()
    binary = args.binary.resolve()
    outdir = Path(m5.options.outdir).resolve()
    roi_stats = outdir / "roi-stats.txt"
    roi_result = outdir / "roi.json"
    # A failed run must not expose an earlier run's ROI as current evidence.
    roi_stats.unlink(missing_ok=True)
    roi_result.unlink(missing_ok=True)
    if not binary.is_file():
        parser.error(f"Binary not found: {binary}")
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    if not 0 < args.max_ticks <= m5.MaxTick:
        parser.error(
            "--max-ticks must be positive and no greater than MaxTick"
        )
    stats_paths = list(text_statistics_paths(outdir))
    if not stats_paths:
        parser.error("Measurement requires a text --stats-file output")
    if any(filename.resolve() == roi_stats for filename in stats_paths):
        parser.error(
            "The global statistics output must differ from roi-stats.txt"
        )

    # Keep the existing hand-configured O3 hierarchy and bare-metal platform.
    # Sv39 mappings and DASICS state are initialized by the guest itself.
    system = RiscvSystem(mem_mode="timing", cache_line_size=64)
    system.mem_ranges = [AddrRange(0x80000000, size="8GiB")]
    system.voltage_domain = VoltageDomain(voltage="1V")
    system.clk_domain = SrcClockDomain(
        clock="2GHz", voltage_domain=system.voltage_domain
    )
    system.workload = RiscvBareMetal(
        bootloader=str(binary),
        semihosting=RiscvSemihosting(cmd_line=str(binary)),
    )
    system.exit_on_work_items = True
    system.iobus = IOXBar()
    system.membus = _xbar(SystemXBar)
    system.system_port = system.membus.cpu_side_ports
    system.platform = HiFive()
    system.platform.rtc = RiscvRTC(frequency="10MHz")
    system.platform.clint.int_pin = system.platform.rtc.int_pin
    system.platform.pci_host.internal_connect()
    system.platform.pci_host.connect_upper_bus(system.iobus, True)
    system.platform.attachOnChipIO(system.membus)
    system.platform.attachOffChipIO(system.iobus)
    system.platform.attachPlic()
    system.platform.setNumCores(1)
    system.bridge = Bridge(delay="50ns")
    system.bridge.mem_side_port = system.iobus.cpu_side_ports
    system.bridge.cpu_side_port = system.membus.mem_side_ports
    system.bridge.ranges = system.platform._off_chip_ranges()
    system.iobridge = Bridge(delay="50ns", ranges=system.mem_ranges)
    system.iobridge.cpu_side_port = system.iobus.mem_side_ports
    system.iobridge.mem_side_port = system.membus.cpu_side_ports
    configure_cpu_caches(system, PROFILE)
    system.cpu.isa[0].vlen = args.vlen
    system.cpu.mmu.pma_checker = PMAChecker(
        uncacheable=[
            *system.platform._on_chip_ranges(),
            *system.platform._off_chip_ranges(),
        ]
    )
    system.reset_mem = SimpleMemory(
        range=AddrRange(0x7FFFF000, size="4KiB"),
        latency="1ns",
        latency_dist="None",
        bandwidth="32GiB/s",
    )
    system.reset_mem.port = system.membus.mem_side_ports
    configure_memory(system)
    root = Root(full_system=True, system=system)
    m5.instantiate()
    _print_config(PROFILE)
    config = configparser.ConfigParser(interpolation=None)
    config.read(outdir / m5.options.dump_config)
    clock = config["system.cpu"]["clk_domain"]
    period = int(config[clock]["clock"].split()[0])
    # These labels describe the selected ELF; they do not alter CPU parameters.
    result = {
        "status": "FAIL",
        "mode": args.mode,
        "vlen": args.vlen,
        "workload": args.workload,
        "iterations": args.iterations,
        "warmup": 128,
        "start_tick": None,
        "end_tick": None,
        "clock_period_ticks": period,
        "elapsed_cycles": None,
        "guest_exit_code": None,
        "exit_cause": None,
        "error": None,
    }
    if args.clobber_count is not None:
        result["clobber_count"] = args.clobber_count
    deadline = min(m5.MaxTick, m5.curTick() + args.max_ticks)
    try:
        while m5.curTick() < deadline:
            event = m5.simulate(deadline - m5.curTick())
            cause = event.getCause()
            code = event.getCode()
            result["exit_cause"] = cause
            if cause == "workbegin":
                if code != 0 or result["start_tick"] is not None:
                    result["error"] = "Unexpected or duplicate workbegin"
                    break
                result["start_tick"] = m5.curTick()
                m5.stats.reset()
            elif cause == "workend":
                if (
                    code != 0
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
            elif cause == "semi:ADP_Stopped_ApplicationExit":
                result["guest_exit_code"] = code
                if code != 0:
                    result["error"] = "The guest exited with a nonzero status"
                elif result["end_tick"] is None:
                    result["error"] = "The measurement has no complete ROI"
                else:
                    result["status"] = "PASS"
                break
            else:
                result["error"] = (
                    "The total simulation tick budget was exhausted"
                    if m5.curTick() >= deadline
                    else f"Unexpected simulation exit: {cause}"
                )
                break
        else:
            result["error"] = "The total simulation tick budget was exhausted"
    except (OSError, RuntimeError) as error:
        result["error"] = str(error)
    roi_result.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"DASICS register protection {args.mode}/{args.workload}: "
        f"{result['status']}; exit cause: {result['exit_cause']}; "
        f"ROI elapsed cycles: {result['elapsed_cycles']}",
        flush=True,
    )
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__m5_main__":
    run()
