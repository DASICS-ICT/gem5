#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Run the protected call and isolated fault cases on one selected model."""

import argparse
import json
import os
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from threading import Thread

PROGRAM = "riscv-dasics-reg-protection"
CASES = (
    "normal",
    "context-read",
    "context-write",
    "stack-read",
    "stack-write",
)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def read_cycles(path):
    cycles = "N/A"
    if path.is_file():
        for line in path.read_text().splitlines():
            fields = line.split()
            if len(fields) > 1 and fields[0] == "system.cpu.numCycles":
                cycles = fields[1] if fields[1].isdigit() else "N/A"
    return cycles


def forward_output(stream, log):
    for line in stream:
        log.write(line)
        log.flush()
        print(line, end="", flush=True)


def run_case(args, case):
    # Normal outputs retain the root dispatcher's config/statistics layout.
    directory = args.outdir if case == "normal" else args.outdir / case
    suffix = "" if case == "normal" else f"-{case}"
    elf = Path(__file__).resolve().parent.parent / "build"
    elf = elf / f"{PROGRAM}{suffix}.elf"
    marker = "normal" if case == "normal" else "expected fault"
    expected = f"[OK] DASICS register protection: {marker}"
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("stats.txt", "config.ini", "config.json", "case-result.json"):
        (directory / name).unlink(missing_ok=True)
    command = [
        str(args.gem5),
        "--listener-mode=off",
        f"--outdir={directory}",
        str(args.config),
        str(elf),
    ]
    result = {
        "case": case,
        "cpu": args.cpu,
        "command": command,
        "started": timestamp(),
    }
    log_path = directory / "run.log"
    with log_path.open("w") as log:
        log.write(f"Started: {result['started']}\n")
        log.write(f"Command: {shlex.join(command)}\n")
        log.flush()
        try:
            with subprocess.Popen(
                command,
                cwd=args.repo,
                stdout=subprocess.PIPE if case == "normal" else log,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            ) as process:
                reader = None
                if case == "normal":
                    reader = Thread(
                        target=forward_output, args=(process.stdout, log)
                    )
                    reader.start()
                try:
                    raw_rc = process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raw_rc = 124
                finally:
                    # Drain the pipe before closing its persistent log.
                    if reader is not None:
                        reader.join()
                if raw_rc == 124:
                    log.write("Timeout: exceeded 60 seconds\n")
        except OSError as error:
            raw_rc = 1
            log.write(f"Launch failed: {error}\n")
        result.update(finished=timestamp(), process_exit_code=raw_rc)
        log.write(f"Finished: {result['finished']}\nExit code: {raw_rc}\n")

    marker_found = (
        expected in log_path.read_text(errors="replace").splitlines()
    )
    rc = raw_rc if raw_rc >= 0 else 128 - raw_rc
    if rc == 0 and not marker_found:
        rc = 1
    cycles = read_cycles(directory / "stats.txt") if rc == 0 else "N/A"
    if case == "normal" and cycles == "N/A" and rc == 0:
        rc = 1
    result.update(
        expected_marker=expected,
        marker_found=marker_found,
        exit_code=rc,
        cycles=cycles,
        log=str(log_path),
    )
    write_json(directory / "case-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("repo", "gem5", "config", "outdir", "cpu"):
        parser.add_argument(f"--{option}", required=True)
    args = parser.parse_args()
    if not all(vars(args).values()):
        parser.error("Use the root dasics-test target to supply run settings.")
    for option in ("repo", "gem5", "config", "outdir"):
        setattr(args, option, Path(getattr(args, option)).resolve())
    if not args.gem5.is_file() or not os.access(args.gem5, os.X_OK):
        parser.error("Missing gem5 binary; run make riscv-dasics first.")
    if not args.config.is_file():
        parser.error(f"Missing CPU config: {args.config}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    for name in ("run-result.txt", "result.json"):
        (args.outdir / name).unlink(missing_ok=True)
    with ThreadPoolExecutor(max_workers=len(CASES)) as executor:
        results = list(executor.map(lambda case: run_case(args, case), CASES))

    print("\nRegister-protection cases:")
    for result in results:
        rc = result["exit_code"]
        status = "PASS" if rc == 0 else "TIMEOUT" if rc == 124 else "FAIL"
        detail = f"  {result['case']:<16} {status:<7} exit={rc}"
        print(detail if rc == 0 else f"\033[1;31m{detail}\033[0m")
    # Require the guest's exact marker as well as a successful process exit.
    rc = next((r["exit_code"] for r in results if r["exit_code"]), 0)
    if any(r["exit_code"] == 124 for r in results):
        rc = 124
    cycles = results[0]["cycles"] if rc == 0 else "N/A"
    (args.outdir / "run-result.txt").write_text(f"{rc} {cycles}\n")
    write_json(
        args.outdir / "result.json", {"exit_code": rc, "cases": results}
    )
    print(f"CPU cycles (normal full functional case, not ROI): {cycles}")
    print(f"Case logs: {args.outdir}")
    status = "OK" if rc == 0 else "TIMEOUT" if rc == 124 else "FAIL"
    color = "32" if rc == 0 else "31"
    print(f"\033[1;{color}m[{status}] DASICS register protection\033[0m")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
