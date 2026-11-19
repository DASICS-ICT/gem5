/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CSR_DASICS_S_MAIN_CFG,      0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3
    .equ DASICS_SENA, 1 << 0
    .equ DASICS_UENA, 1 << 1
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ ILLEGAL, 2
    .equ BREAKPOINT, 3
    .equ MSTATUS_MPP, 3 << 11
    /* custom-0, funct3=3, rd=rs1=0, imm12=0x008 (s3). */
    .equ PROREG_G_I_S3, 0x0080300B

    .option norelax
    .option nopic
    .option norvc
    .section .text.init
    .globl _start
_start:
    li      s1, 255
    la      s6, setup_failure
    la      t0, machine_trap
    csrw    mtvec, t0
    csrw    mie, zero
    csrw    medeleg, zero
    csrw    satp, zero
    /* The test image lies below the PMP TOR upper bound 0x90000000. */
    li      t0, 0x24000000
    csrw    pmpaddr0, t0
    li      t0, 0x0F
    csrw    pmpcfg0, t0

    la      t0, probe_a
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    la      t0, probe_a_end
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t0
    la      t0, probe_b
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    la      t0, probe_b_end
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    li      t0, DASICS_UENA | DASICS_SENA
    csrw    CSR_DASICS_S_MAIN_CFG, t0

    la      s0, cases
    li      s1, 1
start_case:
    ld      t0, 0(s0)               /* Probe entry PC. */
    ld      s2, 8(s0)               /* Expected source privilege. */
    ld      s4, 16(s0)              /* Expected mcause. */
    ld      s5, 24(s0)              /* Expected mepc. */
    ld      s6, 32(s0)              /* Failure message. */
    li      a5, 0
    csrw    mepc, t0
    li      t0, MSTATUS_MPP
    csrc    mstatus, t0
    slli    t0, s2, 11
    csrs    mstatus, t0
    mret

    /* a5 becomes architecturally visible only after PROREG retires. */
    .macro PROBE name
    .balign 8
\name:
    .word   PROREG_G_I_S3
    addi    a5, zero, 1
\name\()_break:
    ebreak
    .balign 8
\name\()_end:
    .endm
    PROBE probe_a
    PROBE probe_b

    .balign 4
machine_trap:
    csrr    t0, mstatus
    srli    t0, t0, 11
    andi    t0, t0, 3
    li      t1, 3
    beq     t0, t1, fail            /* A trap from the M-mode driver. */
    bne     t0, s2, fail
    csrr    t0, mcause
    bne     t0, s4, fail
    csrr    t0, mepc
    bne     t0, s5, fail
    li      t0, BREAKPOINT
    bne     s4, t0, check_illegal
    li      t0, 1
    bne     a5, t0, fail
    j       case_passed
check_illegal:
    bnez    a5, fail
    csrr    t0, mtval
    li      t1, PROREG_G_I_S3
    bne     t0, t1, fail
case_passed:
    addi    s0, s0, 40
    addi    s1, s1, 1
    la      t0, cases_end
    bne     s0, t0, start_case
    li      a2, 0
    j       exit_test

fail:
    li      a0, 0x04                /* SYS_WRITE0 */
    mv      a1, s6
    .balign 16
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
    mv      a2, s1
exit_test:
    la      a1, exit_args
    sd      a2, 8(a1)
    fence   rw, rw
    li      a0, 0x20                /* SYS_EXIT_EXTENDED */
    .balign 16
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
halt:
    j       halt

    .section .rodata
    .balign 8
cases:
    .dword probe_a, PRV_U, BREAKPOINT, probe_a_break, trusted_u_failure
    .dword probe_b, PRV_S, BREAKPOINT, probe_b_break, trusted_s_failure
    .dword probe_b, PRV_U, ILLEGAL,    probe_b,       untrusted_u_failure
    .dword probe_a, PRV_S, ILLEGAL,    probe_a,       untrusted_s_failure
cases_end:
setup_failure:       .asciz "PROREG.G.I: setup failed\n"
trusted_u_failure:   .asciz "PROREG.G.I: trusted U failed\n"
trusted_s_failure:   .asciz "PROREG.G.I: trusted S failed\n"
untrusted_u_failure: .asciz "PROREG.G.I: untrusted U failed\n"
untrusted_s_failure: .asciz "PROREG.G.I: untrusted S failed\n"

    .section .data
    .balign 8
exit_args:
    .dword  0x20026, 0
