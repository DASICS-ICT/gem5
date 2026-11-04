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

"""Build checks and isolated execution for SPEC CPU2006 workloads."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent
SPEC_RUNTIME = SPEC_DIR / "tools/specdiff-runtime"
LIBDASICS_MARKERS = (
    b"dasics_dynamic_call",
    b"_dasics_entry_stage",
    b"dasics_exception",
    b"warn: dasics_main",
)


def report(status, detail):
    color = (
        "32"
        if status == "OK"
        else "33" if status in ("SMOKE", "UNSUPPORTED") else "31"
    )
    print(f"\033[1;{color}m[{status}] {detail}\033[0m", flush=True)


def require_file(path):
    if not path.is_file():
        raise ValueError(f"Missing file: {path}")


def require_executable(command):
    resolved = shutil.which(str(command))
    if resolved is None:
        raise ValueError(f"Missing executable: {command}")
    return resolved


def identity(path):
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def file_state(directory):
    if not directory.is_dir():
        return {}
    return {
        str(path.relative_to(directory)): identity(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def verify_build(elf, readelf):
    require_file(elf)
    result = subprocess.run(
        [
            require_executable(readelf),
            "--file-header",
            "--program-headers",
            "--dynamic",
            str(elf),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip())
    if "RISC-V" not in result.stdout or "ELF64" not in result.stdout:
        raise ValueError("The executable must be a 64-bit RISC-V ELF")
    if "INTERP" in result.stdout or "NEEDED" in result.stdout:
        raise ValueError("The executable must be a static Linux ELF")
    content = elf.read_bytes().lower()
    if any(marker in content for marker in LIBDASICS_MARKERS):
        raise ValueError("The executable contains a LibDASICS startup marker")
    print("ELF check: static RV64, no known LibDASICS startup markers: PASS")
    return 0


def reference_file(case, input_name, name):
    for size in (input_name, "all"):
        path = case / "data" / size / "output" / name
        if path.is_file():
            return path
    raise ValueError(f"Missing reference: {name}")


def prepare_workdir(case, input_name, workdir, preparation):
    workdir.mkdir(parents=True)
    for size in ("all", input_name):
        source = case / "data" / size / "input"
        if source.is_dir():
            shutil.copytree(source, workdir, dirs_exist_ok=True)
    if preparation == "wrf":
        source = workdir / "le/32/RRTM_DATA"
        require_file(source)
        shutil.copy2(source, workdir / "RRTM_DATA")
    elif preparation == "sphinx3":
        entries = []
        for source in sorted(workdir.glob("*.le.raw")):
            name = source.name.removesuffix(".le.raw")
            shutil.copy2(source, workdir / f"{name}.raw")
            entries.append(f"{name} {source.stat().st_size}\n")
        if not entries:
            raise ValueError("No little-endian Sphinx3 audio inputs found")
        (workdir / "ctlfile").write_text("".join(entries))
    elif preparation:
        raise ValueError(f"Unknown input preparation: {preparation}")
    return file_state(workdir)


def last_stat(outdir, name):
    path = outdir / "stats.txt"
    value = None
    if path.is_file():
        for line in path.read_text().splitlines():
            fields = line.split()
            if len(fields) > 1 and fields[0] == name and fields[1].isdigit():
                value = int(fields[1])
    return value


def execute(command, workdir, invocation, mode):
    env = os.environ.copy()
    env.update(LC_ALL="C", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    if mode == "gem5":
        # Preserve the simulator output both in the batch log and beside its inputs.
        with (workdir / "gem5.log").open("w") as log:
            process = subprocess.Popen(
                command,
                cwd=workdir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            return process.wait()
    stdin = (
        open(workdir / invocation["stdin"], "rb")
        if invocation.get("stdin")
        else open(os.devnull, "rb")
    )
    with (
        stdin,
        (workdir / invocation["stdout"]).open("wb") as stdout,
        (workdir / invocation["stderr"]).open("wb") as stderr,
    ):
        return subprocess.run(
            command,
            cwd=workdir,
            env=env,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        ).returncode


def check_outputs(case, input_name, plan, workdir, runs, mode):
    tool = require_executable(SPEC_RUNTIME / "bin/specdiff")
    env = os.environ.copy()
    env["SPEC"] = str(SPEC_RUNTIME)
    env.pop("SPEC_SPECDIFF", None)
    results = []
    for comparison in plan["comparisons"]:
        name = comparison["file"]
        result = {"file": name, "run": comparison["run"]}
        if mode == "gem5" and comparison.get("unsupported_se"):
            result.update(
                status="UNSUPPORTED", reason=comparison["unsupported_se"]
            )
            results.append(result)
            continue
        run = runs[result["run"] - 1]
        actual = workdir / f"{result['run']:02d}" / name
        if run["returncode"] != 0:
            result.update(
                status="UNAVAILABLE",
                reason="The invocation did not complete successfully",
            )
        elif name not in run["outputs"] or not actual.is_file():
            result.update(
                status="MISSING",
                reason="The invocation did not produce this output",
            )
        else:
            reference = reference_file(case, input_name, name)
            log = actual.with_name(actual.name + ".specdiff.log")
            command = [
                tool,
                *comparison.get("args", []),
                "--mis",
                str(reference),
                str(actual),
            ]
            with log.open("w") as stream:
                code = subprocess.run(
                    command,
                    cwd=actual.parent,
                    env=env,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                ).returncode
            result.update(
                status="PASS" if code == 0 else "FAIL", returncode=code
            )
            if code:
                print(log.read_text(), flush=True)
        print(f"Output check: {name}: {result['status']}", flush=True)
        results.append(result)
    return results


def write_result(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")


def run(args, case, metadata, elf):
    plan = metadata["sizes"][args.input]
    workdir = case / "build" / f"run-{args.mode}"
    if args.mode == "gem5":
        workdir /= Path(args.gem5_config).stem
    workdir /= args.input
    # Failed launches and smoke runs must never inherit a successful old check.
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    require_file(elf)
    require_executable(SPEC_RUNTIME / "bin/specdiff")
    timeout = require_executable("timeout")
    if args.mode == "gem5":
        if not all(
            Path(value).is_absolute()
            for value in (args.gem5_binary, args.gem5_config, args.gem5_outdir)
        ):
            raise ValueError(
                "The gem5 binary, config and outdir must be absolute"
            )
        executable = require_executable(args.gem5_binary)
        require_file(Path(args.gem5_config))
        outdir = Path(args.gem5_outdir).resolve()
        if (
            not outdir.is_relative_to(case / "build")
            or outdir == case / "build"
        ):
            raise ValueError(
                "The gem5 outdir must be inside the case build directory"
            )
        # This directory belongs exclusively to this case, config and input size.
        if outdir.exists():
            shutil.rmtree(outdir)
        outdir.mkdir(parents=True)
    else:
        executable = require_executable(args.qemu)
        outdir = None
    print(f"Work directory: {workdir}", flush=True)
    state = {
        "binary": identity(elf),
        "metadata": identity(case / "workload.json"),
        "inputs": file_state(case / "data"),
        "smoke": args.smoke,
        "runs": [],
    }
    for number, invocation in enumerate(plan["runs"], 1):
        current = workdir / f"{number:02d}"
        print(
            f"Invocation {number}/{len(plan['runs'])}: {invocation['argv']}",
            flush=True,
        )
        result = {"invocation": number, "returncode": None, "cycles": None}
        if args.mode == "gem5" and invocation.get("unsupported_se"):
            result.update(
                status="UNSUPPORTED",
                reason=invocation["unsupported_se"],
                outputs=[],
            )
            state["runs"].append(result)
            print(f"Unsupported in SE: {result['reason']}", flush=True)
            continue
        before = prepare_workdir(
            case, args.input, current, metadata.get("prepare")
        )
        if invocation.get("stdin"):
            require_file(current / invocation["stdin"])
        if args.mode == "gem5":
            current_outdir = outdir / f"{number:02d}"
            command = [
                executable,
                "--listener-mode=off",
                f"--outdir={current_outdir}",
                args.gem5_config,
                "--workdir",
                str(current),
                "--stdout",
                str(current / invocation["stdout"]),
                "--stderr",
                str(current / invocation["stderr"]),
            ]
            if invocation.get("stdin"):
                command += ["--stdin", str(current / invocation["stdin"])]
            command += [str(elf), *invocation["argv"]]
        else:
            command = [executable, str(elf), *invocation["argv"]]
        deadline = [timeout, "--kill-after=5s"]
        if args.mode == "gem5":
            # Let the simulator leave its event loop and write final statistics.
            deadline.append("--signal=INT")
        command = [*deadline, f"{args.timeout}s", *command]
        code = execute(command, current, invocation, args.mode)
        after = file_state(current)
        outputs = [
            name
            for name, value in after.items()
            if before.get(name) != value and name != "gem5.log"
        ]
        progress = any(after[name]["size"] > 0 for name in outputs)
        cycles = (
            last_stat(current_outdir, "system.cpu.numCycles")
            if outdir
            else None
        )
        instructions = (
            last_stat(current_outdir, "simInsts") if outdir else None
        )
        progress = progress or bool(instructions)
        if args.smoke:
            status = (
                "SMOKE"
                if code == 0 or (code == 124 and progress)
                else "TIMEOUT" if code == 124 else "FAIL"
            )
        else:
            status = (
                "COMPLETED"
                if code == 0
                else "TIMEOUT" if code == 124 else "FAIL"
            )
        result.update(
            returncode=code,
            status=status,
            cycles=cycles,
            progress=progress,
            outputs=outputs,
        )
        state["runs"].append(result)
        write_result(workdir / "run-state.json", state)
        print(
            f"Invocation exit code: {code}; CPU cycles: {cycles if cycles is not None else 'N/A'}",
            flush=True,
        )
    comparisons = (
        []
        if args.smoke
        else check_outputs(
            case, args.input, plan, workdir, state["runs"], args.mode
        )
    )
    statuses = [run["status"] for run in state["runs"]]
    if "FAIL" in statuses or any(
        item["status"] in ("FAIL", "MISSING") for item in comparisons
    ):
        status, code = "FAIL", 1
    elif "TIMEOUT" in statuses:
        status, code = "TIMEOUT", 124
    elif any(item["status"] == "UNAVAILABLE" for item in comparisons):
        status, code = "FAIL", 1
    elif "UNSUPPORTED" in statuses or any(
        item["status"] == "UNSUPPORTED" for item in comparisons
    ):
        status, code = "UNSUPPORTED", 77
    else:
        status, code = ("SMOKE", 0) if args.smoke else ("OK", 0)
    state.update(status=status, returncode=code, comparisons=comparisons)
    write_result(workdir / "run-state.json", state)
    cycles = (
        sum(run["cycles"] for run in state["runs"])
        if code == 0
        and not args.smoke
        and all(run["cycles"] is not None for run in state["runs"])
        else None
    )
    summary = {
        "benchmark": metadata["benchmark"],
        "input": args.input,
        "mode": args.mode,
        "status": status,
        "returncode": code,
        "checked": sum(
            item["status"] in ("PASS", "FAIL") for item in comparisons
        ),
        "cycles": cycles,
        "runs": state["runs"],
        "comparisons": comparisons,
    }
    write_result(workdir / "result.json", summary)
    if outdir:
        write_result(outdir / "result.json", summary)
        (outdir / "run-result.txt").write_text(
            f"{code} {cycles if cycles is not None else 'N/A'}\n"
        )
    report(status, f"{case.name} ({args.mode}, {args.input})")
    return code


def check(args, case, metadata, elf):
    workdir = case / "build/run-qemu" / args.input
    path = workdir / "run-state.json"
    require_file(path)
    require_file(elf)
    state = json.loads(path.read_text())
    if state.get("smoke") or any(
        run.get("returncode") != 0 for run in state["runs"]
    ):
        raise ValueError("The QEMU workload did not complete successfully")
    if (
        state.get("binary") != identity(elf)
        or state.get("metadata") != identity(case / "workload.json")
        or state.get("inputs") != file_state(case / "data")
    ):
        raise ValueError(
            "The executable, workload or data changed; rerun the workload"
        )
    results = check_outputs(
        case,
        args.input,
        metadata["sizes"][args.input],
        workdir,
        state["runs"],
        "qemu",
    )
    code = int(any(result["status"] != "PASS" for result in results))
    report("OK" if code == 0 else "FAIL", f"{case.name} output validation")
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument(
        "mode", choices=("qemu", "check", "gem5", "verify-build")
    )
    parser.add_argument("--qemu", default="qemu-riscv64")
    parser.add_argument(
        "--input", choices=("test", "train", "ref"), default="test"
    )
    parser.add_argument("--readelf", default="riscv64-linux-gnu-readelf")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--gem5-binary", default="")
    parser.add_argument("--gem5-config", default="")
    parser.add_argument("--gem5-outdir", default="")
    args = parser.parse_args()
    try:
        if args.timeout <= 0:
            raise ValueError("Timeout must be a positive number of seconds")
        case = args.case.resolve()
        elf = case / "build" / f"{case.name.removeprefix('riscv-')}.elf"
        if args.mode == "verify-build":
            return verify_build(elf, args.readelf)
        metadata = json.loads((case / "workload.json").read_text())
        if args.mode == "check":
            return check(args, case, metadata, elf)
        return run(args, case, metadata, elf)
    except (OSError, ValueError, KeyError, IndexError) as error:
        report("FAIL", str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
