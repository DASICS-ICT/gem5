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
    if pcs:
        # The manager raises a simulation exit at a target count. Use the
        # largest count so the process can run to its ordinary Linux exit.
        targets = [
            PcCountPair(pc, 2**64 - 1) for pc in sorted(set(pcs.values()))
        ]
        system.pc_counts = PcCountTrackerManager(targets=targets)
        system.cpu.probeListener = PcCountTracker(
            core=system.cpu, ptmanager=system.pc_counts, targets=targets
        )
    root = Root(full_system=False, system=system)
    m5.instantiate()
    _print_config(profile)
    event = m5.simulate(args.max_ticks)
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
