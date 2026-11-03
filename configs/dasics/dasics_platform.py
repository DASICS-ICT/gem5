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

"""Shared bare-metal wiring and explicit timing assumptions for DASICS."""

import argparse
import configparser
import math
from pathlib import Path

import m5
from m5.objects import (
    ITTAGE,
    ITTAGE_TAGE,
    LRURP,
    NULL,
    TAGE,
    AddrRange,
    BOPPrefetcher,
    BranchPredictor,
    Bridge,
    BTBLevel,
    Cache,
    DDR4_2400_8x8,
    FUDesc,
    FUPool,
    HiFive,
    IOXBar,
    IQUnit,
    L2XBar,
    MemCtrl,
    MultiLevelBTB,
    MultiPrefetcher,
    OpDesc,
    PMAChecker,
    ReadPort,
    ReturnAddrStack,
    RiscvBareMetal,
    RiscvO3CPU,
    RiscvRTC,
    RiscvSemihosting,
    RiscvSystem,
    Root,
    SIMD_Unit,
    SimpleMemory,
    SmsPrefetcher,
    SnoopFilter,
    SrcClockDomain,
    StridePrefetcher,
    SystemXBar,
    TAGEBase,
    TaggedPrefetcher,
    VoltageDomain,
    WritePort,
)

# These are explicit simulator assumptions, not measured RTL path delays.
CPU_TIMING = {
    "fetchToBacDelay": 1,
    "decodeToFetchDelay": 1,
    "renameToFetchDelay": 1,
    "iewToFetchDelay": 1,
    "commitToFetchDelay": 1,
    "renameToDecodeDelay": 1,
    "iewToDecodeDelay": 1,
    "commitToDecodeDelay": 1,
    "bacToFetchDelay": 1,
    "fetchToDecodeDelay": 1,
    "iewToRenameDelay": 1,
    "commitToRenameDelay": 1,
    "decodeToRenameDelay": 1,
    "commitToIEWDelay": 1,
    "renameToIEWDelay": 2,
    "issueToExecuteDelay": 1,
    "iewToCommitDelay": 1,
    "renameToROBDelay": 1,
    "trapLatency": 13,
    "fetchTrapLatency": 1,
    "backComSize": 5,
    "forwardComSize": 5,
}
CPU_POLICY = {
    "numThreads": 1,
    "issueWidth": 16,
    "wbWidth": 16,
    "numPhysVecPredRegs": 32,
    "numPhysMatRegs": 2,
    "numPhysCCRegs": 0,
    "numRobs": 1,
    "iqInsertionPolicy": "FirstMatch",
    "LSQDepCheckShift": 4,
    "LSQCheckLoads": True,
    "store_set_clear_period": 250000,
    "LFSTSize": 1024,
    "SSITSize": "1024",
    "SSITAssoc": 1,
    "needsTSO": False,
    "decoupledFrontEnd": True,
    "minInstSize": 2,
    "maxFTPerCycle": 4,
    "maxTakenPredPerCycle": 2,
    "smtNumFetchingThreads": 1,
    "smtFetchPolicy": "RoundRobin",
    "smtLSQPolicy": "Partitioned",
    "smtROBPolicy": "Partitioned",
    "smtCommitPolicy": "RoundRobin",
}
CACHE_TIMING = {
    "l1i": (2, 2, 2),
    "l1d": (2, 2, 2),
    "l2": (2, 2, 2),
    "l3": (2, 2, 2),
}
OP_LATENCY = {
    "IntAlu": (1, True),
    "IntMult": (3, True),
    "IntDiv": (20, False),
    "System": (1, True),
    "FloatAdd": (2, True),
    "FloatCmp": (2, True),
    "FloatCvt": (2, True),
    "Bf16Cvt": (2, True),
    "FloatMult": (4, True),
    "FloatMultAcc": (5, True),
    "FloatMisc": (3, True),
    "FloatDiv": (12, False),
    "FloatSqrt": (24, False),
    "SimdFloatAdd": (2, True),
    "SimdFloatMult": (3, True),
    "SimdFloatMultAcc": (3, True),
    "SimdDiv": (20, False),
    "SimdFloatDiv": (20, False),
    "SimdSqrt": (24, False),
    "SimdFloatSqrt": (24, False),
}


def _bytes(value):
    for suffix, scale in (
        ("GiB", 1 << 30),
        ("MiB", 1 << 20),
        ("KiB", 1 << 10),
        ("B", 1),
    ):
        if value.endswith(suffix):
            return int(float(value[: -len(suffix)]) * scale)
    return int(value)


def _op_names(unit):
    return [str(op.opClass) for op in unit.opList]


def _units(tag, count):
    names = {
        "alu": ["IntAlu"],
        "mdu": ["IntMult", "IntDiv"],
        "system": ["System"],
        "int_pair": ["IntAlu", "IntMult", "IntDiv", "System"],
        "fmac": ["FloatAdd", "FloatMult", "FloatMultAcc"],
        "fmisc": [
            "FloatCmp",
            "FloatCvt",
            "Bf16Cvt",
            "FloatMisc",
            "FloatDiv",
            "FloatSqrt",
        ],
        "load": _op_names(ReadPort()),
        "store": _op_names(WritePort()),
        "simd": _op_names(SIMD_Unit()),
        "simd_mem": [
            name
            for name in _op_names(ReadPort()) + _op_names(WritePort())
            if name.startswith("Simd")
        ],
    }[tag]
    # Vector operations share the modeled FP ports in every selected model.
    if tag in ("fmac", "fmisc"):
        names += _op_names(SIMD_Unit())
    ops = []
    for name in dict.fromkeys(names):
        latency, pipelined = OP_LATENCY.get(name, (1, True))
        ops.append(OpDesc(opClass=name, opLat=latency, pipelined=pipelined))
    return [FUDesc(count=count, opList=ops)]


def _tage_params(branch):
    histories = branch["tage_histories"]
    rows = int(math.log2(branch["tage_rows"]))
    return dict(
        numThreads=1,
        instShiftAmt=1,
        nHistoryTables=len(histories),
        minHist=min(histories),
        maxHist=max(histories),
        tagTableTagWidths=[0] + [branch["tage_tag"]] * len(histories),
        logTagTableSizes=[rows] * (len(histories) + 1),
        logRatioBiModalHystEntries=2,
        tagTableCounterBits=3,
        tagTableUBits=2,
        histBufferSize=1 << 21,
        pathHistBits=16,
        logUResetPeriod=18,
        numUseAltOnNa=1,
        initialTCounterValue=1 << 17,
        useAltOnNaBits=4,
        maxNumAlloc=1,
        noSkip=[True] * (len(histories) + 1),
        speculativeHistUpdate=True,
        takenOnlyHistory=False,
    )


def _predictor(branch):
    # gem5 generates geometric TAGE histories; RTL table histories are in
    # PROFILE["rtl"]. SC, loop and FTB semantics require separate modeling.
    return BranchPredictor(
        numThreads=1,
        instShiftAmt=1,
        speculativeHistUpdate=True,
        requiresBTBHit=False,
        updateBTBAtSquash=True,
        takenOnlyHistory=False,
        btb=MultiLevelBTB(
            levels=[
                BTBLevel(
                    numEntries=branch["ubtb"],
                    associativity=4,
                    tagBits=16,
                    latency=1,
                    inclusive=True,
                    instShiftAmt=1,
                ),
                BTBLevel(
                    numEntries=branch["ftb"],
                    associativity=branch["ftb_ways"],
                    tagBits=16,
                    latency=2,
                    inclusive=False,
                    instShiftAmt=1,
                ),
            ]
        ),
        ras=ReturnAddrStack(numThreads=1, numEntries=branch["ras"]),
        conditionalBranchPred=TAGE(
            numThreads=1,
            instShiftAmt=1,
            defaultLatency=1,
            tage=TAGEBase(**_tage_params(branch)),
        ),
        indirectBranchPred=ITTAGE(
            numThreads=1,
            instShiftAmt=1,
            itage=ITTAGE_TAGE(**_tage_params(branch)),
        ),
    )


def _prefetcher(kind):
    common = dict(
        latency=1,
        queue_size=16,
        max_prefetch_requests_with_pending_translation=16,
        queue_squash=True,
        queue_filter=True,
        cache_snoop=True,
        tag_prefetch=True,
        throttle_control_percentage=0,
        block_size=64,
        page_bytes="4KiB",
        use_virtual_addresses=False,
        on_read=True,
        on_write=True,
        on_data=True,
        on_inst=False,
        prefetch_on_access=True,
        prefetch_on_pf_hit=True,
        on_miss=False,
    )
    if kind == "none":
        return NULL
    if kind == "tagged":
        return TaggedPrefetcher(
            **dict(common, on_inst=True, on_data=False), degree=1
        )
    if kind == "sms":
        return SmsPrefetcher(
            **common, ft_size=16, pht_size=64, region_size=1024
        )
    if kind == "stream_stride":
        return StridePrefetcher(
            **common,
            degree=1,
            distance=0,
            confidence_counter_bits=2,
            initial_confidence=0,
            confidence_threshold=50,
            use_requestor_id=True,
            use_cache_line_address=True,
            table_assoc=1,
            table_entries="16",
        )
    if kind == "bop":
        return BOPPrefetcher(
            **dict(common, on_miss=True),
            degree=1,
            score_max=31,
            round_max=50,
            bad_score=2,
            rr_size=256,
            tag_bits=12,
            offset_list_size=46,
            negative_offsets_enable=True,
            delay_queue_enable=True,
            delay_queue_size=16,
            delay_queue_cycles=175,
        )
    if kind == "bop_sms":
        return MultiPrefetcher(
            block_size=64,
            on_inst=False,
            prefetchers=[_prefetcher("bop"), _prefetcher("sms")],
        )
    raise ValueError(f"Unknown prefetcher: {kind}")


def _cache(level, spec, bank=0):
    bank_count = spec["banks"] if level in ("l2", "l3") else 1
    bits = int(math.log2(bank_count))
    bank_bytes = _bytes(spec["size"]) // bank_count
    sets = bank_bytes // (spec["assoc"] * 64)
    # Keep bank selection above the cache's set index so every set is usable.
    # RTL line-interleaved routing needs a bank-aware indexing implementation.
    bank_low_bit = 6 + int(math.log2(sets))
    ranges = (
        [
            AddrRange(
                0,
                size=1 << 36,
                intlvHighBit=bank_low_bit + bits - 1,
                intlvBits=bits,
                intlvMatch=bank,
            )
        ]
        if bits
        else []
    )
    tag, data, response = CACHE_TIMING[level]
    kwargs = dict(
        size=f"{bank_bytes}B",
        assoc=spec["assoc"],
        tag_latency=tag,
        data_latency=data,
        response_latency=response,
        mshrs=spec["mshrs"] // bank_count,
        tgts_per_mshr=20,
        write_buffers=8,
        sequential_access=False,
        replacement_policy=LRURP(),
        clusivity="mostly_incl",
        writeback_clean=False,
        is_read_only=(level == "l1i"),
        prefetcher=_prefetcher(spec["prefetch"]),
    )
    if ranges:
        kwargs["addr_ranges"] = ranges
    return Cache(**kwargs)


def _xbar(cls):
    return cls(
        width=32,
        frontend_latency=1,
        forward_latency=1,
        response_latency=1,
        header_latency=1,
        snoop_filter=SnoopFilter(lookup_latency=1, max_capacity="32MiB"),
    )


def _display_size(size):
    for suffix, scale in (
        ("GiB", 1 << 30),
        ("MiB", 1 << 20),
        ("KiB", 1 << 10),
    ):
        if size >= scale:
            return f"{size / scale:g} {suffix}"
    return f"{size} B"


def _print_config(profile):
    config_path = Path(m5.options.outdir) / m5.options.dump_config
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(config_path):
        raise RuntimeError(f"Missing generated configuration: {config_path}")
    cpu = config["system.cpu"]
    for name, expected in profile["cpu"].items():
        if cpu[name] != str(expected):
            raise RuntimeError(f"{name}: expected {expected}, got {cpu[name]}")

    period = int(config[cpu["clk_domain"]]["clock"].split()[0])
    frequency = m5.ticks.fromSeconds(1.0) / period / 1e9
    isa = config["system.cpu.isa"]
    queues = [
        section
        for section in config.sections()
        if config[section].get("type") == "IQUnit"
    ]
    iq_entries = sum(int(config[section]["numEntries"]) for section in queues)
    items = [
        ("Model", profile["name"]),
        ("Config", str(config_path)),
        ("CPU type", cpu["type"]),
        ("Frequency", f"{frequency:g} GHz"),
        ("Memory mode", config["system"]["mem_mode"]),
        ("Vector length", f"{isa['vlen']} bits"),
        ("Fetch width", cpu["fetchWidth"]),
        ("Decode width", cpu["decodeWidth"]),
        ("Rename width", cpu["renameWidth"]),
        ("Issue width", cpu["issueWidth"]),
        ("Commit width", cpu["commitWidth"]),
        ("ROB entries", cpu["numROBEntries"]),
        ("IQ entries", f"{iq_entries} ({len(queues)} queues)"),
        (
            "Load / store queue entries",
            f"{cpu['LQEntries']} / {cpu['SQEntries']}",
        ),
        ("Cache line", f"{config['system']['cache_line_size']} B"),
    ]
    for label, prefix in (
        ("L1 instruction cache", "system.cpu.icache"),
        ("L1 data cache", "system.cpu.dcache"),
        ("L2 cache", "system.l2"),
        ("L3 / LLC", "system.l3"),
    ):
        banks = [
            config[section]
            for section in config.sections()
            if section.startswith(prefix)
            and config[section].get("type") == "Cache"
        ]
        if not banks:
            items.append((label, "None"))
            continue
        size = sum(int(bank["size"]) for bank in banks)
        detail = f"{_display_size(size)}, {banks[0]['assoc']}-way"
        if len(banks) > 1:
            detail += f", {len(banks)} banks"
        prefetch = any(bank["prefetcher"] != "Null" for bank in banks)
        detail += f", prefetch {'on' if prefetch else 'off'}"
        items.append((label, detail))

    dram = config["system.mem_ctrl.dram"]
    capacity = (
        int(dram["device_size"])
        * int(dram["devices_per_rank"])
        * int(dram["ranks_per_channel"])
    )
    items.append(("Memory capacity", _display_size(capacity)))
    print("CPU configuration:")
    for label, value in items:
        print(f"  - {label}: {value}")
    print(f"Beginning simulation: {profile['name']}", flush=True)


def run_model(profile):
    parser = argparse.ArgumentParser(description=profile["name"])
    parser.add_argument("binary", help="RV64 bare-metal ELF")
    args = parser.parse_args()

    system = RiscvSystem(mem_mode="timing", cache_line_size=64)
    system.mem_ranges = [AddrRange(0x80000000, size="8GiB")]
    system.voltage_domain = VoltageDomain(voltage="1V")
    system.clk_domain = SrcClockDomain(
        clock="2GHz", voltage_domain=system.voltage_domain
    )
    system.workload = RiscvBareMetal(
        bootloader=args.binary,
        semihosting=RiscvSemihosting(cmd_line=args.binary),
    )
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

    system.cpu = RiscvO3CPU(**CPU_TIMING, **CPU_POLICY, **profile["cpu"])
    system.cpu.dispatchWidth = profile["cpu"]["renameWidth"]
    system.cpu.fetchTargetWidth = profile["cpu"]["fetchBufferSize"]
    system.cpu.cacheLoadPorts = 2
    system.cpu.cacheStorePorts = 1 if profile["name"].startswith("v5") else 2
    system.cpu.instQueues = [
        IQUnit(numEntries=entries, fuPool=FUPool(FUList=_units(tag, count)))
        for _, entries, tag, count in profile["queues"]
    ]
    system.cpu.branchPred = _predictor(profile["branch"])
    system.cpu.createInterruptController()
    system.cpu.createThreads()
    isa = system.cpu.isa[0]
    isa.riscv_profile = "RVA20S64"
    isa.extra_extensions = ["Zba", "Zbb", "Zbc", "Zbs"] + (
        ["V"] if profile["vector"] else []
    )
    isa.vlen = 128
    isa.elen = 64
    isa.privilege_mode_set = "MSU"

    system.cpu.addPrivateSplitL1Caches(
        _cache("l1i", profile["caches"]["l1i"]),
        _cache("l1d", profile["caches"]["l1d"]),
    )
    system.l1bus = _xbar(L2XBar)
    system.cpu.connectBus(system.l1bus)
    upstream = system.l1bus
    for level in ("l2", "l3"):
        spec = profile["caches"][level]
        if spec is None:
            continue
        caches = [_cache(level, spec, bank) for bank in range(spec["banks"])]
        setattr(system, level, caches)
        if level == "l3":
            downstream = system.membus
        else:
            system.l2bus = _xbar(L2XBar)
            downstream = system.l2bus
        for cache in caches:
            cache.cpu_side = upstream.mem_side_ports
            cache.mem_side = downstream.cpu_side_ports
        upstream = downstream
    system.cpu.mmu.pma_checker = PMAChecker(
        uncacheable=[
            *system.platform._on_chip_ranges(),
            *system.platform._off_chip_ranges(),
        ]
    )
    # The reset page is outside DRAM, keeping the DIMM capacity exact.
    system.reset_mem = SimpleMemory(
        range=AddrRange(0x7FFFF000, size="4KiB"),
        latency="1ns",
        latency_dist="None",
        bandwidth="32GiB/s",
    )
    system.reset_mem.port = system.membus.mem_side_ports
    system.mem_ctrl = MemCtrl(
        mem_sched_policy="frfcfs",
        write_high_thresh_perc=85,
        write_low_thresh_perc=50,
        min_writes_per_switch=16,
        min_reads_per_switch=16,
        dram=DDR4_2400_8x8(
            range=system.mem_ranges[0],
            ranks_per_channel=1,
            read_buffer_size=64,
            write_buffer_size=128,
        ),
    )
    system.mem_ctrl.port = system.membus.mem_side_ports
    root = Root(full_system=True, system=system)
    m5.instantiate()
    _print_config(profile)
    event = m5.simulate()
    print(
        f"Exiting @ tick {m5.curTick()} because {event.getCause()}.",
        flush=True,
    )
    raise SystemExit(event.getCode())
