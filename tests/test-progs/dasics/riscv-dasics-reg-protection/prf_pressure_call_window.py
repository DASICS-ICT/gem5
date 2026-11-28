# SPDX-License-Identifier: BSD-3-Clause
"""Measure one complete cold Sv39 call, using retired PCs as its boundaries."""

from pathlib import Path

from prf_pressure_analyze import (
    SAVED,
    SCRATCH,
    decode_prf,
    lines,
    require,
)


def extract_call(trace, symbols, transfer_pc, count, mode, period=500):
    """Use the caller's actual jump and first resumed instruction."""
    require(mode in ("sw", "hw") and count in (0, 12), "invalid gate or count")
    require(period > 0, "invalid CPU clock")
    trace = Path(trace)
    resume = symbols["prf_measure_return"]
    load_pc = symbols["prf_slow_load"]
    cold = symbols["prf_cold_word"]
    require(transfer_pc + 4 == resume, "unexpected caller continuation")

    measured = []
    warm = 0
    active = False
    with lines(trace) as stream:
        for line in stream:
            if ": PRF retire " not in line:
                continue
            tick, _, event = decode_prf(line)
            pc, sn = event["pc"], event["sn"]
            if pc == transfer_pc:
                require(not measured and warm == 4, "unexpected measured call")
                active = True
            if active:
                measured.append((pc, sn, tick))
                if pc == resume:
                    active = False
            elif pc == load_pc:
                require(not measured, "extra B invocation after measured call")
                warm += 1

    require(measured and not active, "missing complete call")
    pcs = [pc for pc, _, _ in measured]
    require(len(pcs) == len(set(pcs)), "repeated PC in straight-line call")
    require(
        all(
            a[1] < b[1] and a[2] <= b[2]
            for a, b in zip(measured, measured[1:])
        ),
        "retirements out of order",
    )
    require(
        pcs[:2] == [transfer_pc, symbols["protected_gate"]]
        and pcs[-1] == resume,
        "unexpected A gate entry or return",
    )
    # Every instruction between the two gate markers belongs to the B body,
    # including the callee's ret. No warm-up or speculative PC enters this list.
    first = symbols["prf_clobber_begin"]
    writes, end = symbols["prf_writes_begin"], symbols["prf_writes_end"]
    require(
        first == symbols["callee_entry"]
        and load_pc == first + 12 * 4
        and writes == load_pc + 4
        and end == writes + 128 * 4
        and pcs[
            pcs.index(symbols["gate_call"])
            + 1 : pcs.index(symbols["return_gate"])
        ]
        == list(range(first, end + 4, 4)),
        "B entry writes, load, pressure stream or return differ",
    )
    by_pc = {pc: (sn, tick) for pc, sn, tick in measured}
    load_sn, load_retire = by_pc[load_pc]
    call_sn, call = by_pc[transfer_pc]
    resume_sn, returned = by_pc[resume]
    packets = []
    owners = {"protect": [], "hold": [], "release": []}
    entry_writes = {}
    entry_sns = {by_pc[pc][0] for pc in range(first, load_pc, 4)}
    with lines(trace) as stream:
        for line in stream:
            if ": PRF " not in line or ": PRF retire " in line:
                continue
            tick, kind, event = decode_prf(line)
            sn = event["sn"]
            if sn == load_sn and kind in ("send", "response"):
                require(
                    event["pc"] == load_pc
                    and event["addr"] == cold
                    and event["size"] == 8,
                    "LSQ packet differs from the measured aligned load",
                )
                packets.append((kind, tick))
            elif sn in entry_sns and kind == "rename":
                require(
                    sn not in entry_writes, "duplicate integer destination"
                )
                entry_writes[sn] = event["arch"]
            elif call_sn < sn < resume_sn and kind in owners:
                owners[kind].append((event["arch"], event["phys"]))

    require(
        [kind for kind, _ in packets] == ["send", "response"]
        and cold % 8 == 0,
        "expected one accepted load and one full response",
    )
    require(
        [entry_writes.get(sn) for sn in sorted(entry_sns)]
        == list(SAVED if count else SCRATCH),
        "unexpected destinations in the twelve B entry writes",
    )
    saved = owners["protect"]
    if mode == "sw":
        require(
            not any(owners.values()),
            "software gate emitted a protection record",
        )
    else:
        require(
            sorted(r for r, _ in saved) == sorted(SAVED)
            and len({p for _, p in saved}) == len(SAVED)
            and sorted(owners["release"]) == sorted(saved)
            and sorted(owners["hold"]) == (sorted(saved) if count else []),
            "hardware gate history differs from the selected B overwrites",
        )

    send, response = (tick for _, tick in packets)
    b_ret = by_pc[end][1]
    times = (call, send, response, b_ret, returned)
    require(
        call <= send < response <= load_retire <= b_ret <= returned,
        "invalid load interval",
    )
    require(
        all((t - call) % period == 0 for t in times), "fractional CPU cycle"
    )
    return dict(
        call_pc=transfer_pc,
        resume_pc=resume,
        call_tick=call,
        resume_tick=returned,
        cycles=(returned - call) // period,
        retired_instructions=len(measured) - 1,
        load_pc=load_pc,
        load_sn=load_sn,
        cold_addr=cold,
        load_size=8,
        load_send_tick=send,
        load_response_tick=response,
        b_ret_tick=b_ret,
        before_send_cycles=(send - call) // period,
        load_wait_cycles=(response - send) // period,
        after_response_cycles=(returned - response) // period,
        response_to_b_ret_cycles=(b_ret - response) // period,
        b_ret_to_resume_cycles=(returned - b_ret) // period,
        entry_writes=len(entry_writes),
        pressure_writes=(end - writes) // 4,
        protected_mappings=len(saved),
        deferred_mappings=len(owners["hold"]),
        released_mappings=len(owners["release"]),
    )
