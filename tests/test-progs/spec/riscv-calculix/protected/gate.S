/* SPDX-License-Identifier: BSD-3-Clause */
#include "../../../dasics/riscv-dasics-reg-protection/src/context.h"

#if USE_INT_PROREG != USE_FP_PROREG
#error The fmod hardware gate protects both the integer and FP saved registers
#endif

    .equ CONTEXT_BASE, 0x8b4
    .equ LIB_CFG,      0x880
    .equ TABLE_LO,     0x890
    .equ TABLE_HI,     0x891
    .equ TABLE_PTR_LO, 0x892
    .equ TABLE_PTR_HI, 0x893
    .equ STACK_LO,     0x894
    .equ STACK_HI,     0x895
    /* Slots 0 and 1 allow reads, slot 2 allows reads and writes. */
    .equ LIB_PERMISSIONS, 0xbaa
    .equ LIB_VALID_BITS,  0x888

    .option norelax
    .option norvc
    .section .text.fmod_gate,"ax",@progbits
    .balign 4

    /* t0 always names A's trusted frame during these spills and reloads. */
    .macro saved_regs gpr_op, fpr_op
    .irp i,0,1,2,3,4,5,6,7,8,9,10,11
    \gpr_op s\i,  (CTX_GPR_SAVE + 8 * \i)(t0)
    .endr
    .irp i,0,1,2,3,4,5,6,7,8,9,10,11
    \fpr_op fs\i, (CTX_FPR_SAVE + 8 * \i)(t0)
    .endr
    .endm

    .globl dasics_fmod_gate
    .type dasics_fmod_gate, @function
dasics_fmod_gate:
    csrr    t0, CONTEXT_BASE
    sd      ra, CTX_RA(t0)
    sd      sp, CTX_SP(t0)
    sd      gp, CTX_GP(t0)
    sd      tp, CTX_TP(t0)
    csrr    t1, fcsr
    sd      t1, CTX_FCSR(t0)
#if !USE_INT_PROREG
    saved_regs sd, fsd
#endif

    lla     t1, __dasics_ro_start
    csrw    TABLE_LO, t1
    lla     t1, __dasics_ro_end
    csrw    TABLE_HI, t1
    /* The helpers load the table address from this single GOT entry. */
1:  auipc   t1, %got_pcrel_hi(dasics_fmod_table)
    addi    t1, t1, %pcrel_lo(1b)
    csrw    TABLE_PTR_LO, t1
    addi    t1, t1, 8
    csrw    TABLE_PTR_HI, t1
    lla     t1, __dasics_stack_bottom
    csrw    STACK_LO, t1
    lla     sp, __dasics_stack_top
    csrw    STACK_HI, sp
    li      t1, LIB_PERMISSIONS
    csrw    LIB_CFG, t1
    csrwi   fcsr, 0

    /* LP64D passes fmod(x, y) in fa0/fa1, with no integer arguments. */
    .irp reg,gp,tp,t0,t1,t2,t3,t4,t5,t6,a0,a1,a2,a3,a4,a5,a6,a7
    li      \reg, 0
    .endr
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fa2,fa3,fa4,fa5,fa6,fa7
    fmv.d.x \reg, zero
    .endr
#if USE_INT_PROREG
    .globl dasics_fmod_proreg_g, dasics_fmod_proreg_f
dasics_fmod_proreg_g:
    .word   0xfff0300b              /* PROREG.G.I 0xfff */
dasics_fmod_proreg_f:
    .word   0xfff0400b              /* PROREG.F.I 0xfff */
#else
    .irp i,0,1,2,3,4,5,6,7,8,9,10,11
    li      s\i, 0
    fmv.d.x fs\i, zero
    .endr
#endif
    .globl dasics_fmod_call, dasics_fmod_return, dasics_fmod_ret
dasics_fmod_call:
    .word   dasics_fmod_call_encoding
dasics_fmod_return:
    /* Recover A's frame without trusting a register or the stack from B. */
    csrr    t0, CONTEXT_BASE
    li      t1, LIB_VALID_BITS
    csrc    LIB_CFG, t1
#if USE_INT_PROREG
    .globl dasics_fmod_leave
dasics_fmod_leave:
    .word   0x0000500b              /* LEAVE */
#else
    saved_regs ld, fld
#endif
    ld      t1, CTX_FCSR(t0)
    csrw    fcsr, t1
    ld      gp, CTX_GP(t0)
    ld      tp, CTX_TP(t0)
    ld      sp, CTX_SP(t0)
    ld      ra, CTX_RA(t0)
dasics_fmod_ret:
    ret
    .size dasics_fmod_gate, .-dasics_fmod_gate
    /* Give ld the same input size in both builds before it relaxes calls.
     * The unused tail follows ret and is outside the function's extent.
     */
    .org dasics_fmod_gate + 640, 0
    .globl dasics_fmod_gate_slot_end
dasics_fmod_gate_slot_end:

    .section .dasics.fmod.error,"ax",@progbits
    .balign 4
    .globl dasics_fmod_error
    .type dasics_fmod_error, @function
dasics_fmod_error:
    /* Make an unexpected domain error observable before trapping in B. */
    nop
    .word   0
    .size dasics_fmod_error, .-dasics_fmod_error

    .section .note.GNU-stack,"",@progbits
