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

"""Run a static RV64 Linux workload on a selected O3 reference model."""

import argparse
import json
from pathlib import Path

from dasics_platform import (
    _print_config,
    _xbar,
    configure_cpu_caches,
    configure_memory,
)

import m5
from m5 import debug
from m5.objects import (
    AddrRange,
    PcCountTracker,
    PcCountTrackerManager,
    Process,
    Root,
    SEWorkload,
    SrcClockDomain,
    System,
    SystemXBar,
    VoltageDomain,
)
from m5.params import PcCountPair


def _retired_pc(value):
    name, _, address = value.partition("=")
    try:
        pc = int(address, 0)
    except ValueError:
        raise argparse.ArgumentTypeError("expected NAME=ADDRESS") from None
    if not name or not 0 <= pc < 2**64 or pc % 2:
        raise argparse.ArgumentTypeError(
            "expected NAME and an RV64 instruction address"
        )
    return name, pc


def run_model(profile, *, dasics_init=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--stdin", type=Path)
    parser.add_argument("--max-ticks", type=int, default=m5.MaxTick)
    if dasics_init:
        parser.add_argument(
            "--retired-pc",
            action="append",
            type=_retired_pc,
            default=[],
            metavar="NAME=ADDRESS",
            help="count retirements at this ELF address",
        )
        parser.add_argument(
            "--stats-at-retire",
            nargs=2,
            type=lambda value: int(value, 0),
            metavar=("PC", "COUNT"),
            help="dump cumulative statistics on the specified retirement",
        )
        parser.add_argument(
            "--trace-tail-fetch",
            action="store_true",
            help="trace instruction fetches after the retirement snapshot",
        )
        parser.add_argument(
            "--cache-hit-ticks",
            help="trace the cache hierarchy after the snapshot; record L1 read hits at these comma-separated ticks",
        )
    parser.add_argument("binary", type=Path, help="Static RV64 Linux ELF")
    parser.add_argument("program_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    binary = args.binary.resolve()
    workdir = args.workdir.resolve()
    if not binary.is_file():
        parser.error(f"Binary not found: {binary}")
    if not workdir.is_dir():
        parser.error(f"Work directory not found: {workdir}")
    if args.stdin and not args.stdin.is_file():
        parser.error(f"Input not found: {args.stdin}")
    if args.max_ticks <= 0:
        parser.error("--max-ticks must be positive")
    requested = args.retired_pc if dasics_init else []
    pcs = dict(requested)
    if len(pcs) != len(requested):
        parser.error("each --retired-pc name must be unique")
    snapshot = args.stats_at_retire if dasics_init else None
    cache_ticks = []
    if dasics_init and args.cache_hit_ticks is not None:
        if not snapshot or "ClassicCachePath" not in debug.flags:
            parser.error(
                "cache-path tracing requires a snapshot and ClassicCachePath"
            )
        try:
            cache_ticks = [int(t, 0) for t in args.cache_hit_ticks.split(",")]
        except ValueError:
            parser.error("--cache-hit-ticks expects comma-separated integers")
        if any(t < 0 or t > m5.MaxTick for t in cache_ticks):
            parser.error("cache trace tick out of range")
    if dasics_init and args.trace_tail_fetch:
        if not snapshot:
            parser.error("--trace-tail-fetch requires --stats-at-retire")
        if "O3FetchTiming" not in debug.flags:
            parser.error("the gem5 binary needs the O3FetchTiming debug flag")
    if snapshot:
        pc, count = snapshot
        if not (0 <= pc < 2**64 and pc % 2 == 0 and 0 < count < 2**64):
            parser.error(
                "--stats-at-retire requires an aligned PC and a positive count"
            )

    system = System(mem_mode="timing", cache_line_size=64)
    system.mem_ranges = [AddrRange(0x80000000, size="8GiB")]
    system.voltage_domain = VoltageDomain(voltage="1V")
    system.clk_domain = SrcClockDomain(
        clock="2GHz", voltage_domain=system.voltage_domain
    )
    system.membus = _xbar(SystemXBar)
    system.system_port = system.membus.cpu_side_ports
    system.workload = SEWorkload.init_compatible(str(binary))
    if dasics_init:
        system.workload.dasics_init = True
    configure_cpu_caches(system, profile)
    if cache_ticks:
        system.cpu.icache.trace_hit_ticks = cache_ticks
        system.cpu.dcache.trace_hit_ticks = cache_ticks
    configure_memory(system)
    process = Process(
        executable=str(binary),
        cmd=[str(binary), *args.program_args],
        cwd=str(workdir),
        output=str(args.stdout.resolve()),
        errout=str(args.stderr.resolve()),
        env=["LC_ALL=C", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1"],
    )
    if args.stdin:
        process.input = str(args.stdin.resolve())
    system.cpu.workload = process
    if pcs or snapshot:
        # The sentinel keeps counting named PCs through process exit, including
        # after the manager has consumed a one-shot snapshot target.
        targets = [
            PcCountPair(pc, 2**64 - 1) for pc in sorted(set(pcs.values()))
        ]
        if snapshot:
            targets.append(PcCountPair(*snapshot))
        system.pc_counts = PcCountTrackerManager(targets=targets)
        system.cpu.probeListener = PcCountTracker(
            core=system.cpu, ptmanager=system.pc_counts, targets=targets
        )
    root = Root(full_system=False, system=system)
    m5.instantiate()
    _print_config(profile)
    deadline = min(m5.MaxTick, m5.curTick() + args.max_ticks)
    event = m5.simulate(deadline - m5.curTick())
    if snapshot:
        pc, count = snapshot
        if (
            event.getCause() != "simpoint starting point found"
            or system.pc_counts.getPcCount(pc) != count
        ):
            print(
                f"Missing retirement snapshot at {pc:#x} count {count}: "
                f"{event.getCause()} at tick {m5.curTick()}",
                flush=True,
            )
            raise SystemExit(1)
        # Python regains control after the O3 tick completes; other
        # instructions can retire in the same tick as the selected PC.
        tick = m5.curTick()
        m5.stats.dump(message="Retirement snapshot")
        report = Path(m5.options.outdir) / "retire-snapshot.json"
        report.write_text(
            json.dumps({"pc": pc, "count": count, "tick": tick}) + "\n"
        )
        if args.trace_tail_fetch:
            debug.flags["O3FetchTiming"].enable()
        if cache_ticks:
            debug.flags["ClassicCachePath"].enable()
        event = m5.simulate(deadline - tick)
    cause = event.getCause()
    code = event.getCode()
    print(
        f"Exiting @ tick {m5.curTick()} because {cause}. "
        f"Guest exit code: {code}",
        flush=True,
    )
    if cause != "exiting with last active thread context":
        raise SystemExit(1)
    if pcs and code == 0:
        counts = {
            name: system.pc_counts.getPcCount(pc) for name, pc in pcs.items()
        }
        report = Path(m5.options.outdir) / "retired-pcs.json"
        report.write_text(json.dumps(counts, indent=2) + "\n")
    raise SystemExit(0 if code == 0 else 1)
