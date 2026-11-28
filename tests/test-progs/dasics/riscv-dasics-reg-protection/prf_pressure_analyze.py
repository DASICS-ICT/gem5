# SPDX-License-Identifier: BSD-3-Clause
"""Replay a single cold load, committed overwrites and integer free-list activity."""

import argparse
import configparser
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

from elftools.elf.elffile import ELFFile

SAVED = (8, 9, *range(18, 28))
SCRATCH = (5, 6, 7, 28, 29, 30, 31, 11, 12, 13, 14, 15)
PHASES = ("before_send", "in_wait", "after_response")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def program(elf, k):
    with elf.open("rb") as f:
        image = ELFFile(f)
        syms = {
            s.name: s["st_value"]
            for s in image.get_section_by_name(".symtab").iter_symbols()
        }
        sec = image.get_section_by_name(".text.trusted")
        text, base = sec.data(), sec["sh_addr"]
        leaves = [
            base + i
            for i in range(syms["return_gate"] - base, len(text) - 3, 4)
            if text[i : i + 4] == b"\x0b\x50\x00\x00"
        ]
        require(len(leaves) == 1, "expected one LEAVE in the return gate")
        sec = image.get_section_by_name(".text.untrusted")
        text, base = sec.data(), sec["sh_addr"]
    entry, load = syms["prf_clobber_begin"], syms["prf_slow_load"]
    begin, end = syms["prf_writes_begin"], syms["prf_writes_end"]
    require(
        load == entry + 48 and begin == load + 4 and end == begin + 512,
        "unexpected B layout",
    )
    for i, dest in enumerate(SAVED if k == 12 else SCRATCH):
        n = entry + 4 * i - base
        word = int.from_bytes(text[n : n + 4], "little")
        require(
            word == ((0x101 + i) << 20 | dest << 7 | 0x13),
            f"incorrect entry write {i}",
        )
    return syms, leaves[0]


def lines(path):
    opener = gzip.open if path.suffix == ".gz" else open
    return opener(path, "rt", encoding="utf-8")


def decode_prf(line):
    tick, _, msg = line.split(": ", 2)
    _, kind, *fields = msg.split()
    data = {
        key: int(raw, 0)
        for key, raw in (item.split("=", 1) for item in fields)
    }
    require(data["tid"] == 0, "expected a single hardware thread")
    return int(tick), kind, data


def measured_retirements(trace, syms, leave):
    # Sequence numbers select the measured call even when younger instructions
    # were renamed before the caller marker itself retired.
    active = False
    retired = {}
    warm = 0
    with lines(trace) as stream:
        for line in stream:
            if ": PRF retire " not in line:
                continue
            _, _, event = decode_prf(line)
            pc, sn = event["pc"], event["sn"]
            if pc == syms["prf_measure_call"]:
                require(not retired, "repeated measured call")
                active = True
            if active:
                require(
                    pc not in retired,
                    f"repeated PC in measured straight-line call: {pc:#x}",
                )
                retired[pc] = sn
                if pc == syms["prf_measure_return"]:
                    active = False
            elif pc == syms["prf_slow_load"]:
                warm += 1
    expected = [
        syms["prf_measure_call"],
        syms["gate_call"] - 4,
        syms["gate_call"],
        *range(syms["prf_clobber_begin"], syms["prf_writes_end"] + 4, 4),
        syms["return_gate"],
        leave,
        syms["prf_measure_return"],
    ]
    seq = [retired[pc] for pc in expected]
    require(
        warm == 4 and not active and all(a < b for a, b in zip(seq, seq[1:])),
        "expected four warm calls and one complete ordered measurement",
    )
    return retired


def analyze(trace, elf, config, k, rob_entries=96, int_regs=128):
    trace, elf, config = map(Path, (trace, elf, config))
    require(k in (0, 12), "clobber must be 0 or 12")
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(config)
    cpu = cfg["system.cpu"]
    require(
        int(cpu["numROBEntries"]) == rob_entries
        and int(cpu["numPhysIntRegs"]) == int_regs,
        f"expected ROB={rob_entries} and {int_regs} integer physical registers",
    )
    period = int(cfg[cpu["clk_domain"]]["clock"])
    syms, leave = program(elf, k)
    retired = measured_retirements(trace, syms, leave)
    load = retired[syms["prf_slow_load"]]
    start, end = syms["prf_writes_begin"], syms["prf_writes_end"]
    call = (
        retired[syms["prf_measure_call"]],
        retired[syms["prf_measure_return"]],
    )
    cold = syms["prf_cold_word"]
    entry_pcs = range(syms["prf_clobber_begin"], syms["prf_slow_load"], 4)
    entries = {retired[pc]: pc for pc in entry_pcs}

    # Keep protection ownership separate from ordinary free-list membership:
    # a register protected but never overwritten does not belong to 'held'.
    protected, held, released = {}, {}, {}
    observed_holds = []
    renamed = set()
    phase_counts = Counter()
    phase_edges = {}
    head_count = rejects = other_rejects = squashed_writes = 0
    send = response = first_head = None
    minimum = None
    free = 0
    calibrated = False
    peak = 0
    key = []
    reject_at_free = Counter()
    first_reject_at_free = {}
    last_reject = None
    entry_renames = {}
    sent_state = response_state = None
    phase = PHASES[0]

    def point(tick, order, label, event=None):
        info = event or {}
        return dict(
            tick=tick,
            trace_line=order,
            event=label,
            sn=info.get("sn"),
            pc=info.get("pc"),
            arch=info.get("arch"),
            phys=info.get("phys", info.get("new")),
            held=len(held),
            free=free,
        )

    with lines(trace) as stream:
        for order, line in enumerate(stream, 1):
            # FreeList logs immediately before each push or pop; there is no
            # other visible event between its log and the queue mutation.
            if ": Enqueue integer P" in line or ": Dequeue integer P" in line:
                free += 1 if ": Enqueue " in line else -1
                if phase == "in_wait" and free < minimum["free"]:
                    tick = int(line.partition(":")[0])
                    minimum = point(
                        tick,
                        order,
                        "free_min",
                        {"phys": int(line.rsplit("P", 1)[1])},
                    )
                continue
            if ": PRF " not in line or ": PRF retire " in line:
                continue
            tick, kind, ev = decode_prf(line)
            sn = ev["sn"]
            if "free" in ev:
                # Some builds start logging after initial RAT assignment.
                # An absolute Rename sample anchors all subsequent FIFO deltas.
                if not calibrated:
                    free, calibrated = ev["free"], True
                require(
                    free == ev["free"] and 0 <= free <= int_regs,
                    f"line {order}: free-list replay {free} != sample {ev['free']}",
                )
            if kind == "reject" and phase == "in_wait":
                require(
                    ev["need"] > free, "spurious integer allocation rejection"
                )
                reject_at_free[free] += 1
                last_reject = point(tick, order, "integer_rename_reject", ev)
                first_reject_at_free.setdefault(free, last_reject)
                if start <= ev["pc"] < end and retired.get(ev["pc"]) == sn:
                    rejects += 1
                else:
                    other_rejects += 1
            if (
                kind == "rename"
                and start <= ev["pc"] < end
                and retired.get(ev["pc"]) != sn
            ):
                squashed_writes += phase == "in_wait"
                continue
            if not call[0] < sn < call[1]:
                continue
            if kind == "protect":
                require(
                    sn == retired[syms["gate_call"] - 4],
                    "unexpected PROREG owner",
                )
                require(
                    ev["arch"] not in protected, "duplicate protected register"
                )
                protected[ev["arch"]] = ev["phys"]
            elif kind == "hold":
                arch = ev["arch"]
                require(
                    sn in entries
                    and arch in SAVED
                    and protected.get(arch) == ev["phys"]
                    and arch not in held
                    and entry_renames.get(sn) == (arch, ev["phys"]),
                    f"line {order}: invalid deferred owner",
                )
                held[arch] = ev["phys"]
                row = point(
                    tick, order, "defer_reclaim", dict(ev, pc=entries[sn])
                )
                observed_holds.append(row)
                key.append(row)
                if phase == "in_wait":
                    peak = max(peak, len(held))
            elif kind == "release":
                arch = ev["arch"]
                require(
                    sn == retired[leave]
                    and arch not in released
                    and protected.get(arch) == ev["phys"],
                    "unexpected LEAVE ownership",
                )
                released[arch] = ev["phys"]
                held.pop(arch, None)
                if len(released) == 12:
                    key.append(
                        point(tick, order, "leave_release_complete", ev)
                    )
            elif sn == load and kind == "head":
                if first_head is None:
                    first_head = point(
                        tick, order, "load_at_blocked_rob_head", ev
                    )
                    key.append(first_head)
            elif sn == load and kind in ("send", "response"):
                require(
                    ev["pc"] == syms["prf_slow_load"]
                    and ev["addr"] == cold
                    and cold % 64 == 0
                    and ev["size"] == 8
                    and calibrated,
                    "measured LSQ packet does not match the cold aligned word",
                )
                row = point(tick, order, "load_" + kind, ev)
                key.append(row)
                if kind == "send":
                    require(
                        send is None and phase == "before_send",
                        "repeated load send",
                    )
                    send, phase = row, "in_wait"
                    minimum = dict(row, event="free_min")
                    peak = len(held)
                    sent_state = dict(held)
                else:
                    require(phase == "in_wait", "unmatched load completion")
                    response, phase = row, "after_response"
                    response_state = dict(held)
            elif kind == "rename" and sn in entries:
                require(
                    ev["pc"] == entries[sn] and sn not in entry_renames,
                    "entry write Rename does not match retirement",
                )
                entry_renames[sn] = ev["arch"], ev["old"]
            elif kind == "rename" and start <= ev["pc"] < end:
                require(
                    sn > load and sn not in renamed and ev["old"] != ev["new"],
                    "pressure instruction did not allocate a unique integer destination",
                )
                renamed.add(sn)
                phase_counts[phase] += 1
                if phase == "in_wait" and first_head is not None:
                    head_count += 1
                row = point(tick, order, "pressure_rename_" + phase, ev)
                edges = phase_edges.setdefault(phase, [row, row])
                edges[-1] = row

    require(
        send is not None
        and response is not None
        and response["tick"] > send["tick"],
        "expected a returned external load request",
    )
    require(
        set(protected) == set(SAVED)
        and len(set(protected.values())) == 12
        and released == protected
        and not held,
        "protected slots were not fully restored",
    )
    require(
        len(entry_renames) == 12
        and len(observed_holds) == k
        and len(renamed) == 128,
        "incomplete hold or Rename trace",
    )
    for edge in phase_edges.values():
        key.append(edge[0])
        if edge[1] != edge[0]:
            key.append(edge[1])
    if first_reject_at_free:
        first_reject = min(
            first_reject_at_free.values(), key=lambda row: row["trace_line"]
        )
        chosen = {
            row["trace_line"]: row
            for row in [
                first_reject,
                last_reject,
                first_reject_at_free.get(minimum["free"]),
            ]
            if row
        }
        key.extend(chosen.values())
    else:
        first_reject = None
    key.append(minimum)
    return dict(
        clobber=k,
        measured_load_sn=load,
        cold_addr=cold,
        cpu_period_ticks=period,
        load_send_tick=send["tick"],
        load_response_tick=response["tick"],
        load_wait_cycles=(response["tick"] - send["tick"]) / period,
        load_at_rob_head_tick=first_head["tick"] if first_head else None,
        delayed_at_send=send["held"],
        delayed_peak_in_wait=peak,
        delayed_before_response=response["held"],
        held_at_send=sent_state,
        held_before_response=response_state,
        delayed_after_leave=len(held),
        delayed_origins=observed_holds,
        younger_writes={name: phase_counts[name] for name in PHASES},
        younger_writes_at_blocked_head=head_count,
        squashed_pressure_renames_in_wait=squashed_writes,
        free_at_send=send["free"],
        free_before_response=response["free"],
        min_free=minimum["free"],
        min_tick=minimum["tick"],
        held_at_first_min=minimum["held"],
        integer_rejects_in_wait=rejects + other_rejects,
        pressure_rejects_in_wait=rejects,
        integer_rejects_at_minimum=reject_at_free[minimum["free"]],
        first_integer_rejection=first_reject,
        boundary_order="trace_line within a common tick; send included, response excluded",
        key_trace=sorted(key, key=lambda row: row["trace_line"]),
    )


def save(result, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    rows = result["key_trace"]
    with (outdir / "key-trace.tsv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("trace", "elf", "config", "outdir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--clobber", type=int, choices=(0, 12), required=True)
    parser.add_argument(
        "--rob-entries", type=int, choices=(96, 128), default=96
    )
    parser.add_argument(
        "--int-regs", type=int, choices=(128, 160), default=128
    )
    args = parser.parse_args()
    result = analyze(
        args.trace,
        args.elf,
        args.config,
        args.clobber,
        args.rob_entries,
        args.int_regs,
    )
    save(result, args.outdir)
