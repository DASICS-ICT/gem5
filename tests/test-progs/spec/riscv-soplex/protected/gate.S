/* SPDX-License-Identifier: BSD-3-Clause */
#include "../../../dasics/riscv-dasics-reg-protection/src/context.h"
#include "../../../dasics/riscv-dasics-printf/full_policy.inc"

    .equ context_base, 0x8b4
    .equ lib_cfg, 0x880
    .option norelax
    .option norvc
    .section .text.strtok_gate,"ax",@progbits
    .balign 8
    .globl strtok_gate, gate_call, gate_return, gate_ret
    .type strtok_gate,@function

    .macro grant_symbols slot, lower, upper
    lla     t1, \lower
    csrw    (0x890 + 2 * \slot), t1
    lla     t1, \upper
    csrw    (0x891 + 2 * \slot), t1
    .endm

/* readLine supplies either base + 1 or NULL and a single space delimiter.
 * The trusted caller passes the same aligned row in a2 on continuations.
 */
strtok_gate:
    andi    t1, a2, 7
    bnez    t1, .Lbad_row
    beqz    a0, .Lsave
    addi    t1, a2, 1
    bne     a0, t1, .Lbad_row
.Lsave:
    csrr    t0, context_base
    sd      ra, CTX_RA(t0)
    sd      sp, CTX_SP(t0)
    sd      gp, CTX_GP(t0)
    sd      tp, CTX_TP(t0)
    frcsr   t1
    sd      t1, CTX_FCSR(t0)

    csrw    0x890, a2
    addi    t1, a2, 256
    csrw    0x891, t1
    grant_symbols 1, __strtok_b_ro_start, __strtok_b_ro_end
    grant_symbols 2, __strtok_b_rw_start, __strtok_b_rw_end
    lla     t1, __dasics_stack_bottom
    csrw    0x896, t1
    lla     sp, __dasics_stack_top
    csrw    0x897, sp
    /* Slots from low to high: row RW, constants RO, cursor RW, stack RW. */
    li      t1, 0xbbab
    csrw    lib_cfg, t1

    lla     a1, b_delim
    csrwi   fcsr, 0
    li      gp, 0
    li      tp, 0
    .irp i,2,3,4,5,6,7
    li      a\i, 0
    .endr
    mv      ra, t0
    full_enter
    lla     ra, b_strtok
gate_call:
    .insn   i 0x0b, 1, ra, ra, 0
gate_return:
    /* Revoke access between calls while preserving B's saved cursor. */
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
.Lbad_row:
    unimp
    .size strtok_gate, .-strtok_gate
    .section .note.GNU-stack,"",@progbits
