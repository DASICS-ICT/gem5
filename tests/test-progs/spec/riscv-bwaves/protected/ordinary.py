# SPDX-License-Identifier: BSD-3-Clause
"""Count the ordinary bwaves pow calls and produce the one-step reference."""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pow_sites import ordinary_sites

CASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE.parent))
import run as spec

# For each cell shell calls flux once and jacobian in three directions.
CALLS_PER_CELL = {
    "flux": 1,
    "jacobian_first": 3,
    "jacobian_second": 3,
    "shell": 1,
}
CELLS = 33 * 33 * 16


def set_steps(path, steps):
    text = path.read_text()
    if not re.search(r"^'nx\s+ny\s+nz'\s*\n\s*33\s+33\s+16\s*$", text, re.M):
        raise ValueError("Expected the 33 x 33 x 16 SPEC test grid")
    new_text, replaced = re.subn(
        r"^('Number of Time Steps'[ \t]*\n[ \t]*)25(?=[ \t]*$)",
        lambda m: m[1] + str(steps),
        text,
        flags=re.M,
    )
    if replaced != 1:
        raise ValueError("Expected one 25-step record in bwaves.in")
    if steps != 25:
        path.write_text(new_text)


def profile(ordinary, batch, elf, plugin, pcs, plan, steps):
    name = "full-reference" if steps == 25 else "one-step-reference"
    directory = batch / name
    current = directory / "work/01"
    before = spec.prepare_workdir(ordinary, "test", current, None)
    set_steps(current / "bwaves.in", steps)
    log = directory / "qemu-counts.txt"
    if "," in str(plugin):
        raise ValueError("QEMU plugin paths must not contain a comma")
    cmd = [
        "timeout",
        "600s",
        "qemu-riscv64",
        "-d",
        "plugin",
        "-D",
        str(log),
        "-plugin",
        ",".join([str(plugin), *(f"{k}={pc:#x}" for k, pc in pcs.items())]),
        str(elf),
    ]
    (invocation,) = plan["runs"]
    result = dict(status="FAIL", steps=steps, pcs=pcs, command=cmd)
    try:
        rc = spec.execute(cmd, current, invocation, "qemu")
        result["returncode"] = rc
        if rc:
            raise ValueError(
                f"{name}: QEMU exit {rc}, see {current}/bwaves.err"
            )
        names = {pc: label for label, pc in pcs.items()}
        counts = {}
        for line in log.read_text().splitlines():
            if not line.strip():
                continue
            address, count = line.split()
            label = names[int(address, 16)]
            if label in counts:
                raise ValueError(f"{name}: duplicate count for {label}")
            counts[label] = int(count)
        result["counts"] = counts
        # The error probes are outgoing transfers inside pow. A hit would
        # require a separate examination of the math error and TLS paths.
        expected = dict.fromkeys(pcs, 0)
        expected.update(
            {k: n * CELLS * steps for k, n in CALLS_PER_CELL.items()}
        )
        expected.update(main=1, pow=8 * CELLS * steps)
        if counts != expected:
            raise ValueError(f"{name}: expected {expected}, observed {counts}")
        outputs = [c["file"] for c in plan["comparisons"]]
        after = spec.file_state(current)
        for filename in outputs:
            if (
                before.get(filename) == after.get(filename)
                or not (current / filename).stat().st_size
            ):
                raise ValueError(f"{name}: missing output {filename}")
        result["outputs"] = outputs
        if steps == 25:
            checks = spec.check_outputs(
                ordinary,
                "test",
                plan,
                current.parent,
                [{"returncode": rc, "outputs": outputs}],
                "qemu",
                runtime=ordinary.parent / "tools/specdiff-runtime",
            )
            result["comparisons"] = checks
            if len(checks) != 3 or any(c["status"] != "PASS" for c in checks):
                raise ValueError(f"{name}: SPEC output mismatch")
        result["status"] = "PASS"
        print(
            f"PASS {name}: {counts['pow']:,} calls, three numerical outputs",
            flush=True,
        )
    except (OSError, ValueError, KeyError) as exc:
        result["error"] = str(exc)
        raise
    finally:
        spec.write_result(directory / "result.json", result)


def run(ordinary, batch):
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    elf = ordinary / "build/bwaves.elf"
    spec.verify_build(
        elf, os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-") + "readelf"
    )
    spec.require_executable(
        ordinary.parent / "tools/specdiff-runtime/bin/specdiff"
    )
    if any(
        (batch / p).exists() for p in ("one-step-reference", "full-reference")
    ):
        raise ValueError("Use fresh reference directories")
    markers, sites = ordinary_sites(elf)
    pcs = {**markers, **{label: pc for pc, label in sites.items()}}
    if len(set(pcs.values())) != len(pcs) or set(sites.values()) != set(
        CALLS_PER_CELL
    ):
        raise ValueError(f"Unexpected linked pow call sites: {sites}")
    batch.mkdir(parents=True, exist_ok=True)
    plugin = batch / "qemu-count.so"
    flags = shlex.split(
        subprocess.check_output(
            ["pkg-config", "--cflags", "glib-2.0"], text=True
        )
    )
    subprocess.run(
        [
            os.environ.get("HOST_CC", "cc"),
            "-O2",
            "-shared",
            "-fPIC",
            "-fvisibility=hidden",
            *flags,
            Path(__file__).with_name("qemu_count.c"),
            "-o",
            plugin,
        ],
        check=True,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = [
            pool.submit(
                profile, ordinary, batch, elf, plugin, pcs, plan, steps
            )
            for steps in (25, 1)
        ]
        for job in runs:
            job.result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinary-case", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    args = parser.parse_args()
    run(args.ordinary_case.resolve(), args.batch.resolve())
