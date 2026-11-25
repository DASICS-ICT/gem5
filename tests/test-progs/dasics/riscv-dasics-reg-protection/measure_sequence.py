#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Measure A-B-A-C-A chains with one or all saved registers in each bank."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

import measure

MODES = ("software", "proreg_gf")


def protection_mask(full):
    return 0xFFF if full else 0x008


def expected_deltas(full):
    # Two banks use the same mask. Each round trip replaces save, clear
    # and restore for every selected register with two PROREGs and a LEAVE.
    registers = 2 * protection_mask(full).bit_count()
    return 2 * (3 * registers - 3), 2 * registers, 2 * registers


def elf_path(mode, count, *, full=False):
    directory = "sequence-full" if full else "sequence"
    return measure.build_dir() / "roi" / directory / f"{mode}-{count}.elf"


def run_one(outdir, mode, count, *, trace=False, full=False):
    directory = Path(outdir).resolve() / f"{mode}-{count}"
    directory.mkdir(parents=True)
    mask = protection_mask(full)
    job = dict(
        mode=mode, workload="sequence", iterations=count, sequence_mask=mask
    )
    command = [
        str(measure.REPO / "build/RISCV_DASICS/gem5.opt"),
        "--listener-mode=off",
        f"--outdir={directory}",
    ]
    if trace:
        command += ["--debug-flags=Commit", "--debug-file=debug.trace.gz"]
    command += [
        str(
            measure.REPO
            / "configs/dasics/riscv_dasics_reg_protection_o3_v5_full.py"
        ),
        str(elf_path(mode, count, full=full)),
        "--mode",
        mode,
        "--workload",
        "sequence",
        "--iterations",
        str(count),
        "--sequence-mask",
        hex(mask),
    ]
    result = {**job, **measure.run_process(directory, command, timeout=300)}
    try:
        if result["timed_out"] or result["process_exit_code"] != 0:
            raise ValueError(
                result.get("error", "gem5 exited with a nonzero status")
            )
        roi, stats = measure.validate(directory, job)
        result.update(status="PASS", roi=roi, statistics=stats)
    except (OSError, TypeError, ValueError) as error:
        result.update(status="FAIL", error=str(error))
        raise ValueError(f"{directory}: {error}") from error
    finally:
        measure.write_json(directory / "result.json", result)
    return result


def summarize(results, *, full=False):
    mask = protection_mask(full)
    # Runs archived before the full-mask experiment only protected s3/fs3.
    if any(r.get("sequence_mask", 0x008) != mask for r in results):
        raise ValueError("Sequence result has a different protection mask")
    by_gate = {(r["iterations"], r["mode"]): r["statistics"] for r in results}
    pairs = []
    for count in measure.ITERATIONS:
        sw, gf = (by_gate[count, mode] for mode in MODES)
        sw_cycles, gf_cycles = (s["system.cpu.numCycles"] for s in (sw, gf))
        saved = sw_cycles - gf_cycles
        pair = dict(
            chains=count,
            sequence_mask=mask,
            software_roi_cycles=sw_cycles,
            proreg_gf_roi_cycles=gf_cycles,
            software_cycles_per_chain=sw_cycles / count,
            proreg_gf_cycles_per_chain=gf_cycles / count,
            saved_cycles_per_chain=saved / count,
            saved_percent=100 * saved / sw_cycles,
        )
        instructions, loads, stores = expected_deltas(full)
        for key, field, expected in (
            ("numInsts", "instructions", instructions),
            ("numLoadInsts", "loads", loads),
            ("numStoreInsts", "stores", stores),
        ):
            stat = f"system.cpu.commitStats0.{key}"
            observed = sw[stat] - gf[stat]
            if observed != expected * count:
                raise ValueError(
                    f"{count} chains: expected {expected * count} "
                    f"fewer {field}, observed {observed}"
                )
            pair[f"{field}_saved_per_chain"] = observed // count
        pairs.append(pair)
    return {
        "status": "PASS",
        "sequence_mask": mask,
        "protected_registers": "s0-s11/fs0-fs11" if full else "s3/fs3",
        "warmup_chains": measure.WARMUP,
        "pairs": pairs,
        "absolute_savings_drift_cycles_per_chain": abs(
            pairs[0]["saved_cycles_per_chain"]
            - pairs[1]["saved_cycles_per_chain"]
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir", type=Path, required=True, help="New output directory"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="protect all 12 integer and 12 FP saved registers",
    )
    args = parser.parse_args()
    outdir = args.outdir.resolve()
    jobs = list(product(measure.ITERATIONS, MODES))
    try:
        outdir.mkdir(parents=True)
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = [
                pool.submit(run_one, outdir, mode, count, full=args.full)
                for count, mode in jobs
            ]
            results = [future.result() for future in futures]
        measure.write_json(outdir / "results.json", results)
        summary = summarize(results, full=args.full)
        measure.write_json(outdir / "summary.json", summary)
        pairs = summary["pairs"]
        measure.write_csv(outdir / "summary.csv", pairs, list(pairs[0]))
    except (OSError, ValueError) as error:
        parser.exit(1, f"[FAIL] {error}\n")

    for row in pairs:
        print(
            f"{row['chains']} chains: SW {row['software_cycles_per_chain']:.4f}, "
            f"G+F {row['proreg_gf_cycles_per_chain']:.4f}, "
            f"saved {row['saved_cycles_per_chain']:.7f} cycles/chain "
            f"({row['saved_percent']:.6f}%)"
        )


if __name__ == "__main__":
    main()
