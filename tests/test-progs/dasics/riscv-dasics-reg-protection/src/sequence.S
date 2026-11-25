/* SPDX-License-Identifier: BSD-3-Clause */
#define SEQUENCE_CALLS 1
#ifndef SEQUENCE_DENY
#define SEQUENCE_DENY 0
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
    /* Each call supplies only its own code range and private stack. */
    .macro call_domain name, caller_int, caller_fp, local_int, code
    li      s3, \caller_int
    li      t0, \caller_fp
    fmv.d.x fs3, t0
    la      a0, \name\()_entry
    la      a1, \name\()_end
    la      a2, \name\()_stack_bottom
    la      a3, \name\()_stack_top
    call    sequence_gate

    mv      t1, a0
    li      a0, \code
    li      t0, \local_int
    bne     t1, t0, sequence_finish
    li      a0, \code + 1
    li      t0, \caller_int
    bne     s3, t0, sequence_finish
    li      a0, \code + 2
    fmv.x.d t1, fs3
    li      t0, \caller_fp
    bne     t1, t0, sequence_finish
    li      a0, \code + 3
    la      t0, a_stack_top
    bne     sp, t0, sequence_finish
    csrr    t1, CSR_DASICS_LIB_CFG
    li      t0, 3                       /* R/W retained, V cleared. */
    bne     t1, t0, sequence_finish
    csrr    t1, CSR_DASICS_JUMP_CFG
    bnez    t1, sequence_finish
    .endm

trusted_entry:
    call_domain b, A_BEFORE_B, A_FP_BEFORE_B, B_LOCAL, 40
    call_domain c, A_BEFORE_C, A_FP_BEFORE_C, C_LOCAL, 44

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

sequence_gate:
    csrr    t0, CSR_DASICS_CONTEXT_BASE
    sd      ra, CTX_RA(t0)
    sd      sp, CTX_SP(t0)
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
    .word   0x0080300b                  /* PROREG.G.I: s3 */
    .word   0x0080400b                  /* PROREG.F.I: fs3 */
    .globl gate_call, return_gate
gate_call:
    .insn   i 0x0b, 1, ra, a0, 0        /* DASICSCALL.JR */
return_gate:
    csrci   CSR_DASICS_LIB_CFG, 8
    csrci   CSR_DASICS_JUMP_CFG, 1
    .word   0x0000500b                  /* LEAVE consumes both banks. */
    csrr    t0, CSR_DASICS_CONTEXT_BASE
    ld      sp, CTX_SP(t0)
    ld      ra, CTX_RA(t0)
    ret

    .section .text.untrusted,"ax",@progbits
    .macro callee name, local_int, local_fp, deny_read, deny_jump, peer
    .balign 8
    .globl \name\()_entry, \name\()_end
\name\()_entry:
    fmv.x.d t0, fs3
    /* A taken branch within the current jump window must be permitted. */
    beqz    s3, .Lgpr_zero\@
.Lbad\@:
    li      a0, 0
    ret
.Lgpr_zero\@:
    bnez    t0, .Lbad\@
    la      t0, \name\()_stack_top
    bne     sp, t0, .Lbad\@
    addi    sp, sp, -16
    li      s3, \local_int
    li      t0, \local_fp
    fmv.d.x fs3, t0
    sd      s3, 8(sp)
    fsd     fs3, 0(sp)
    ld      a0, 8(sp)
    bne     a0, s3, .Lbad\@
    ld      t1, 0(sp)
    bne     t1, t0, .Lbad\@
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
