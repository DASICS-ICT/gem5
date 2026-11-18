/* SPDX-License-Identifier: BSD-3-Clause */
#include "runtime.inc"

    .section .text.trusted,"ax",@progbits
trusted_entry:
    li      a0, 1
    csrr    t0, CSR_DASICS_LIB_CFG
    bnez    t0, user_finish
    csrr    t0, CSR_DASICS_JUMP_CFG
    li      t1, 1
    bne     t0, t1, user_finish
    li      a0, 3
    csrr    t0, CSR_DASICS_CONTEXT_BASE
    la      t1, context_frame
    bne     t0, t1, user_finish

    /* Distinct simultaneous sentinels catch accidental physical aliases. */
    li      t1, 0x11
    sd      t1, 0(t0)
    la      t0, a_stack_bottom
    li      t1, 0x22
    sd      t1, 0(t0)
    la      t0, b_stack_bottom
    li      t1, 0x33
    sd      t1, 0(t0)
    la      t0, input_buffer
    li      t1, 0x44
    sd      t1, 0(t0)
    la      t0, output_buffer
    li      t1, 0x55
    sd      t1, 0(t0)

    .macro CHECK_PAGE name, value
    la      t0, \name
    ld      t1, 0(t0)
    li      t2, \value
    bne     t1, t2, user_finish
    sd      zero, 0(t0)
    .endm
    li      a0, 4
    CHECK_PAGE context_frame, 0x11
    CHECK_PAGE a_stack_bottom, 0x22
    CHECK_PAGE b_stack_bottom, 0x33
    CHECK_PAGE input_buffer, 0x44
    CHECK_PAGE output_buffer, 0x55

    li      a0, 5
    la      t0, a_stack_top
    bne     sp, t0, user_finish
    andi    t1, sp, 15
    bnez    t1, user_finish
    addi    sp, sp, -16
    li      t1, 0x66
    sd      t1, 0(sp)
    ld      t2, 0(sp)
    bne     t1, t2, user_finish
    sd      zero, 0(sp)
    addi    sp, sp, 16

    li      a0, 6
    csrr    t0, fcsr
    bnez    t0, user_finish
    fmv.d.x ft0, zero
    fmv.x.d t0, ft0
    bnez    t0, user_finish
    j       test_calls

test_calls:
    /* Input records contain {uint64_t integer, double floating}. */
    la      t0, input_buffer
    li      t1, 1
    li      t2, ELEMENT_COUNT + 1
.Linput_init:
    sd      t1, 0(t0)
    fcvt.d.lu ft0, t1
    fsd     ft0, 8(t0)
    addi    t0, t0, 16
    addi    t1, t1, 1
    bne     t1, t2, .Linput_init
    la      t0, a_stack_bottom
    li      t1, 2
    sd      t1, 0(t0)
    li      t1, A_STACK_VALUE
    sd      t1, -8(sp)
.Lprepare_call:
    /* Different seeds on each call detect stale save-frame reuse. */
    la      t0, a_stack_bottom
    ld      t2, 0(t0)
    slli    t2, t2, 8
    li      t0, GPR_SEED
    add     t0, t0, t2
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    mv      \reg, t0
    addi    t0, t0, 1
    .endr
    li      t0, FPR_SEED
    add     t0, t0, t2
    .irp num,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,\
             16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    fmv.d.x f\num, t0
    addi    t0, t0, 1
    .endr
    srli    t2, t2, 8
    ori     t2, t2, 0x60
    csrw    fcsr, t2
    li      gp, GP_SEED
    li      tp, TP_SEED
    la      a0, input_buffer
    la      a1, output_buffer
    li      a2, ELEMENT_COUNT
    li      t0, FP_SCALE
    fmv.d.x fa0, t0
    .irp reg,a3,a4,a5,a6,a7,t0,t1,t2,t3,t4,t5,t6
    li      \reg, 0x7E5
    .endr
    call    protected_gate
after_gate:
    /* Inspect results before using argument registers as diagnostics. */
    li      t1, 14
    bne     a0, t1, .Lbad_integer_result
    fmv.x.d t0, fa0
    li      t1, FP_CHECKSUM
    bne     t0, t1, .Lbad_float_result
    li      a0, 14
    la      t0, a_stack_top
    bne     sp, t0, user_finish
    la      t0, after_gate
    bne     ra, t0, user_finish
    li      t0, GP_SEED
    bne     gp, t0, user_finish
    li      t0, TP_SEED
    bne     tp, t0, user_finish
    la      t0, a_stack_bottom
    ld      t2, 0(t0)
    li      a0, 15
    ori     t0, t2, 0x60
    csrr    t1, fcsr
    bne     t0, t1, user_finish
    slli    t2, t2, 8
    li      t0, GPR_SEED
    add     t0, t0, t2
    li      a0, 12
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    bne     \reg, t0, user_finish
    addi    t0, t0, 1
    .endr
    li      a0, 13
    .irp num,8,9,18,19,20,21,22,23,24,25,26,27
    li      t0, FPR_SEED + \num
    add     t0, t0, t2
    fmv.x.d t1, f\num
    bne     t0, t1, user_finish
    .endr

    li      a0, 19
    la      t0, output_buffer
    la      t1, expected_entry_gpr
    li      t2, 32
.Lcheck_entry_gpr:
    ld      t3, 0(t0)
    ld      t4, 0(t1)
    bne     t3, t4, user_finish
    addi    t0, t0, 8
    addi    t1, t1, 8
    addi    t2, t2, -1
    bnez    t2, .Lcheck_entry_gpr
    li      a0, 20
    li      t1, 0
    li      t4, 32
.Lcheck_entry_fpr:
    li      t2, 0
    li      t3, 10
    bne     t1, t3, .Lentry_fpr_value
    li      t2, FP_SCALE
.Lentry_fpr_value:
    ld      t3, 0(t0)
    bne     t2, t3, user_finish
    addi    t0, t0, 8
    addi    t1, t1, 1
    bne     t1, t4, .Lcheck_entry_fpr
    li      a0, 21
    ld      t1, 0(t0)
    bnez    t1, user_finish
    li      a0, 27
    ld      t1, 8(t0)
    li      t2, B_STACK_VALUE
    bne     t1, t2, user_finish
    ld      t1, -8(sp)
    li      t2, A_STACK_VALUE
    bne     t1, t2, user_finish

    li      a0, 18
    la      t0, output_buffer
    addi    t0, t0, OUTPUT_DATA
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

    li      a0, 23
    csrr    t0, CSR_DASICS_LIB_CFG
    li      t1, LIB_REVOKED
    bne     t0, t1, user_finish
    .macro CHECK_BOUND csr, symbol, offset=0
    csrr    t0, \csr
    la      t1, \symbol
    addi    t1, t1, \offset
    bne     t0, t1, user_finish
    .endm
    li      a0, 24
    CHECK_BOUND CSR_DASICS_LIB_BOUND_LO0, input_buffer
    CHECK_BOUND CSR_DASICS_LIB_BOUND_HI0, input_buffer, ELEMENT_COUNT * 16
    CHECK_BOUND CSR_DASICS_LIB_BOUND_LO1, output_buffer
    CHECK_BOUND CSR_DASICS_LIB_BOUND_HI1, output_buffer_end
    CHECK_BOUND CSR_DASICS_LIB_BOUND_LO2, b_stack_bottom
    CHECK_BOUND CSR_DASICS_LIB_BOUND_HI2, b_stack_top
    li      a0, 25
    CHECK_BOUND CSR_DASICS_CONTEXT_BASE, context_frame
    CHECK_BOUND CSR_DASICS_RETURN_PC, return_gate
    la      t0, a_stack_bottom
    ld      t1, 0(t0)
    addi    t1, t1, -1
    sd      t1, 0(t0)
    bnez    t1, .Lprepare_call
    li      a0, 0
    j       user_finish
.Lbad_integer_result:
    li      a0, 16
    j       user_finish
.Lbad_float_result:
    li      a0, 17
    j       user_finish

#include "gate.inc"

user_finish:
    li      a3, COMPLETION_TOKEN
user_done:
    ecall
    unimp

    .section .text.untrusted,"ax",@progbits
    .globl callee_entry
callee_entry:
    /* Capture entry bits before using any scratch registers. a1 is output. */
    .set .Lobserve_offset, 0
    .irp num,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,\
             16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    sd      x\num, .Lobserve_offset(a1)
    .set .Lobserve_offset, .Lobserve_offset + 8
    .endr
    .set .Lobserve_offset, OBS_FPR
    .irp num,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,\
             16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    fsd     f\num, .Lobserve_offset(a1)
    .set .Lobserve_offset, .Lobserve_offset + 8
    .endr
    csrr    t0, fcsr
    sd      t0, OBS_FCSR(a1)
    addi    sp, sp, -32
    sd      ra, 24(sp)
    li      t0, B_STACK_VALUE
    sd      t0, 0(sp)
    ld      t0, 0(sp)
    sd      t0, OBS_STACK(a1)

#if TEST_SCENARIO != 0
#if TEST_SCENARIO <= 2
    la      t4, context_frame
#else
    la      t4, a_stack_top
    addi    t4, t4, -8
#endif
    li      a4, LOAD_DEST_VALUE
fault_probe:
#if TEST_SCENARIO == 1 || TEST_SCENARIO == 3
    ld      a4, 0(t4)
#else
    sd      a4, 0(t4)
#endif
    /* An access that escaped DASICS must never reach the success handler. */
    unimp
#else
    mv      t3, a0
    addi    t4, a1, OUTPUT_DATA
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
    /* Deliberately violate saved-register and stack conventions. */
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    li      \reg, -1
    .endr
    li      t0, -1
    .irp reg,fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fmv.d.x \reg, t0
    .endr
    li      t0, 0x3F
    csrw    fcsr, t0
    li      gp, -1
    li      tp, -1
    ld      ra, 24(sp)
    li      sp, 0
    ret
#endif

    .section .rodata.trusted,"a",@progbits
    .balign 8
expected_entry_gpr:
    .dword 0, return_gate, b_stack_top, 0, 0, 0, 0, 0
    .dword 0, 0, input_buffer, output_buffer, ELEMENT_COUNT, 0, 0, 0
    .dword 0, 0, 0, 0, 0, 0, 0, 0
    .dword 0, 0, 0, 0, 0, 0, 0, 0
