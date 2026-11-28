#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Run matched v5_full integer register pressure traces with a cold load."""

import argparse
import configparser
import gzip
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from check_clobber import (
    INT_SCRATCH,
    SAVED,
)
from elftools.elf.elffile import ELFFile
from measure import (
    REPO,
    TEST_DIR,
    require,
    run_process,
    write_json,
)

FLAGS = "O3RegPressure,FreeList,ClassicCachePath,HWPrefetch"
PRESSURE_CONFIGS = {
    (96, 128): "riscv_dasics_o3_v5_full.py",
    (128, 128): "riscv_prf_pressure_o3_v5_full_rob128.py",
    (128, 160): "riscv_prf_pressure_o3_v5_full_rob128_int160.py",
}
NAMES = (
    "prf_clobber_begin",
    "prf_clobber_end",
    "prf_slow_load",
    "prf_writes_begin",
    "prf_writes_end",
    "prf_measure_call",
    "prf_measure_return",
    "prf_cold_word",
    "prf_hot_word",
    "protected_gate",
    "gate_call",
    "return_gate",
    "callee_entry",
)


def inspect_image(path, count, *, hardware=True):
    with path.open("rb") as src:
        elf = ELFFile(src)
        table = elf.get_section_by_name(".symtab")
        symbols = {}
        for name in NAMES:
            (symbol,) = table.get_symbol_by_name(name)
            symbols[name] = symbol["st_value"]
        trusted = elf.get_section_by_name(".text.trusted")
        body = trusted.data()
        gate = symbols["protected_gate"] - trusted["sh_addr"]
        call = symbols["gate_call"] - trusted["sh_addr"]
        resume = symbols["return_gate"] - trusted["sh_addr"]
        require(
            body[gate:call].count((0xFFF0300B).to_bytes(4, "little"))
            == int(hardware)
            and body[resume:].count((0x0000500B).to_bytes(4, "little"))
            == int(hardware),
            f"{path}: unexpected integer protection policy",
        )
        text = elf.get_section_by_name(".text.untrusted")
        base = text["sh_addr"]
        raw = bytearray(text.data())

        def word(pc):
            return int.from_bytes(raw[pc - base : pc - base + 4], "little")

        start = symbols["prf_clobber_begin"]
        load = symbols["prf_slow_load"]
        writes, end = symbols["prf_writes_begin"], symbols["prf_writes_end"]
        require(
            start == symbols["callee_entry"]
            and load == start + 48
            and load == symbols["prf_clobber_end"]
            and writes == load + 4
            and end == writes + 128 * 4,
            f"{path}: unexpected B instruction boundaries",
        )
        require(
            word(load) == 0x00053503 and word(end) == 0x8067,
            f"{path}: expected ld a0,0(a0) and ret",
        )
        for i, rd in enumerate(SAVED if count else INT_SCRATCH):
            pc = start + 4 * i
            w = word(pc)
            require(
                w == ((0x101 + i) << 20 | rd << 7 | 0x13),
                f"{path}: incorrect entry write {i}",
            )
            raw[pc - base : pc - base + 4] = (w & ~(31 << 7)).to_bytes(
                4, "little"
            )
        for pc in range(writes, end, 4):
            w = word(pc)
            require(
                w & 0xFF07F == 0x13 and ((w >> 7) & 31) in INT_SCRATCH,
                f"{path}: pressure write at {pc:#x} is not independent",
            )
        require(
            symbols["prf_hot_word"] // 4096 == symbols["prf_cold_word"] // 4096
            and abs(symbols["prf_hot_word"] - symbols["prf_cold_word"])
            >= 1024,
            f"{path}: warm and cold data must use distant lines on one page",
        )
        image = []
        for seg in elf.iter_segments():
            if seg["p_type"] != "PT_LOAD":
                continue
            addr = seg["p_vaddr"]
            contents = bytearray(seg.data())
            if addr <= base and base + len(raw) <= addr + len(contents):
                contents[base - addr : base - addr + len(raw)] = raw
            image.append(
                (
                    addr,
                    seg["p_paddr"],
                    seg["p_memsz"],
                    seg["p_flags"],
                    contents,
                )
            )
        return symbols, image


def check_config(path, rob_entries=96, int_regs=128):
    require(
        (rob_entries, int_regs) in PRESSURE_CONFIGS,
        "Unsupported experimental ROB and integer PRF configuration",
    )
    cfg = configparser.ConfigParser(interpolation=None)
    with path.open() as src:
        cfg.read_file(src)
    cpu = cfg["system.cpu"]
    expected = dict(
        numThreads=1,
        numROBEntries=rob_entries,
        numPhysIntRegs=int_regs,
        numPhysFloatRegs=160,
        renameWidth=4,
        commitWidth=8,
    )
    require(
        all(cpu.getint(k) == v for k, v in expected.items()),
        f"{path}: unexpected O3 resource configuration",
    )
    require(
        cfg["system"].getint("cache_line_size") == 64
        and cfg[cpu["clk_domain"]].getint("clock") == 500,
        f"{path}: unexpected clock or cache-line size",
    )
    for cache, target in {
        "system.cpu.icache": "TaggedPrefetcher",
        "system.cpu.dcache": "StridePrefetcher",
        "system.l20": "MultiPrefetcher",
        "system.l21": "MultiPrefetcher",
        "system.l30": "Null",
        "system.l31": "Null",
    }.items():
        pf = cfg[cache]["prefetcher"]
        require(
            (pf if pf == "Null" else cfg[pf]["type"]) == target,
            f"{path}: unexpected prefetcher on {cache}",
        )
        if target == "MultiPrefetcher":
            require(
                [cfg[p]["type"] for p in cfg[pf]["prefetchers"].split()]
                == ["BOPPrefetcher", "SmsPrefetcher"],
                f"{path}: unexpected {cache} child prefetchers",
            )


def cache_path(trace, symbols, send, response):
    """Follow the cold demand's requestor and birth tick to the DRAM command."""
    target = symbols["prf_cold_word"]
    require(
        target % 64 == 0, "Cold target must start on a cache-line boundary"
    )
    address = f"{target:#x}"
    events = []
    with gzip.open(trace, "rt") as src:
        for line in src:
            if address not in line:
                continue
            pieces = line.strip().split(": ", 2)
            if len(pieces) != 3 or not pieces[0].isdigit():
                continue
            stamp, component, message = pieces
            if message == f"Generating prefetch for {address}.":
                events.append(
                    dict(
                        tick=int(stamp), component=component, op="generate_pf"
                    )
                )
                continue
            if not message.startswith(("cpath ", "cachepath mem-")):
                continue
            head, op, *rest = message.split()
            fields = dict(v.split("=", 1) for v in rest)
            addr = (
                fields.get("line") if head == "cpath" else fields.get("addr")
            )
            if addr is None or (int(addr, 0) & ~63) != target:
                continue
            events.append(
                dict(
                    tick=int(stamp),
                    component=component,
                    op=op.removeprefix("op="),
                    **fields,
                )
            )
    require(
        events
        and events[0]["op"] == "new"
        and events[0]["component"] == "system.cpu.dcache"
        and events[0]["tick"] == send
        and int(events[0]["pc"], 0) == symbols["prf_slow_load"],
        "Target line was touched before the measured demand or was not cold",
    )
    root = events[0]
    identity = root["rid"], root["born"]
    demand = [
        e
        for e in events
        if (e.get("rid"), e.get("born")) == identity
        and send <= e["tick"] <= response
    ]
    news = [e for e in demand if e["op"] == "new"]
    names = [e["component"] for e in news]
    require(
        len(names) == 3
        and names[0] == "system.cpu.dcache"
        and re.fullmatch(r"system\.l2[01]", names[1])
        and re.fullmatch(r"system\.l3[01]", names[2])
        and all(e["pf"] == e["leader_pf"] == "0" for e in news),
        f"Demand did not allocate fresh L1D/L2/L3 misses: {names}",
    )
    mem = [e for e in demand if e["op"] == "mem-issue"]
    require(
        mem
        and all(send <= int(e["cmd"]) <= response for e in mem)
        and any(e["op"] == "mem-queue" for e in demand)
        and any(e["op"] == "mem-response" for e in demand)
        and not any(e["op"] == "mem-bypass" for e in demand),
        "No complete demand read from DRAM inside the load interval",
    )
    return dict(
        address=address,
        requestor=int(root["rid"]),
        birth_tick=int(root["born"]),
        misses=names,
        dram_command_ticks=[int(e["cmd"]) for e in mem],
        events=events,
    )


def run_simulation(directory, elf, rob_entries=96, int_regs=128):
    config_script = (
        REPO / "configs/dasics" / PRESSURE_CONFIGS[rob_entries, int_regs]
    )
    directory.mkdir()
    m5out = directory / "m5out"
    command = [
        str(REPO / "build/RISCV_DASICS/gem5.opt"),
        "--listener-mode=off",
        f"--outdir={m5out}",
        f"--debug-flags={FLAGS}",
        "--debug-file=debug.trace.gz",
        str(config_script),
        str(elf),
    ]
    run = run_process(directory, command, 300)
    write_json(directory / "simulation.json", run)
    log = (directory / "run.log").read_text()
    require(
        run["process_exit_code"] == 0
        and not run["timed_out"]
        and "[OK] DASICS register protection: PRF pressure" in log.splitlines()
        and re.search(
            r"^Exiting @ tick \d+ because semi:ADP_Stopped_ApplicationExit\.$",
            log,
            re.M,
        ),
        f"Guest exit or register/value validation failed; see {directory}/run.log",
    )
    config = m5out / "config.ini"
    check_config(config, rob_entries, int_regs)
    return m5out / "debug.trace.gz", config


def run_case(batch, count, elf, symbols):
    from prf_pressure_analyze import (
        analyze,
        save,
    )

    directory = batch / f"k{count}"
    trace, config = run_simulation(directory, elf)
    result = analyze(trace, elf, config, count)
    require(
        result["cold_addr"] == symbols["prf_cold_word"],
        "LSQ target and ELF physical address differ",
    )
    cache = cache_path(
        trace, symbols, result["load_send_tick"], result["load_response_tick"]
    )
    write_json(directory / "cache-evidence.json", cache)
    result.update(
        guest_exit_code=0, dram_command_ticks=cache["dram_command_ticks"]
    )
    save(result, directory)
    print(
        f"PASS k{count}: guest, v5_full configuration, DRAM path and Rename trace",
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    batch = parser.parse_args().batch.resolve()
    batch.mkdir(parents=True, exist_ok=True)
    elfs = TEST_DIR / "build/prf-pressure"
    cases = []
    common = None
    for count in (0, 12):
        require(
            not (batch / f"k{count}").exists(), "Use fresh output directories"
        )
        elf = elfs / f"k{count}.elf"
        symbols, image = inspect_image(elf, count)
        if common is not None:
            require(
                common == (symbols, image),
                "Load image differs outside the 12 destination fields",
            )
        common = symbols, image
        cases.append((count, elf, symbols))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(run_case, batch, *case) for case in cases]
        summaries = [job.result() for job in results]
    write_json(batch / "summary.json", dict(status="PASS", cases=summaries))


if __name__ == "__main__":
    main()
