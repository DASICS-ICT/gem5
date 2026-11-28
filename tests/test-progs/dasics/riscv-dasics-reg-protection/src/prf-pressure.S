/* SPDX-License-Identifier: BSD-3-Clause */
#define PRF_PRESSURE 1
#ifndef USE_INT_PROREG
#define USE_INT_PROREG 1
#endif
#if !defined(PRF_CLOBBERS) || (PRF_CLOBBERS != 0 && PRF_CLOBBERS != 12)
#error Select zero or twelve protected integer destinations
#endif
#include "runtime.inc"

    .equ HOT_VALUE,  0x119
    .equ COLD_VALUE, 0x36b
    .section .text.trusted,"ax",@progbits
trusted_entry:
    /* Warm the B instruction stream and this data page's translation using
     * a distant line. A never loads the measured word directly. */
    li      s0, 4
.Lwarm:
    la      a0, prf_hot_word
    la      a1, output_buffer
    li      a2, 1
    call    protected_gate
    li      t0, HOT_VALUE
    bne     a0, t0, .Lbad_load
    addi    s0, s0, -1
    bnez    s0, .Lwarm

    .irp i,0,1,2,3,4,5,6,7,8,9,10,11
    li      s\i, (0x401 + \i)
    .endr
    la      a0, prf_cold_word
    la      a1, output_buffer
    li      a2, 1                       /* Grant the 16-byte input record. */
    .globl prf_measure_call, prf_measure_return
prf_measure_call:
    call    protected_gate
prf_measure_return:
    li      t0, COLD_VALUE
    bne     a0, t0, .Lbad_load
    .irp i,0,1,2,3,4,5,6,7,8,9,10,11
    li      t0, (0x401 + \i)
    bne     s\i, t0, .Lbad_restore
    .endr
    li      a0, 0
    j       .Lfinish
.Lbad_load:
    li      a0, 40
    j       .Lfinish
.Lbad_restore:
    li      a0, 41
.Lfinish:
    li      a3, COMPLETION_TOKEN
user_done:
    ecall
    unimp

#include "gate.inc"

    .section .text.untrusted,"ax",@progbits
    .globl callee_entry, prf_clobber_begin, prf_clobber_end
    .globl prf_slow_load, prf_writes_begin, prf_writes_end
callee_entry:
prf_clobber_begin:
    /* Only the twelve rd fields differ between the two images. */
    .set n, 0
#if PRF_CLOBBERS == 12
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
#else
    .irp reg,t0,t1,t2,t3,t4,t5,t6,a1,a2,a3,a4,a5
#endif
    addi    \reg, zero, (0x101 + n)
    .set n, n + 1
    .endr
prf_clobber_end:
prf_slow_load:
    ld      a0, 0(a0)
prf_writes_begin:
    /* The younger writes have no true dependencies on each other or the
     * load. The loaded value remains live in a0 across the return. */
    .set n, 0
    .rept 16
    .irp reg,t0,t1,t2,t3,t4,t5,t6,a1
    addi    \reg, zero, (0x201 + n)
    .set n, n + 1
    .endr
    .endr
prf_writes_end:
    ret

    .section .rodata.prf_pressure,"a",@progbits
    .balign 4096
    .globl prf_hot_word, prf_cold_word
prf_hot_word:
    .dword HOT_VALUE
    .org prf_hot_word + 2048
prf_cold_word:
    .dword COLD_VALUE
    .org prf_hot_word + 4096
