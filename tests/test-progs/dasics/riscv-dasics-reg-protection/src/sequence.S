/* SPDX-License-Identifier: BSD-3-Clause */
#define SEQUENCE_CALLS 1
#ifndef SEQUENCE_DENY
#define SEQUENCE_DENY 0
#endif
#ifndef SEQUENCE_SOFTWARE
#define SEQUENCE_SOFTWARE 0
#endif
#if SEQUENCE_FULL
#define SAVED_INDICES 0,1,2,3,4,5,6,7,8,9,10,11
#define SEQUENCE_MASK 0xfff
#define SEQUENCE_GATE_BYTES 384
#else
#define SAVED_INDICES 3
#define SEQUENCE_MASK 0x008
#define SEQUENCE_GATE_BYTES 128
#endif
#if SEQUENCE_ROI
#include <gem5/asm/generic/m5ops.h>
#if ROI_ITERATIONS <= 0 || SEQUENCE_DENY
#error The ROI requires a positive number of complete, fault-free chains
#endif
    .globl roi_iterations, roi_int_proreg, roi_fp_proreg, roi_sequence_mask
    .equ roi_iterations, ROI_ITERATIONS
    .equ roi_int_proreg, (1 - SEQUENCE_SOFTWARE)
    .equ roi_fp_proreg, (1 - SEQUENCE_SOFTWARE)
    .equ roi_sequence_mask, SEQUENCE_MASK
#endif
#include "runtime.inc"

    .equ A_BEFORE_B,    0x11
    .equ A_BEFORE_C,    0x22
    .equ A_FP_BEFORE_B, 0x3ff0000000000011
    .equ A_FP_BEFORE_C, 0xbff0000000000022
    .equ B_LOCAL,       0xbb
    .equ C_LOCAL,       0xcc
    .equ B_FP_LOCAL,    0x7ff81234000000bb
    .equ C_FP_LOCAL,    0x7ff85678000000cc

    .section .text.trusted,"ax",@progbits
#if SEQUENCE_FULL && !SEQUENCE_ROI
    /* Give each slot a distinct value; slot 3 retains its per-call sentinel. */
    .macro seed_all int_bits, fp_bits
    li      t0, (\fp_bits - 3)
    .irp i,SAVED_INDICES
    li      s\i, (\int_bits - 3 + \i)
    fmv.d.x fs\i, t0
    addi    t0, t0, 1
    .endr
    .endm
#endif

    /* Each call supplies only its own code range and private stack. */
    .macro call_domain name, caller_int, caller_fp, local_int, code
#if SEQUENCE_FULL && !SEQUENCE_ROI
    seed_all \caller_int, \caller_fp
#else
    li      s3, \caller_int
    li      t0, \caller_fp
    fmv.d.x fs3, t0
#endif
    la      a0, \name\()_entry
    la      a1, \name\()_end
    la      a2, \name\()_stack_bottom
    la      a3, \name\()_stack_top
    .globl seq_call_\name, seq_after_\name
seq_call_\name:
    call    sequence_gate
seq_after_\name:

#if !SEQUENCE_ROI
    mv      t1, a0
    li      a0, \code
    li      t0, \local_int
    bne     t1, t0, sequence_finish
    li      a0, \code + 1
#if SEQUENCE_FULL
    .irp i,SAVED_INDICES
    li      t0, (\caller_int - 3 + \i)
    bne     s\i, t0, sequence_finish
    .endr
    li      a0, \code + 2
    li      t0, (\caller_fp - 3)
    .irp i,SAVED_INDICES
    fmv.x.d t1, fs\i
    bne     t1, t0, sequence_finish
    addi    t0, t0, 1
    .endr
#else
    li      t0, \caller_int
    bne     s3, t0, sequence_finish
    li      a0, \code + 2
    fmv.x.d t1, fs3
    li      t0, \caller_fp
    bne     t1, t0, sequence_finish
#endif
    li      a0, \code + 3
    la      t0, a_stack_top
    bne     sp, t0, sequence_finish
    csrr    t1, CSR_DASICS_LIB_CFG
    li      t0, 3                       /* R/W retained, V cleared. */
    bne     t1, t0, sequence_finish
    csrr    t1, CSR_DASICS_JUMP_CFG
    bnez    t1, sequence_finish
#endif
    .endm

trusted_entry:
#if SEQUENCE_ROI
    /* Warmup and measurement use the same caller and both callee PCs. */
    li      s0, 128
    li      s1, 0
    li      s2, 0
    j       roi_loop
    .balign 64
    .globl roi_loop
roi_loop:
#endif
    call_domain b, A_BEFORE_B, A_FP_BEFORE_B, B_LOCAL, 40
#if SEQUENCE_ROI
    /* Keep B's observations before A replaces the two protected values. */
    or      s2, s2, a1
    mv      s4, s3
    fmv.x.d s5, fs3
    mv      s6, a0
    mv      s7, t1
#endif
    call_domain c, A_BEFORE_C, A_FP_BEFORE_C, C_LOCAL, 44
#if SEQUENCE_ROI
    or      s2, s2, a1
    addi    s0, s0, -1
    bnez    s0, roi_loop
    bnez    s1, .Lchain_complete
    li      s0, ROI_ITERATIONS
    li      s1, 1
    li      a0, 0
    li      a1, 0
    .globl roi_work_begin
roi_work_begin:
    .long   0x0000007b | (M5OP_WORK_BEGIN << 25)
    j       roi_loop
.Lchain_complete:
    mv      t5, a0                      /* workend writes a0. */
    li      a0, 0
    li      a1, 0
    .globl roi_work_end
roi_work_end:
    .long   0x0000007b | (M5OP_WORK_END << 25)

    /* The sticky entry bits cover every invocation, including warmup. */
    li      a0, 50
    bnez    s2, sequence_finish
    li      a0, 51
    li      t0, A_BEFORE_B
    bne     s4, t0, sequence_finish
    li      t0, A_FP_BEFORE_B
    bne     s5, t0, sequence_finish
    li      a0, 52
    li      t0, A_BEFORE_C
    bne     s3, t0, sequence_finish
    fmv.x.d t2, fs3
    li      t0, A_FP_BEFORE_C
    bne     t2, t0, sequence_finish
    li      a0, 53
    li      t0, B_LOCAL
    bne     s6, t0, sequence_finish
    li      t0, B_FP_LOCAL
    bne     s7, t0, sequence_finish
    li      t0, C_LOCAL
    bne     t5, t0, sequence_finish
    li      t0, C_FP_LOCAL
    bne     t1, t0, sequence_finish
    li      a0, 54
    la      t0, a_stack_top
    bne     sp, t0, sequence_finish
    csrr    t1, CSR_DASICS_LIB_CFG
    li      t0, 3
    bne     t1, t0, sequence_finish
    csrr    t1, CSR_DASICS_JUMP_CFG
    bnez    t1, sequence_finish
#endif

    /* A can see both stacks after C returns. An alias would lose B's data. */
    li      a0, 48
    la      t0, b_stack_top
    ld      t1, -8(t0)
    li      t2, B_LOCAL
    bne     t1, t2, sequence_finish
    ld      t1, -16(t0)
    li      t2, B_FP_LOCAL
    bne     t1, t2, sequence_finish
    li      a0, 49
    la      t0, c_stack_top
    ld      t1, -8(t0)
    li      t2, C_LOCAL
    bne     t1, t2, sequence_finish
    ld      t1, -16(t0)
    li      t2, C_FP_LOCAL
    bne     t1, t2, sequence_finish

    li      a0, 0
sequence_finish:
    li      a3, COMPLETION_TOKEN
user_done:
    ecall
    unimp

#if SEQUENCE_SOFTWARE
    .macro transfer_saved int_op, fp_op
    .irp i,SAVED_INDICES
    \int_op s\i, (CTX_GPR_SAVE + 8 * \i)(t0)
    .endr
    .irp i,SAVED_INDICES
    \fp_op fs\i, (CTX_FPR_SAVE + 8 * \i)(t0)
    .endr
    .endm
#endif

    .globl sequence_gate
sequence_gate:
    csrr    t0, CSR_DASICS_CONTEXT_BASE
    sd      ra, CTX_RA(t0)
    sd      sp, CTX_SP(t0)
#if SEQUENCE_SOFTWARE
    transfer_saved sd, fsd
#endif
    csrwi   CSR_DASICS_JUMP_CFG, 0
    csrwi   CSR_DASICS_LIB_CFG, 0
    csrw    CSR_DASICS_JUMP_BOUND_LO0, a0
    csrw    CSR_DASICS_JUMP_BOUND_HI0, a1
    csrw    CSR_DASICS_LIB_BOUND_LO0, a2
    csrw    CSR_DASICS_LIB_BOUND_HI0, a3
    mv      sp, a3
    csrwi   CSR_DASICS_JUMP_CFG, 1
    csrwi   CSR_DASICS_LIB_CFG, 0xb     /* Stack only: valid, readable, writable. */
    li      t0, 0
#if SEQUENCE_SOFTWARE
    .irp i,SAVED_INDICES
    li      s\i, 0
    fmv.d.x fs\i, zero
    .endr
#else
    .globl sequence_proreg_g, sequence_proreg_f, sequence_leave
sequence_proreg_g:
    .word   (SEQUENCE_MASK << 20) | 0x300b   /* PROREG.G.I */
sequence_proreg_f:
    .word   (SEQUENCE_MASK << 20) | 0x400b   /* PROREG.F.I */
#endif
    .globl gate_call, return_gate
gate_call:
    .insn   i 0x0b, 1, ra, a0, 0        /* DASICSCALL.JR */
return_gate:
    csrci   CSR_DASICS_LIB_CFG, 8
    csrci   CSR_DASICS_JUMP_CFG, 1
#if !SEQUENCE_SOFTWARE
sequence_leave:
    .word   0x0000500b                  /* LEAVE consumes both banks. */
#endif
    csrr    t0, CSR_DASICS_CONTEXT_BASE
#if SEQUENCE_SOFTWARE
    transfer_saved ld, fld
#endif
    ld      sp, CTX_SP(t0)
    ld      ra, CTX_RA(t0)
    .globl sequence_gate_ret
sequence_gate_ret:
    ret
#if SEQUENCE_ROI
    /* Leave padding outside the executed gate to isolate its code-size change. */
    .org sequence_gate + SEQUENCE_GATE_BYTES, 0
#endif

    .section .text.untrusted,"ax",@progbits
    .macro callee name, local_int, local_fp, deny_read, deny_jump, peer
    .balign 8
    .globl \name\()_entry, \name\()_end
\name\()_entry:
#if SEQUENCE_ROI
    fmv.x.d t0, fs3
    or      a1, s3, t0                  /* Return both entry observations. */
#else
#if SEQUENCE_FULL
    .irp i,SAVED_INDICES
    bnez    s\i, .Lbad\@
    fmv.x.d t0, fs\i
    bnez    t0, .Lbad\@
    .endr
    j       .Lgpr_zero\@
#else
    fmv.x.d t0, fs3
    /* A taken branch within the current jump window must be permitted. */
    beqz    s3, .Lgpr_zero\@
#endif
.Lbad\@:
    li      a0, 0
    ret
.Lgpr_zero\@:
#if !SEQUENCE_FULL
    bnez    t0, .Lbad\@
#endif
    la      t0, \name\()_stack_top
    bne     sp, t0, .Lbad\@
#endif
    addi    sp, sp, -16
#if SEQUENCE_FULL && !SEQUENCE_ROI
    seed_all \local_int, \local_fp
    li      t0, \local_fp
#else
    li      s3, \local_int
    li      t0, \local_fp
    fmv.d.x fs3, t0
#endif
    sd      s3, 8(sp)
    fsd     fs3, 0(sp)
    ld      a0, 8(sp)
#if !SEQUENCE_ROI
    bne     a0, s3, .Lbad\@
#endif
    ld      t1, 0(sp)
#if !SEQUENCE_ROI
    bne     t1, t0, .Lbad\@
#endif
    addi    sp, sp, 16

    .if SEQUENCE_DENY == \deny_read
    .globl seq_peer_target, seq_fault_probe
    .set seq_peer_target, \peer\()_stack_top - 8
    la      t0, seq_peer_target
seq_fault_probe:
    ld      t1, 0(t0)
    unimp
    .elseif SEQUENCE_DENY == \deny_jump
    .globl seq_peer_target, seq_fault_probe
    .set seq_peer_target, \peer\()_forbidden_landing
seq_fault_probe:
    j       seq_peer_target
    .endif
    ret
\name\()_forbidden_landing:
    unimp
    .balign 8
\name\()_end:
    .endm

    .globl callee_entry
callee_entry:
    callee b, B_LOCAL, B_FP_LOCAL, 1, 3, c
    callee c, C_LOCAL, C_FP_LOCAL, 2, 4, b

    .section .bss.c_stack,"aw",@nobits
    .balign 4096
    .globl c_stack_bottom, c_stack_top
c_stack_bottom:
    .space 4096
c_stack_top:
