/* SPDX-License-Identifier: BSD-3-Clause */
#include "../../../dasics/riscv-dasics-reg-protection/src/context.h"
#include "../../../dasics/riscv-dasics-printf/full_policy.inc"

    .equ context_base, 0x8b4
    .equ lib_cfg, 0x880
    .option norelax
    .option norvc
    .section .text.pow_gate,"ax",@progbits
    .balign 8
    .globl pow_gate, gate_call, gate_return, gate_ret
    .type pow_gate,@function
pow_gate:
    csrr    t0, context_base
    sd      ra, CTX_RA(t0)
    sd      sp, CTX_SP(t0)
    sd      gp, CTX_GP(t0)
    sd      tp, CTX_TP(t0)
    frcsr   t1
    sd      t1, CTX_FCSR(t0)

    /* pow reads its own tables and spills to B's stack. */
    lla     t1, __pow_b_ro_start
    csrw    0x890, t1
    lla     t1, __pow_b_ro_end
    csrw    0x891, t1
    lla     t1, __dasics_stack_bottom
    csrw    0x892, t1
    lla     sp, __dasics_stack_top
    csrw    0x893, sp
    li      t1, 0xba
    csrw    lib_cfg, t1
    csrwi   fcsr, 0

    /* LP64D passes both doubles in fa0/fa1. Clear the other caller-saved
     * registers that are outside the masks handled by full_enter.
     */
    .irp reg,gp,tp,a0,a1,a2,a3,a4,a5,a6,a7
    li      \reg, 0
    .endr
    .irp reg,ft7,ft8,ft9,ft10,ft11,fa2,fa3,fa4,fa5,fa6,fa7
    fmv.d.x \reg, zero
    .endr
    mv      ra, t0
    full_enter
    lla     ra, b_pow
gate_call:
    .insn   i 0x0b, 1, ra, ra, 0
gate_return:
    /* Keep fa0 as pow's scalar result while restoring A's private state. */
    csrw    lib_cfg, zero
    csrr    ra, context_base
    full_leave
    ld      t0, CTX_FCSR(ra)
    fscsr   t0
    ld      sp, CTX_SP(ra)
    ld      gp, CTX_GP(ra)
    ld      tp, CTX_TP(ra)
    ld      ra, CTX_RA(ra)
gate_ret:
    ret
    .size pow_gate, .-pow_gate
    .section .note.GNU-stack,"",@progbits
