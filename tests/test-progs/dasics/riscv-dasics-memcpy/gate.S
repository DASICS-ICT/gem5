/* SPDX-License-Identifier: BSD-3-Clause */
#include "../riscv-dasics-reg-protection/src/context.h"

/* The shared printf register checks use a2/a3 as scratch. memcpy uses a2
 * for its length and a3 for the selected B entry, so use a4/a5 instead. */
#define PRINTF_FULL_CHECK 1
#define a2 a4
#define a3 a5
#include "../riscv-dasics-printf/full_policy.inc"
#undef a2
#undef a3

    .equ context_base, 0x8b4
    .equ lib_cfg, 0x880
    .option norelax
    .option norvc
    .text
    .balign 8
    .globl run_memcpy
    .type run_memcpy,@function
/* A passes dst, src, length and B entry in a0-a3. Both arrays are 64B aligned. */
run_memcpy:
    csrr    a4, context_base
    sd      ra, CTX_RA(a4)
    sd      sp, CTX_SP(a4)
    sd      gp, CTX_GP(a4)
    sd      tp, CTX_TP(a4)
    frcsr   a5
    sd      a5, CTX_FCSR(a4)
    /* DASICS grants whole eight-byte blocks. Check padding in A on return. */
    addi    a5, a2, 7
    andi    a5, a5, -8
    csrw    0x890, a1
    add     a6, a1, a5
    csrw    0x891, a6
    csrw    0x892, a0
    add     a6, a0, a5
    csrw    0x893, a6
    lla     a5, __dasics_stack_bottom
    csrw    0x894, a5
    lla     sp, __dasics_stack_top
    csrw    0x895, sp
    lla     a5, __dasics_b_ro_start
    csrw    0x896, a5
    lla     a5, __dasics_b_ro_end
    csrw    0x897, a5
    li      a5, 0xabba              /* RO src/table, RW dst/stack. */
    csrw    lib_cfg, a5
    csrwi   fcsr, 0
    li      gp, 0
    li      tp, 0
    mv      ra, a4
    li      a4, 0
    li      a5, 0
    li      a6, 0
    full_enter
    mv      ra, a3
    li      a3, 0
    .globl gate_call, gate_return
gate_call:
    .insn   i 0x0b, 1, ra, ra, 0    /* DASICSCALL.JR ra,ra,0 */
gate_return:
    csrw    lib_cfg, zero
    csrr    ra, context_base
    full_leave
    .globl a_result
a_result:
    ld      t0, CTX_FCSR(ra)
    fscsr   t0
    ld      sp, CTX_SP(ra)
    ld      gp, CTX_GP(ra)
    ld      tp, CTX_TP(ra)
    ld      ra, CTX_RA(ra)
    ret
    .size run_memcpy, .-run_memcpy

    .globl checked_memcpy
    .type checked_memcpy,@function
/* Preserve the real C caller before seeding all saved and temporary registers. */
checked_memcpy:
    addi    sp, sp, -208
    sd      ra, 0(sp)
    full_transfer sd, fsd, sp, 16, 112
    full_seed
    lla     a3, probe_b_entry
    call    run_memcpy
    full_check_restore
    j       .Lrestore_abi
.Lbad_restore:
    li      a0, 0
.Lrestore_abi:
    full_transfer ld, fld, sp, 16, 112
    ld      ra, 0(sp)
    addi    sp, sp, 208
    ret
    .size checked_memcpy, .-checked_memcpy

    .section .dasics.memcpy.entry,"ax",@progbits
    .balign 8
    .globl probe_b_entry, probe_b_clobber, probe_b_return
    .type probe_b_entry,@function
probe_b_entry:
    full_check_entry
    addi    sp, sp, -16
    sd      ra, 8(sp)
    call    b_memcpy
probe_b_clobber:
    full_clobber
    ld      ra, 8(sp)
    addi    sp, sp, 16
probe_b_return:
    ret
.Lbad_entry:
    li      a0, 0
    ret
    .size probe_b_entry, .-probe_b_entry
    .section .note.GNU-stack,"",@progbits
