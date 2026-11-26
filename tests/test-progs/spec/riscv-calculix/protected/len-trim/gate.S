/* SPDX-License-Identifier: BSD-3-Clause */
#include "../../../../dasics/riscv-dasics-reg-protection/src/context.h"
#include "../../../../dasics/riscv-dasics-printf/full_policy.inc"

    .equ context_base, 0x8b4
    .equ lib_cfg, 0x880
    .option norelax
    .option norvc
    .section .text.trim_gate,"ax",@progbits
    .balign 8
    .globl trim_gate, gate_call, gate_return, gate_ret
    .type trim_gate,@function
/* RV64 libgfortran ABI: a0 = character count, a1 = source address.
 * This getnewline_ call always supplies exactly one character. */
trim_gate:
    li      t0, 1
    bne     a0, t0, .Lbad_length
    csrr    t0, context_base
    sd      ra, CTX_RA(t0)
    sd      sp, CTX_SP(t0)
    sd      gp, CTX_GP(t0)
    sd      tp, CTX_TP(t0)
    frcsr   t1
    sd      t1, CTX_FCSR(t0)

    /* Stage the byte so B cannot read neighboring data in A's input line. */
    lbu     t2, 0(a1)
    lla     a1, __trim_input
    sb      t2, 0(a1)
    csrw    0x890, a1
    addi    t2, a1, 8
    csrw    0x891, t2
    lla     t2, __dasics_stack_bottom
    csrw    0x892, t2
    lla     sp, __dasics_stack_top
    csrw    0x893, sp
    li      t2, 0xba                /* Slot 0: input RO. Slot 1: stack RW. */
    csrw    lib_cfg, t2
    csrwi   fcsr, 0
    li      gp, 0
    li      tp, 0
    .irp i,2,3,4,5,6,7
    li      a\i, 0
    .endr
    mv      ra, t0
    full_enter
    lla     ra, b_len_trim
gate_call:
    .insn   i 0x0b, 1, ra, ra, 0
gate_return:
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
.Lbad_length:
    unimp
    .size trim_gate, .-trim_gate
    .section .note.GNU-stack,"",@progbits
