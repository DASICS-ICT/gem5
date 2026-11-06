/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CSR_DASICS_S_MAIN_CFG, 0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3
    .equ CSR_DASICS_LIB_CFG, 0x880
    .equ CSR_DASICS_FREASON, 0x8B3
    .equ DASICS_UENA, (1 << 1)
    .equ DASICS_SENA, (1 << 0)
    /* Mixed low bits make immediate set and clear operations observable. */
    .equ LIB_CFG_INITIAL, 0x13579BDF2468ACEF
    .equ LIB_CFG_SOURCE, 0xFEDCBA9876543210
    .equ CSR_IMMEDIATE, 0x15
    .equ LIB_CFG_SET, LIB_CFG_INITIAL | LIB_CFG_SOURCE
    .equ LIB_CFG_CLEAR, LIB_CFG_INITIAL & ~LIB_CFG_SOURCE
    .equ LIB_CFG_IMM_SET, LIB_CFG_INITIAL | CSR_IMMEDIATE
    .equ LIB_CFG_IMM_CLEAR, LIB_CFG_INITIAL & ~CSR_IMMEDIATE
    .equ RD_SENTINEL, 0xA5A5A5A5A5A5A5A5
    .equ FREASON_SENTINEL, 5
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ MSTATUS_MPP, (3 << 11)
    .equ MSTATUS_MPRV, (1 << 17)
    .equ MSTATUS_MIE, (1 << 3)
    .equ MSTATUS_MPIE, (1 << 7)

    /* Each case records two entry PCs, an input, and two allowed results. */
    .equ CASE_TRUSTED_PC, 0
    .equ CASE_UNTRUSTED_PC, 8
    .equ CASE_SOURCE, 16
    .equ CASE_RD, 24
    .equ CASE_VALUE, 32
    .equ CASE_SIZE, 40

    /* No runtime initializes gp; fixed-width instructions allow mepc += 4. */
    .option norelax
    .option nopic
    .option norvc
    .section .text.init
    .globl _start
_start:
    la      t0, trap_handler
    csrw    mtvec, t0
    csrw    mie, zero
    csrw    mideleg, zero
    csrw    medeleg, zero
    csrw    satp, zero

    /* Allow S/U access to code and data in [0, 0x90000000) using TOR. */
    li      t0, 0x24000000
    csrw    pmpaddr0, t0
    li      t0, 0x0f
    csrw    pmpcfg0, t0

    /* s3 is the non-virtualized privilege under test: U first, then S. */
    li      s3, PRV_U
.Lstart_domain:
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, zero
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, zero
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, zero
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, zero

    /* s0 selects a table row; s2 is its one-based diagnostic case number. */
    li      s0, 0
    li      s2, 0
    /* s1 selects traps: 0/1 harness, 2 disabled, 3 trusted, 4/5 rejected. */
    li      s1, 0
    la      t0, mode_entry
enter_lower_mode:
    csrw    mepc, t0
    li      t0, MSTATUS_MPP | MSTATUS_MPRV | MSTATUS_MIE | MSTATUS_MPIE
    csrc    mstatus, t0
    slli    t0, s3, 11
    csrs    mstatus, t0
    mret

mode_entry:
    li      a0, 0x5678
mode_ecall_first:
    ecall
    addi    a0, a0, 1
mode_ecall_second:
    ecall
    j       halt

    /* Emit the instruction pair and its expectations from the same case. */
    .macro DEFINE_CSR_CASE name, op, rd, operand, source, old, value
    .balign 8
mode_\name\()_trusted:
    \op     \rd, CSR_DASICS_LIB_CFG, \operand
    ecall
mode_\name\()_untrusted:
    \op     \rd, CSR_DASICS_LIB_CFG, \operand
    ecall
    j       halt

    .pushsection .rodata
    .dword  mode_\name\()_trusted, mode_\name\()_untrusted
    .dword  \source, \old, \value
    .popsection
    .endm

    .pushsection .rodata
    .balign 8
csr_cases:
    .popsection

    DEFINE_CSR_CASE csrrw, csrrw, a0, a1, LIB_CFG_SOURCE, \
                    LIB_CFG_INITIAL, LIB_CFG_SOURCE
    DEFINE_CSR_CASE csrrs, csrrs, a0, a1, LIB_CFG_SOURCE, \
                    LIB_CFG_INITIAL, LIB_CFG_SET
    DEFINE_CSR_CASE csrrc, csrrc, a0, a1, LIB_CFG_SOURCE, \
                    LIB_CFG_INITIAL, LIB_CFG_CLEAR
    DEFINE_CSR_CASE csrrwi, csrrwi, a0, CSR_IMMEDIATE, CSR_IMMEDIATE, \
                    LIB_CFG_INITIAL, CSR_IMMEDIATE
    DEFINE_CSR_CASE csrrsi, csrrsi, a0, CSR_IMMEDIATE, CSR_IMMEDIATE, \
                    LIB_CFG_INITIAL, LIB_CFG_IMM_SET
    DEFINE_CSR_CASE csrrci, csrrci, a0, CSR_IMMEDIATE, CSR_IMMEDIATE, \
                    LIB_CFG_INITIAL, LIB_CFG_IMM_CLEAR
    DEFINE_CSR_CASE csrrw_rd_zero, csrrw, zero, a1, LIB_CFG_SOURCE, \
                    RD_SENTINEL, LIB_CFG_SOURCE
    DEFINE_CSR_CASE csrrwi_rd_zero, csrrwi, zero, CSR_IMMEDIATE, \
                    CSR_IMMEDIATE, RD_SENTINEL, CSR_IMMEDIATE
    DEFINE_CSR_CASE csrrs_rs1_zero, csrrs, a0, zero, 0, \
                    LIB_CFG_INITIAL, LIB_CFG_INITIAL
    DEFINE_CSR_CASE csrrc_rs1_zero, csrrc, a0, zero, 0, \
                    LIB_CFG_INITIAL, LIB_CFG_INITIAL
    DEFINE_CSR_CASE csrrsi_uimm_zero, csrrsi, a0, 0, 0, \
                    LIB_CFG_INITIAL, LIB_CFG_INITIAL
    DEFINE_CSR_CASE csrrci_uimm_zero, csrrci, a0, 0, 0, \
                    LIB_CFG_INITIAL, LIB_CFG_INITIAL

    .pushsection .rodata
csr_cases_end:
    .popsection

    .balign 4
trap_handler:
    /* ra, t0/t1, a2/a3 and s0-s3 are reserved; a0/a1 hold case operands. */
    csrr    a3, mcause
    li      a2, 1
    li      t0, 4
    beq     s1, t0, .Lexpect_illegal
    /* The ECALL cause is 8 for U and 9 for non-virtualized S. */
    addi    t0, s3, 8
    j       .Lcheck_cause
.Lexpect_illegal:
    li      t0, 2
.Lcheck_cause:
    bne     a3, t0, exit_test

    li      a2, 2
    csrr    t0, mstatus
    li      t1, MSTATUS_MPP
    and     t0, t0, t1
    slli    t1, s3, 11
    bne     t0, t1, exit_test

    csrr    t0, mepc
    beqz    s1, .Lfirst_trap
    li      t1, 1
    beq     s1, t1, .Lsecond_trap
    li      t1, 2
    beq     s1, t1, .Ldisabled_trap
    li      t1, 3
    beq     s1, t1, .Ltrusted_trap
    li      t1, 4
    beq     s1, t1, .Lillegal_trap
    li      t1, 5
    beq     s1, t1, .Lresumed_trap
    li      a2, 3
    j       exit_test

.Lsecond_trap:
    li      a2, 6
    la      t1, mode_ecall_second
    bne     t0, t1, exit_test
    li      a2, 7
    li      t1, 0x5679
    bne     a0, t1, exit_test

    la      s0, csr_cases
    li      s2, 1
.Lstart_case:
    /* Every form starts with protection disabled and its own main bound. */
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    ld      t0, CASE_TRUSTED_PC(s0)
    ld      t1, CASE_UNTRUSTED_PC(s0)
    beqz    s3, .Lset_u_bounds
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t1
    j       .Lbounds_ready
.Lset_u_bounds:
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t1
.Lbounds_ready:
    li      s1, 2
    j       .Lstart_untrusted

.Lfirst_trap:
    li      a2, 4
    la      t1, mode_ecall_first
    bne     t0, t1, exit_test
    li      a2, 5
    li      t1, 0x5678
    bne     a0, t1, exit_test
    li      s1, 1
    addi    t0, t0, 4
    csrw    mepc, t0
    mret

.Ldisabled_trap:
    li      a2, 8
    ld      t1, CASE_UNTRUSTED_PC(s0)
    addi    t1, t1, 4
    bne     t0, t1, exit_test
    j       .Lcheck_allowed

.Ltrusted_trap:
    li      a2, 9
    ld      t1, CASE_TRUSTED_PC(s0)
    addi    t1, t1, 4
    bne     t0, t1, exit_test

.Lcheck_allowed:
    li      a2, 10
    ld      t0, CASE_RD(s0)
    bne     a0, t0, exit_test
    li      a2, 11
    csrr    t0, CSR_DASICS_LIB_CFG
    ld      t1, CASE_VALUE(s0)
    bne     t0, t1, exit_test
    li      a2, 12
    csrr    t0, CSR_DASICS_FREASON
    li      t1, FREASON_SENTINEL
    bne     t0, t1, exit_test

    li      t0, 2
    beq     s1, t0, .Lstart_trusted
    li      s1, 4
    j       .Lstart_untrusted

.Lstart_trusted:
    li      t0, DASICS_UENA
    beqz    s3, .Lenable_domain
    li      t0, DASICS_SENA
.Lenable_domain:
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      s1, 3
    call    prepare_lib_cfg
    ld      t0, CASE_TRUSTED_PC(s0)
    j       enter_lower_mode

.Lstart_untrusted:
    /* Both protection settings use the same out-of-bound CSR instruction. */
    call    prepare_lib_cfg
    ld      t0, CASE_UNTRUSTED_PC(s0)
    j       enter_lower_mode

.Lillegal_trap:
    li      a2, 13
    ld      t1, CASE_UNTRUSTED_PC(s0)
    bne     t0, t1, exit_test
    li      a2, 14
    /* Illegal-instruction MTVAL contains the zero-extended instruction. */
    lwu     t1, 0(t0)
    csrr    t0, mtval
    bne     t0, t1, exit_test
    j       .Lcheck_rejected

.Lresumed_trap:
    li      a2, 18
    ld      t1, CASE_UNTRUSTED_PC(s0)
    addi    t1, t1, 4
    bne     t0, t1, exit_test

.Lcheck_rejected:
    li      a2, 15
    li      t0, RD_SENTINEL
    bne     a0, t0, exit_test
    li      a2, 16
    csrr    t0, CSR_DASICS_LIB_CFG
    li      t1, LIB_CFG_INITIAL
    bne     t0, t1, exit_test
    li      a2, 17
    csrr    t0, CSR_DASICS_FREASON
    li      t1, FREASON_SENTINEL
    bne     t0, t1, exit_test

    li      t0, 5
    beq     s1, t0, .Lnext_case
    li      s1, 5
    csrr    t0, mepc
    addi    t0, t0, 4
    csrw    mepc, t0
    mret

.Lnext_case:
    /* Advance only after the rejected instruction and its return checks. */
    addi    s0, s0, CASE_SIZE
    la      t0, csr_cases_end
    beq     s0, t0, .Lnext_domain
    addi    s2, s2, 1
    j       .Lstart_case

.Lnext_domain:
    li      t0, PRV_S
    beq     s3, t0, .Lsuccess
    li      s3, PRV_S
    j       .Lstart_domain

.Lsuccess:
    li      a2, 0
    j       exit_test

prepare_lib_cfg:
    /* M mode resets each case independently, including the CSR operands. */
    li      t0, LIB_CFG_INITIAL
    csrw    CSR_DASICS_LIB_CFG, t0
    li      t0, FREASON_SENTINEL
    csrw    CSR_DASICS_FREASON, t0
    li      a0, RD_SENTINEL
    ld      a1, CASE_SOURCE(s0)
    ret

exit_test:
    la      a1, exit_args
    sd      a2, 8(a1)
    li      a0, 0x20

    /* Keep all three semihosting marker instructions within one page. */
    .balign 16
semihost_exit:
    slli    zero, zero, 0x1f
    ebreak
    srai    zero, zero, 7

halt:
    j       halt

    .section .data
    .balign 8
exit_args:
    .dword  0x20026
    .dword  0
