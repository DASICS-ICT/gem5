/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CONTEXT_BASE, 0x8b4
    .equ PROREG_G_I_S3, 0x0080300b
    .equ LEAVE, 0x0000500b

    .option norvc
    .text
    .balign 8
    .globl __dasics_trusted_start, _start
__dasics_trusted_start:
_start:
    /* The protected loader supplies the context address before user entry. */
    csrr    t0, CONTEXT_BASE
    li      a0, 2                       /* Ordinary SE has no context. */
    beqz    t0, .Lexit
    lla     t1, __dasics_context_base
    bne     t0, t1, .Lfail

    ld      s1, 0(sp)                   /* Linux argc */
    li      s3, 19
    li      a1, 0
    lla     t0, .Lcallee
    .word   PROREG_G_I_S3
    .insn   i 0x0b, 1, ra, t0, 0       /* DASICSCALL.JR */
    .word   LEAVE
    beqz    a1, .Lfail
    li      t0, 19
    bne     s3, t0, .Lfail

    /* With an extra argument, issue the same PROREG in B with empty slots. */
    li      t0, 1
    bne     s1, t0, untrusted_proreg
    li      a0, 0
    j       .Lexit
.Lfail:
    li      a0, 1
.Lexit:
    li      a7, 93                      /* Linux exit */
    ecall

    .balign 8
    .globl __dasics_trusted_end, __dasics_untrusted_start
__dasics_trusted_end:
__dasics_untrusted_start:
.Lcallee:
    beqz    s3, .Lzero
    ret
.Lzero:
    li      a1, 1
    li      s3, 7
    ret

    .globl untrusted_proreg
untrusted_proreg:
    .word   PROREG_G_I_S3
    ebreak                              /* Distinguishes an unexpected pass. */
    .balign 8
    .globl __dasics_untrusted_end
__dasics_untrusted_end:

    .bss
    .balign 4096
    .globl __dasics_context_base
__dasics_context_base:
    .skip   256
