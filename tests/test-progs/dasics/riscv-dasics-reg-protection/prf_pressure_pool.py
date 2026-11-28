# SPDX-License-Identifier: BSD-3-Clause
"""Replay integer free-list activity for the ordinary and protected gate bodies."""

from prf_pressure_analyze import (
    decode_prf,
    lines,
    require,
)


def pressure_window(trace, symbols, call, int_regs):
    """Measure [accepted load request, matching response) in trace order."""
    load_sn = call["load_sn"]
    begin = symbols["prf_writes_begin"]
    end = symbols["prf_writes_end"]
    send = call["load_send_tick"]
    response = call["load_response_tick"]
    period, remainder = divmod(response - send, call["load_wait_cycles"])
    require(period > 0 and remainder == 0, "Invalid load timing")

    free = None
    free_at_send = free_at_response = minimum = minimum_tick = None
    call_minimum = None
    in_call = waiting = False
    wait_rejects = call_rejects = 0
    enqueues = dequeues = 0
    renamed = set()
    retired = {}
    with lines(trace) as source:
        for line in source:
            enqueue = ": Enqueue integer P" in line
            if enqueue or ": Dequeue integer P" in line:
                if free is None:
                    continue
                free += 1 if enqueue else -1
                require(0 <= free <= int_regs, "Out-of-range free-list size")
                if in_call:
                    call_minimum = min(free, call_minimum)
                if waiting:
                    enqueues += int(enqueue)
                    dequeues += int(not enqueue)
                    if free < minimum:
                        minimum = free
                        minimum_tick = int(line.partition(":")[0])
                continue
            if ": PRF " not in line:
                continue
            tick, kind, event = decode_prf(line)
            if "free" in event:
                # The logger may start after initial architectural assignment.
                # Once anchored, each later sample must agree with the FIFO.
                if free is None:
                    free = event["free"]
                require(free == event["free"], "Free-list replay mismatch")
            pc, sn = event.get("pc"), event["sn"]
            if kind == "retire":
                if pc == call["call_pc"]:
                    require(
                        not in_call
                        and tick == call["call_tick"]
                        and free is not None,
                        "Unexpected caller transfer",
                    )
                    in_call, call_minimum = True, free
                elif in_call and pc == call["resume_pc"]:
                    require(
                        tick == call["resume_tick"] and not waiting,
                        "Unexpected caller continuation",
                    )
                    in_call = False
                elif in_call and begin <= pc < end:
                    require(
                        pc not in retired and sn > load_sn,
                        "Duplicate pressure write",
                    )
                    retired[pc] = sn
            elif sn == load_sn and kind in ("send", "response"):
                require(
                    in_call
                    and pc == call["load_pc"]
                    and event["addr"] == call["cold_addr"],
                    "Packet does not belong to the measured cold load",
                )
                if kind == "send":
                    require(
                        free_at_send is None and tick == send,
                        "Invalid load send",
                    )
                    waiting = True
                    free_at_send = minimum = free
                    minimum_tick = tick
                else:
                    require(
                        waiting and tick == response, "Invalid load response"
                    )
                    waiting = False
                    free_at_response = free
            elif in_call and kind == "reject":
                require(
                    event["need"] > free,
                    "Spurious integer allocation rejection",
                )
                call_rejects += 1
                wait_rejects += int(waiting)
            elif (
                waiting
                and kind == "rename"
                and begin <= pc < end
                and sn > load_sn
            ):
                require(
                    event["old"] != event["new"], "Missing integer allocation"
                )
                renamed.add((pc, sn))

    require(
        free_at_response is not None and not in_call and not waiting,
        "Incomplete measured call",
    )
    require(
        free_at_send + enqueues - dequeues == free_at_response,
        "Free-list balance mismatch",
    )
    require(
        set(retired) == set(range(begin, end, 4)), "Incomplete pressure stream"
    )
    # Only count Rename events of the dynamic writes that eventually retired.
    valid = renamed & set(retired.items())
    return dict(
        free_at_send=free_at_send,
        free_before_response=free_at_response,
        min_free=minimum,
        min_tick=minimum_tick,
        first_min_cycle=(minimum_tick - send) // period,
        enqueues_in_wait=enqueues,
        dequeues_in_wait=dequeues,
        integer_rejects_in_wait=wait_rejects,
        younger_writes_in_wait=len(valid),
        squashed_pressure_renames_in_wait=len(renamed - valid),
        min_free_in_complete_call=call_minimum,
        integer_rejects_in_complete_call=call_rejects,
    )
