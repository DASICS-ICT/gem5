/* SPDX-License-Identifier: BSD-3-Clause */
#include <gem5/asm/generic/m5ops.h>

    .option norelax
    .option norvc
    .text
    .balign 8
    .globl run_memcpy_batch
    .type run_memcpy_batch,@function
/* Use the same call PC and aligned buffers for warmup and measurement. */
run_memcpy_batch:
    addi    sp, sp, -64
    sd      ra, 0(sp)
    sd      s0, 8(sp)
    sd      s1, 16(sp)
    sd      s2, 24(sp)
    sd      s3, 32(sp)
    sd      s4, 40(sp)
    sd      s5, 48(sp)
    sd      s6, 56(sp)
    mv      s0, a0
    mv      s1, a1
    mv      s2, a2
    mv      s3, a3
    li      s4, 128
    li      s5, 0
    li      s6, 0                   /* Sticky return-pointer mismatch. */
.Lloop:
    mv      a0, s0
    mv      a1, s1
    mv      a2, s2
    lla     a3, b_memcpy
    .globl roi_call_loop
roi_call_loop:
    call    run_memcpy
    xor     t0, a0, s0
    or      s6, s6, t0
    addi    s4, s4, -1
    bnez    s4, .Lloop
    bnez    s5, .Lmeasured
    mv      a0, s2
    call    prepare_measured
    beqz    a0, .Ldone
    li      s5, 1
    mv      s4, s3
    li      a0, 0
    li      a1, 0
    .globl roi_begin
roi_begin:
    .word   0x7b | (M5OP_WORK_BEGIN << 25)
    j       .Lloop
.Lmeasured:
    li      a0, 0
    li      a1, 0
    .globl roi_end
roi_end:
    .word   0x7b | (M5OP_WORK_END << 25)
    seqz    a0, s6
.Ldone:
    ld      ra, 0(sp)
    ld      s0, 8(sp)
    ld      s1, 16(sp)
    ld      s2, 24(sp)
    ld      s3, 32(sp)
    ld      s4, 40(sp)
    ld      s5, 48(sp)
    ld      s6, 56(sp)
    addi    sp, sp, 64
    ret
    .size run_memcpy_batch, .-run_memcpy_batch
    .section .note.GNU-stack,"",@progbits
