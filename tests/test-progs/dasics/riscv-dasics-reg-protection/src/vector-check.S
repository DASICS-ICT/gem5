/* SPDX-License-Identifier: BSD-3-Clause */
#define VECTOR_CHECK 1
#include "runtime.inc"

#if (VECTOR_ABI != 1 && VECTOR_ABI != 2) || VECTOR_PROTECTED != 1
#error The vector ABI check requires a protected normal or variant gate
#endif

    .equ LANE_SEED, 0x943E65C02718BC50
    .equ RETURN_SEED, 0x457689ABCC987123
    .equ VECTOR_WORDS, 32 * VEC_LANES
    .if (32 * VEC_BYTES) > 4096
    .error "Vector observations exceed the output page"
    .endif

    .section .text.trusted,"ax",@progbits
trusted_entry:
    li      a0, 40
    csrr    t0, vlenb
    li      t1, VEC_BYTES
    bne     t0, t1, user_finish

    /* Each 64-bit lane starts with a unique nonzero value. Poison the
     * observation page so a skipped store cannot pass a zero check.
     */
    la      t0, output_buffer
    li      t1, -1
    li      t2, VECTOR_WORDS
.Lpoison:
    sd      t1, 0(t0)
    addi    t0, t0, 8
    addi    t2, t2, -1
    bnez    t2, .Lpoison
    vsetivli zero, VEC_LANES, e64, m1, tu, mu
    li      t0, LANE_SEED
    .irp n,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,\
           16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    vid.v   v\n
    vadd.vx v\n, v\n, t0
    addi    t0, t0, VEC_LANES
    .endr
    la      a0, input_buffer
    la      a1, output_buffer
    li      a2, ELEMENT_COUNT
    li      t0, FP_SCALE
    fmv.d.x fa0, t0
    li      t0, 0x61
    csrw    fcsr, t0
    vsetivli zero, 1, e64, m1, tu, mu
    call    protected_gate
after_gate:
    /* B returns check 42 for an incorrect entry environment. */
    bnez    a0, user_finish
    li      a0, 41
    fmv.x.d t0, fa0
    li      t1, FP_SCALE
    bne     t0, t1, user_finish
    csrr    t0, fcsr
    li      t1, 0x61
    bne     t0, t1, user_finish
    la      t0, a_stack_top
    bne     sp, t0, user_finish
    csrr    t0, vstart
    bnez    t0, user_finish

    li      a0, 43
    la      t0, output_buffer
    li      t1, 0
    li      t2, VECTOR_WORDS
.Lcheck_entry:
    li      t3, 0
#if VECTOR_ABI == 2
    /* For v8, all lanes are authorized; the other 31 must be zero. */
    addi    t4, t1, -(8 * VEC_LANES)
    sltiu   t4, t4, VEC_LANES
    beqz    t4, .Lexpect_word
    li      t3, LANE_SEED
    add     t3, t3, t1
.Lexpect_word:
#endif
    ld      t4, 0(t0)
    bne     t4, t3, user_finish
    addi    t0, t0, 8
    addi    t1, t1, 1
    bne     t1, t2, .Lcheck_entry

#if VECTOR_ABI == 2
    /* A has no live stack frame here. Keep its returned register image
     * private, including when it fills the page at VLEN=1024.
     */
    la      t0, a_stack_bottom
    .irp n,0,8,16,24
    vs8r.v  v\n, (t0)
    addi    t0, t0, 8 * VEC_BYTES
    .endr
    la      t0, a_stack_bottom
    li      t1, 0
    li      t2, VECTOR_WORDS
    li      a0, 45
.Lcheck_return:
    /* v1-v7 and v24-v31 are restored; v8 contains B's return lanes. */
    li      t4, VEC_LANES
    divu    t3, t1, t4
    beqz    t3, .Lnext_return
    li      t4, 8
    beq     t3, t4, .Lreturn_value
    bltu    t3, t4, .Lsaved_value
    li      t4, 24
    bltu    t3, t4, .Lnext_return
.Lsaved_value:
    li      t3, LANE_SEED
    j       .Lcompare_return
.Lreturn_value:
    li      t3, RETURN_SEED - 8 * VEC_LANES
.Lcompare_return:
    add     t3, t3, t1
    ld      t4, 0(t0)
    bne     t3, t4, user_finish
.Lnext_return:
    addi    t0, t0, 8
    addi    t1, t1, 1
    bne     t1, t2, .Lcheck_return
#endif
    li      a0, 0
user_finish:
    li      a3, COMPLETION_TOKEN
user_done:
    ecall
    unimp

#include "gate.inc"

    .section .text.untrusted,"ax",@progbits
    .globl callee_entry
#if VECTOR_ABI == 2
    .variant_cc callee_entry
#endif
callee_entry:
    li      a0, 42
    csrr    t0, vstart
    bnez    t0, .Lreturn
    csrr    t0, vl
    li      t1, VEC_LANES
    bne     t0, t1, .Lreturn
    csrr    t0, vtype
    li      t1, 0x18
    bne     t0, t1, .Lreturn
    la      t0, b_stack_top
    bne     sp, t0, .Lreturn
    csrr    t0, fcsr
    bnez    t0, .Lreturn

    /* Extract all lanes with integer stores to the authorized output.
     * Sliding a register in place leaves all unobserved registers intact.
     */
    mv      t2, a1
    .irp n,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,\
           16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    li      t1, VEC_LANES
1:
    vmv.x.s t0, v\n
    sd      t0, 0(t2)
    addi    t2, t2, 8
    vslidedown.vi v\n, v\n, 1
    addi    t1, t1, -1
    bnez    t1, 1b
    .endr
#if VECTOR_ABI == 2
    .irp n,1,2,3,4,5,6,7,24,25,26,27,28,29,30,31
    vmv.v.i v\n, -1
    .endr
    li      t0, RETURN_SEED
    vid.v   v8
    vadd.vx v8, v8, t0
#endif
    li      a0, 0
.Lreturn:
    ret
