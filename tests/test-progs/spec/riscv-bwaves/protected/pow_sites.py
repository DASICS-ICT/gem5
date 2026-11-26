# SPDX-License-Identifier: BSD-3-Clause
"""Locate bwaves pow call sites and verify the linked SW/HW gate pair."""

import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile

SPEC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SPEC / "riscv-soplex/protected"))
from perf_sites import (
    check_policy,
    instructions,
    read_layout,
    transfer,
)

CALLERS = {
    "flux_": ("flux",),
    "jacobian_": ("jacobian_first", "jacobian_second"),
    "shell_": ("shell",),
}
ALIASES = ("pow", "__pow", "__ieee754_pow")
MATH_ERRORS = (
    "__math_oflow",
    "__math_check_uflow",
    "__math_invalid",
    "__math_divzero",
    "__math_check_oflow",
    "__math_uflow",
)
MARKERS = (
    "main",
    "pow_gate",
    "b_pow",
    "b_pow_error",
    "gate_call",
    "gate_return",
    "gate_ret",
    "gate_proreg_g",
    "gate_proreg_f",
    "gate_clr_g",
    "gate_clr_f",
    "gate_leave",
)
SYMBOLS = (
    MARKERS
    + tuple(CALLERS)
    + (
        "__dasics_trusted_start",
        "__dasics_trusted_end",
        "__dasics_untrusted_start",
        "__dasics_untrusted_end",
        "__dasics_context_base",
        "__dasics_stack_bottom",
        "__dasics_stack_top",
        "__pow_b_ro_start",
        "__pow_b_ro_end",
        "b_pow_guard",
        "b_pow_log_table",
        "b_pow_exp_table",
    )
)


def symbols(elf, names):
    with Path(elf).open("rb") as stream:
        table = ELFFile(stream).get_section_by_name(".symtab")
        return {
            name: entries[0]["st_value"]
            for name in names
            if (entries := table.get_symbol_by_name(name))
            and len(entries) == 1
        }


def transfers(body):
    previous = None
    for pc, (word, op, args) in body.items():
        target = transfer(pc, word, op, args, previous)
        if target is not None:
            yield pc, word, target
        previous = pc, word


def call_sites(elf, target, bypass=()):
    sites = {}
    for caller, labels in CALLERS.items():
        body = instructions(elf, caller)
        calls = []
        for pc, word, dest in transfers(body):
            if dest in bypass:
                raise ValueError(
                    f"{caller}: call at {pc:#x} bypasses the gate"
                )
            if dest == target:
                if word & 0xFFF not in (0xEF, 0xE7) or pc + 4 not in body:
                    raise ValueError(
                        f"{pc:#x}: expected a returning RV64 call"
                    )
                calls.append(pc)
        if len(calls) != len(labels):
            raise ValueError(
                f"{caller}: expected {len(labels)} calls, got {calls}"
            )
        sites.update(zip(calls, labels))
    return sites


def ordinary_sites(elf):
    """Track the four callers and exception transfers inside the ordinary libm."""
    names = (*ALIASES, "main", "__stack_chk_fail", *MATH_ERRORS)
    pcs = symbols(elf, names)
    if pcs.keys() != set(names) or len({pcs[s] for s in ALIASES}) != 1:
        raise ValueError("Missing or inconsistent libm pow/error symbols")
    markers = {"main": pcs["main"], "pow": pcs["pow"]}
    error_labels = {
        pcs[name]: f"error_{i}" for i, name in enumerate(MATH_ERRORS)
    }
    error_labels[pcs["__stack_chk_fail"]] = "canary_fail"
    body = instructions(elf, "__ieee754_pow")
    for pc, word, dest in transfers(body):
        if dest in body:
            continue
        label = error_labels.get(dest)
        if label is None or label in markers:
            raise ValueError(f"Unexpected external transfer in pow at {pc:#x}")
        if label == "canary_fail":
            if word & 0xFFF not in (0xEF, 0xE7):
                raise ValueError("Unexpected canary failure call encoding")
        elif body[pc][1] not in ("c.j", "jal") or (
            body[pc][1] == "jal" and word & 0xFFF != 0x6F
        ):
            raise ValueError(f"Expected a tail jump at {pc:#x}")
        markers[label] = pc
    if not set(error_labels.values()).issubset(markers):
        raise ValueError("Missing libm exception transfer sites")
    return markers, call_sites(elf, pcs["pow"])


def discover_pair(sw_elf, hw_elf):
    """Return common marker PCs and the four matched, direct calls into B's gate."""
    sw_elf, hw_elf = Path(sw_elf), Path(hw_elf)
    pair = []
    for path, mode in ((sw_elf, "sw"), (hw_elf, "hw")):
        layout = read_layout(
            path, mode, full=True, common_symbols=SYMBOLS, gate_name="pow_gate"
        )
        check_policy(layout, mode)
        pair.append(layout)
    sw, hw = pair
    if (
        sw.sections != hw.sections
        or sw.blocks != hw.blocks
        or sw.addresses != hw.addresses
    ):
        raise ValueError(
            "Loaded sections or monitored symbols differ outside gate policies"
        )
    pcs = sw.addresses
    if not (
        pcs["__dasics_trusted_start"]
        <= pcs["pow_gate"]
        < pcs["gate_ret"]
        < pcs["__dasics_trusted_end"]
        and pcs["__dasics_untrusted_start"]
        <= pcs["b_pow"]
        < pcs["b_pow_error"]
        < pcs["__dasics_untrusted_end"]
    ):
        raise ValueError(
            "Gate and libm body are outside their expected trust regions"
        )
    bypass = set(symbols(sw_elf, ALIASES).values()) | {pcs["b_pow"]}
    sites = call_sites(sw_elf, pcs["pow_gate"], bypass)
    markers = {name: pcs[name] for name in MARKERS}
    probes = [*markers.values(), *sites, *(pc + 4 for pc in sites)]
    if len(set(probes)) != len(probes):
        raise ValueError("Overlapping pow probe addresses")
    return markers, sites
