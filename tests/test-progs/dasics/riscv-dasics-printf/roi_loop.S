/* SPDX-License-Identifier: BSD-3-Clause */
#include <gem5/asm/generic/m5ops.h>

    .option norelax
    .option norvc
    .text
    .balign 8
    .globl run_printf_batch
    .type run_printf_batch,@function
/* a0: warmup count, a1: measured count. Return the measured sum or an error. */
run_printf_batch:
    addi    sp, sp, -48
    sd      ra, 0(sp)
    sd      s0, 8(sp)
    sd      s1, 16(sp)
    sd      s2, 24(sp)
    sd      s4, 32(sp)
    sd      s5, 40(sp)
    mv      s0, a1
    mv      s1, a0
    li      s2, 0                   /* Sum of printf returns in this batch. */
    li      s4, 0                   /* Set after warmup. */
    li      s5, 0                   /* Sticky mismatch from either batch. */
.Lcalls:
    lla     a0, b_format
    li      a1, 7
    .globl roi_call_loop
roi_call_loop:
    call    run_printf
    addw    s2, s2, a0
    xori    t0, a0, 4
    or      s5, s5, t0
    addiw   s1, s1, -1
    bnez    s1, .Lcalls
    bnez    s4, .Lmeasured_done
    li      s4, 1
    mv      s1, s0
    li      s2, 0
    li      a0, 0
    li      a1, 0
    .globl roi_begin
roi_begin:
    .word   0x7b | (M5OP_WORK_BEGIN << 25)
    j       .Lcalls
.Lmeasured_done:
    li      a0, 0
    li      a1, 0
    .globl roi_end
roi_end:
    .word   0x7b | (M5OP_WORK_END << 25)
    mv      a0, s2
    beqz    s5, .Lreturn
    li      a0, -3
.Lreturn:
    ld      ra, 0(sp)
    ld      s0, 8(sp)
    ld      s1, 16(sp)
    ld      s2, 24(sp)
    ld      s4, 32(sp)
    ld      s5, 40(sp)
    addi    sp, sp, 48
    ret
    .size run_printf_batch, .-run_printf_batch
    .section .note.GNU-stack,"",@progbits
