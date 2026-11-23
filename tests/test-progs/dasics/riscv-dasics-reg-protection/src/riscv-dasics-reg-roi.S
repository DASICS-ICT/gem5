/* SPDX-License-Identifier: BSD-3-Clause */
#include <gem5/asm/generic/m5ops.h>

#define ROI_MEASUREMENT 1
#ifndef USE_INT_PROREG
#define USE_INT_PROREG 0
#endif
#ifndef USE_FP_PROREG
#define USE_FP_PROREG 0
#endif
#ifndef ROI_ITERATIONS
#define ROI_ITERATIONS 1024
#endif
#ifndef ROI_WORKLOAD
#define ROI_WORKLOAD 0
#endif
#if ROI_ITERATIONS <= 0 || (ROI_WORKLOAD != 0 && ROI_WORKLOAD != 1)
#error Invalid ROI workload or iteration count
#endif

#include "runtime.inc"

    .globl roi_iterations, roi_workload, roi_protection, roi_gate_mode
    .equ roi_iterations, ROI_ITERATIONS
    .equ roi_workload, ROI_WORKLOAD
    .equ roi_gate_mode, GATE_MODE
    .globl roi_int_proreg, roi_fp_proreg
    .equ roi_int_proreg, USE_INT_PROREG
    .equ roi_fp_proreg, USE_FP_PROREG
    .equ roi_protection, (GATE_MODE == GATE_SOFTWARE) & 1
#if VECTOR_ABI
    .globl roi_vector_abi, roi_vector_protected, roi_vector_vlen
    .equ roi_vector_vlen, VECTOR_VLEN
    .equ roi_vector_abi, VECTOR_ABI
    .equ roi_vector_protected, VECTOR_PROTECTED
#endif

    .section .text.trusted,"ax",@progbits
trusted_entry:
    /* Initialize the same input and private state before every variant. */
    la      t0, input_buffer
    li      t1, 1
    li      t2, ELEMENT_COUNT + 1
.Linit_input:
    sd      t1, 0(t0)
    fcvt.d.lu ft0, t1
    fsd     ft0, 8(t0)
    addi    t0, t0, 16
    addi    t1, t1, 1
    bne     t1, t2, .Linit_input
    li      t0, GPR_SEED
    .irp reg,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    mv      \reg, t0
    addi    t0, t0, 1
    .endr
    li      t0, FPR_SEED
    .irp reg,fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fmv.d.x \reg, t0
    addi    t0, t0, 1
    .endr
    li      gp, GP_SEED
    li      tp, TP_SEED
    li      t0, A_STACK_VALUE
    sd      t0, -8(sp)
    li      t0, 0x61
    csrw    fcsr, t0
#if VECTOR_ABI
    li      a0, 33
    csrr    t0, vlenb
    li      t1, VEC_BYTES
    bne     t0, t1, user_finish
    /* Both members of an ABI pair enter B with a full e64 vector.
     * v1 and v24 represent the two callee-saved ranges of the variant.
     */
    vsetivli t0, VEC_LANES, e64, m1, tu, mu
    li      t1, VEC_LANES
    bne     t0, t1, user_finish
    vid.v   v1
    vadd.vi v1, v1, 3
    vid.v   v24
    vadd.vi v24, v24, 7
#endif

    /* s0 counts calls and s1 selects warmup versus the measured batch. */
    li      s0, 128
    li      s1, 0
    j       roi_loop
    .balign 64
    .globl roi_loop, roi_gate_call, after_gate
roi_loop:
    la      a0, input_buffer
    la      a1, output_buffer
    li      a2, ELEMENT_COUNT
    li      t0, FP_SCALE
    fmv.d.x fa0, t0
#if VECTOR_ABI == 2
    /* Lane i of the full v8 argument contains 11 + i. */
    vid.v   v8
    vadd.vi v8, v8, 11
#endif
roi_gate_call:
    call    protected_gate
after_gate:
    addi    s0, s0, -1
    bnez    s0, roi_loop
    bnez    s1, .Lroi_complete
    li      s0, ROI_ITERATIONS
    li      s1, 1
    li      a0, 0
    li      a1, 0
    .globl roi_work_begin
roi_work_begin:
    .long   0x0000007B | (M5OP_WORK_BEGIN << 25)
    j       roi_loop
.Lroi_complete:
    /* M5Op writes a0; capture both return values before the end marker. */
    mv      t5, a0
    fmv.x.d t6, fa0
    li      a0, 0
    li      a1, 0
    .globl roi_work_end
roi_work_end:
    .long   0x0000007B | (M5OP_WORK_END << 25)

    /* All correctness loads and diagnostic branches follow workend. */
    li      a0, 16
#if ROI_WORKLOAD == 0
    bnez    t5, user_finish
    li      a0, 17
    bnez    t6, user_finish
#else
    li      t0, 14
    bne     t5, t0, user_finish
    li      a0, 17
    li      t0, FP_CHECKSUM
    bne     t6, t0, user_finish
#endif
#if VECTOR_ABI
    li      a0, 34
    csrr    t0, vstart
    bnez    t0, user_finish
    csrr    t0, vl
    li      t1, VEC_LANES
    bne     t0, t1, user_finish
    csrr    t0, vtype
    li      t1, (3 << 3)    /* e64, m1, tu, mu */
    bne     t0, t1, user_finish
#if VECTOR_ABI == 2
    /* Return values and callee-saved vectors remain live across workend. */
    .macro CHECK_LANES reg, low
    vmv.x.s t0, \reg
    li      t1, \low
    bne     t0, t1, user_finish
    .set .Llane, 1
    .rept VEC_LANES - 1
    vslidedown.vi v16, \reg, .Llane
    vmv.x.s t0, v16
    addi    t1, t1, 1
    bne     t0, t1, user_finish
    .set .Llane, .Llane + 1
    .endr
    .endm
    li      a0, 35
    CHECK_LANES v8, (11 + ROI_WORKLOAD)
    li      a0, 36
    CHECK_LANES v1, 3
    CHECK_LANES v24, 7
#endif
#endif
    li      a0, 14
    bnez    s0, user_finish
    li      t0, 1
    bne     s1, t0, user_finish
    la      t0, a_stack_top
    bne     sp, t0, user_finish
    la      t0, after_gate
    bne     ra, t0, user_finish
    li      t0, GP_SEED
    bne     gp, t0, user_finish
    li      t0, TP_SEED
    bne     tp, t0, user_finish
    li      a0, 15
    csrr    t0, fcsr
    li      t1, 0x61
    bne     t0, t1, user_finish
    li      a0, 12
    li      t0, GPR_SEED
    .irp reg,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    bne     \reg, t0, user_finish
    addi    t0, t0, 1
    .endr
    li      a0, 13
    li      t0, FPR_SEED
    .irp reg,fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fmv.x.d t1, \reg
    bne     t0, t1, user_finish
    addi    t0, t0, 1
    .endr
    li      a0, 27
    ld      t0, -8(sp)
    li      t1, A_STACK_VALUE
    bne     t0, t1, user_finish

    /* Confirm which data-protection variant actually touched the frame. */
    li      a0, 32
    csrr    t0, CSR_DASICS_CONTEXT_BASE
    la      t1, context_frame
    bne     t0, t1, user_finish
    ld      t2, CTX_GPR_SAVE(t0)
#if GATE_MODE >= GATE_SAVE
    /* The last call has s0=1. PROREG leaves its zeroed frame slot alone. */
    li      t1, 1 - roi_int_proreg
    bne     t2, t1, user_finish
    ld      t2, CTX_FPR_SAVE(t0)
#if USE_FP_PROREG
    bnez    t2, user_finish         /* The FP gate leaves this slot untouched. */
#else
    li      t1, FPR_SEED
    bne     t2, t1, user_finish
#endif
#else
    bnez    t2, user_finish
    ld      t2, CTX_FPR_SAVE(t0)
    bnez    t2, user_finish
#endif
    li      a0, 23
    csrr    t0, CSR_DASICS_LIB_CFG
    li      t1, LIB_REVOKED
    bne     t0, t1, user_finish
    csrr    t0, CSR_DASICS_FREASON
    bnez    t0, user_finish
    li      a0, 25
    csrr    t0, CSR_DASICS_RETURN_PC
    la      t1, return_gate
    bne     t0, t1, user_finish

#if ROI_WORKLOAD == 1
    li      a0, 18
    la      t0, output_buffer
    la      t1, input_buffer
    li      t2, 1
    li      t5, ELEMENT_COUNT + 1
.Lcheck_records:
    ld      t3, 0(t0)
    addi    t4, t2, 1
    bne     t3, t4, user_finish
    slli    t4, t2, 1
    fcvt.d.lu ft0, t4
    fmv.x.d t4, ft0
    ld      t3, 8(t0)
    bne     t3, t4, user_finish
    ld      t3, 0(t1)
    bne     t3, t2, user_finish
    fcvt.d.lu ft0, t2
    fmv.x.d t4, ft0
    ld      t3, 8(t1)
    bne     t3, t4, user_finish
    addi    t0, t0, 16
    addi    t1, t1, 16
    addi    t2, t2, 1
    bne     t2, t5, .Lcheck_records
#endif
    li      a0, 0
user_finish:
    li      a3, COMPLETION_TOKEN
user_done:
    ecall
    unimp

    /* Pin the caller loop, gate entry and B entry across the paired ELFs.
     * Gate-internal addresses reflect the actual omitted instructions.
     */
    .org 0x800
#include "gate.inc"

    .section .text.untrusted,"ax",@progbits
    .globl callee_entry
#if VECTOR_ABI == 2
    .variant_cc callee_entry
#endif
callee_entry:
#if ROI_WORKLOAD == 0
    li      a0, 0
    fmv.d.x fa0, zero
#else
    mv      t3, a0
    mv      t4, a1
    li      t1, 0
    li      t2, 0
    fmv.d.x fa1, zero
.Lcompute:
    ld      t0, 0(t3)
    addi    t0, t0, 1
    add     t1, t1, t0
    sd      t0, 0(t4)
    fld     ft0, 8(t3)
    fmul.d  ft0, ft0, fa0
    fadd.d  fa1, fa1, ft0
    fsd     ft0, 8(t4)
    addi    t3, t3, 16
    addi    t4, t4, 16
    addi    t2, t2, 1
    bltu    t2, a2, .Lcompute
    mv      a0, t1
    fmv.d   fa0, fa1
#if VECTOR_ABI == 2
    vadd.vi v8, v8, 1
#endif
#endif
#ifdef ROI_CLOBBER_COUNT
#if ROI_CLOBBER_COUNT != 0 && ROI_CLOBBER_COUNT != 1 && \
    ROI_CLOBBER_COUNT != 6 && ROI_CLOBBER_COUNT != 12
#error Unsupported protected-register clobber count
#endif
    .globl roi_clobber_count, clobber_writes_begin, clobber_writes_end
    .equ roi_clobber_count, ROI_CLOBBER_COUNT
    /* All variants retire twelve independent writes after both results
     * are ready. Only the first k destinations are protected registers.
     */
    .macro CLOBBER slot, saved, scratch
    .if \slot < roi_clobber_count
    addi    \saved, zero, (0x101 + \slot)
    .else
    addi    \scratch, zero, (0x101 + \slot)
    .endif
    .endm
clobber_writes_begin:
    CLOBBER  0, s0,  t0
    CLOBBER  1, s1,  t1
    CLOBBER  2, s2,  t2
    CLOBBER  3, s3,  t3
    CLOBBER  4, s4,  t4
    CLOBBER  5, s5,  t5
    CLOBBER  6, s6,  t6
    CLOBBER  7, s7,  a1
    CLOBBER  8, s8,  a2
    CLOBBER  9, s9,  a3
    CLOBBER 10, s10, a4
    CLOBBER 11, s11, a5
clobber_writes_end:
#endif
    ret
