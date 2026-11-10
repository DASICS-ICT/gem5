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
    .equ DASICS_CUET, (1 << 2)
    .equ DASICS_CSET, (1 << 6)
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

    /* Boundary rows keep the interval and expected result independent. */
    .equ BOUND_LO, 0
    .equ BOUND_HI, 8
    .equ BOUND_ENABLED, 16
    .equ BOUND_ALLOWED, 24
    .equ BOUND_SIZE, 32

    /* Address rows hold two probes, an M-mode reader and minimum privilege. */
    .equ ACCESS_TRUSTED_PC, 0
    .equ ACCESS_UNTRUSTED_PC, 8
    .equ ACCESS_READER_PC, 16
    .equ ACCESS_MIN_PRIV, 24
    .equ ACCESS_SIZE, 32

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
    /* s4 preserves a target CSR snapshot; s5 selects its access scenario. */
    li      s4, 0
    li      s5, 0
    /* s1 selects entry 0/1, forms 2-5, boundaries 6-8, addresses 9-11,
     * or ordinary CSR controls 12/13. */
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

    /* A fixed probe separates interval geometry from instruction coverage. */
    .balign 8
boundary_probe:
    csrrw   a0, CSR_DASICS_LIB_CFG, a1
boundary_ecall:
    ecall
    j       halt

    .pushsection .rodata
    .balign 8
boundary_cases:
    /* PC = Lo - 8; enabled first, then disabled. */
    .dword  boundary_probe + 8, boundary_probe + 24, 1, 0
    .dword  boundary_probe + 8, boundary_probe + 24, 0, 1
    /* PC = Lo. */
    .dword  boundary_probe, boundary_probe + 16, 1, 1
    .dword  boundary_probe, boundary_probe + 16, 0, 1
    /* PC = Hi - 8, distinct from Lo in this 16-byte interval. */
    .dword  boundary_probe - 8, boundary_probe + 8, 1, 1
    .dword  boundary_probe - 8, boundary_probe + 8, 0, 1
    /* PC = Hi. */
    .dword  boundary_probe - 16, boundary_probe, 1, 0
    .dword  boundary_probe - 16, boundary_probe, 0, 1
    /* Empty interval. */
    .dword  boundary_probe, boundary_probe, 1, 0
    .dword  boundary_probe, boundary_probe, 0, 1
    /* Reversed interval. */
    .dword  boundary_probe + 8, boundary_probe - 8, 1, 0
    .dword  boundary_probe + 8, boundary_probe - 8, 0, 1
boundary_cases_end:
    .popsection

    /* Minimum privilege comes from the architectural CSR address encoding. */
    .macro DEFINE_ACCESS_PROBE name, csr
    .balign 8
access_\name\()_trusted:
    csrrs   a0, \csr, zero
    ecall
access_\name\()_untrusted:
    csrrs   a0, \csr, zero
    ecall
    j       halt
access_\name\()_read:
    csrrs   t0, \csr, zero
    ret
    .pushsection .rodata
    .dword  access_\name\()_trusted, access_\name\()_untrusted
    .dword  access_\name\()_read, ((\csr >> 8) & 3)
    .popsection
    .endm

    .pushsection .rodata
    .balign 8
access_cases:
    .popsection

    DEFINE_ACCESS_PROBE lib_cfg              , 0x880
    DEFINE_ACCESS_PROBE lib_bound_lo0        , 0x890
    DEFINE_ACCESS_PROBE lib_bound_hi0        , 0x891
    DEFINE_ACCESS_PROBE lib_bound_lo1        , 0x892
    DEFINE_ACCESS_PROBE lib_bound_hi1        , 0x893
    DEFINE_ACCESS_PROBE lib_bound_lo2        , 0x894
    DEFINE_ACCESS_PROBE lib_bound_hi2        , 0x895
    DEFINE_ACCESS_PROBE lib_bound_lo3        , 0x896
    DEFINE_ACCESS_PROBE lib_bound_hi3        , 0x897
    DEFINE_ACCESS_PROBE lib_bound_lo4        , 0x898
    DEFINE_ACCESS_PROBE lib_bound_hi4        , 0x899
    DEFINE_ACCESS_PROBE lib_bound_lo5        , 0x89A
    DEFINE_ACCESS_PROBE lib_bound_hi5        , 0x89B
    DEFINE_ACCESS_PROBE lib_bound_lo6        , 0x89C
    DEFINE_ACCESS_PROBE lib_bound_hi6        , 0x89D
    DEFINE_ACCESS_PROBE lib_bound_lo7        , 0x89E
    DEFINE_ACCESS_PROBE lib_bound_hi7        , 0x89F
    DEFINE_ACCESS_PROBE lib_bound_lo8        , 0x8A0
    DEFINE_ACCESS_PROBE lib_bound_hi8        , 0x8A1
    DEFINE_ACCESS_PROBE lib_bound_lo9        , 0x8A2
    DEFINE_ACCESS_PROBE lib_bound_hi9        , 0x8A3
    DEFINE_ACCESS_PROBE lib_bound_lo10       , 0x8A4
    DEFINE_ACCESS_PROBE lib_bound_hi10       , 0x8A5
    DEFINE_ACCESS_PROBE lib_bound_lo11       , 0x8A6
    DEFINE_ACCESS_PROBE lib_bound_hi11       , 0x8A7
    DEFINE_ACCESS_PROBE lib_bound_lo12       , 0x8A8
    DEFINE_ACCESS_PROBE lib_bound_hi12       , 0x8A9
    DEFINE_ACCESS_PROBE lib_bound_lo13       , 0x8AA
    DEFINE_ACCESS_PROBE lib_bound_hi13       , 0x8AB
    DEFINE_ACCESS_PROBE lib_bound_lo14       , 0x8AC
    DEFINE_ACCESS_PROBE lib_bound_hi14       , 0x8AD
    DEFINE_ACCESS_PROBE lib_bound_lo15       , 0x8AE
    DEFINE_ACCESS_PROBE lib_bound_hi15       , 0x8AF
    DEFINE_ACCESS_PROBE main_call_entry      , 0x8B0
    DEFINE_ACCESS_PROBE return_pc            , 0x8B1
    DEFINE_ACCESS_PROBE active_zone_return_pc, 0x8B2
    DEFINE_ACCESS_PROBE freason              , 0x8B3
    DEFINE_ACCESS_PROBE jump_cfg             , 0x8C8
    DEFINE_ACCESS_PROBE jump_bound_lo0       , 0x8C0
    DEFINE_ACCESS_PROBE jump_bound_hi0       , 0x8C1
    DEFINE_ACCESS_PROBE jump_bound_lo1       , 0x8C2
    DEFINE_ACCESS_PROBE jump_bound_hi1       , 0x8C3
    DEFINE_ACCESS_PROBE jump_bound_lo2       , 0x8C4
    DEFINE_ACCESS_PROBE jump_bound_hi2       , 0x8C5
    DEFINE_ACCESS_PROBE jump_bound_lo3       , 0x8C6
    DEFINE_ACCESS_PROBE jump_bound_hi3       , 0x8C7
    DEFINE_ACCESS_PROBE u_main_cfg           , 0x9E1
    DEFINE_ACCESS_PROBE u_main_bound_lo      , 0x9E2
    DEFINE_ACCESS_PROBE u_main_bound_hi      , 0x9E3
    DEFINE_ACCESS_PROBE s_main_cfg           , 0xBC0
    DEFINE_ACCESS_PROBE s_main_bound_lo      , 0xBC2
    DEFINE_ACCESS_PROBE s_main_bound_hi      , 0xBC3

    .pushsection .rodata
access_cases_end:
    .popsection

    .balign 8
ordinary_cycle_probe:
    csrrs   a0, cycle, zero
ordinary_cycle_ecall:
    ecall
    j       halt

    .balign 8
ordinary_sscratch_probe:
    csrrw   a0, sscratch, a1
ordinary_sscratch_ecall:
    ecall
    j       halt

    .balign 4
trap_handler:
    /* ra, t0/t1, a2/a3 and s0-s5 are reserved; a0/a1 hold case operands. */
    csrr    a3, mcause
    li      a2, 1
    li      t0, 4
    beq     s1, t0, .Lexpect_illegal
    li      t0, 7
    beq     s1, t0, .Lexpect_illegal
    li      t0, 10
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
    li      t1, 6
    beq     s1, t1, .Lboundary_allowed
    li      t1, 7
    beq     s1, t1, .Lboundary_illegal
    li      t1, 8
    beq     s1, t1, .Lboundary_resumed
    li      t1, 9
    beq     s1, t1, .Laccess_allowed
    li      t1, 10
    beq     s1, t1, .Laccess_illegal
    li      t1, 11
    beq     s1, t1, .Laccess_resumed
    li      t1, 12
    beq     s1, t1, .Lordinary_cycle
    li      t1, 13
    beq     s1, t1, .Lordinary_sscratch
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
    call    set_main_bound
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
    ld      t0, CASE_RD(s0)
    ld      t1, CASE_VALUE(s0)
    call    check_allowed_state

    li      t0, 2
    beq     s1, t0, .Lstart_trusted
    li      s1, 4
    j       .Lstart_untrusted

.Lstart_trusted:
    call    enable_domain
    li      s1, 3
    call    prepare_lib_cfg
    ld      a1, CASE_SOURCE(s0)
    ld      t0, CASE_TRUSTED_PC(s0)
    j       enter_lower_mode

.Lstart_untrusted:
    /* Both protection settings use the same out-of-bound CSR instruction. */
    call    prepare_lib_cfg
    ld      a1, CASE_SOURCE(s0)
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
    call    check_rejected_state

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
    beq     s0, t0, .Lstart_boundary_suite
    addi    s2, s2, 1
    j       .Lstart_case

.Lstart_boundary_suite:
    la      s0, boundary_cases
    li      s2, 1
.Lstart_boundary_case:
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    ld      t0, BOUND_LO(s0)
    ld      t1, BOUND_HI(s0)
    call    set_main_bound
    ld      t0, BOUND_ENABLED(s0)
    beqz    t0, .Lboundary_configured
    call    enable_domain
.Lboundary_configured:
    call    prepare_lib_cfg
    li      a1, LIB_CFG_SOURCE
    /* The table states the expected result without recomputing trust. */
    li      s1, 6
    ld      t0, BOUND_ALLOWED(s0)
    bnez    t0, .Lenter_boundary
    li      s1, 7
.Lenter_boundary:
    la      t0, boundary_probe
    j       enter_lower_mode

.Lboundary_allowed:
    li      a2, 19
    la      t1, boundary_ecall
    bne     t0, t1, exit_test
    li      t0, LIB_CFG_INITIAL
    li      t1, LIB_CFG_SOURCE
    call    check_allowed_state
    j       .Lnext_boundary_case

.Lboundary_illegal:
    li      a2, 13
    la      t1, boundary_probe
    bne     t0, t1, exit_test
    li      a2, 14
    lwu     t1, 0(t0)
    csrr    t0, mtval
    bne     t0, t1, exit_test
    j       .Lboundary_rejected

.Lboundary_resumed:
    li      a2, 20
    la      t1, boundary_ecall
    bne     t0, t1, exit_test
.Lboundary_rejected:
    call    check_rejected_state
    li      t0, 8
    beq     s1, t0, .Lnext_boundary_case
    li      s1, 8
    csrr    t0, mepc
    addi    t0, t0, 4
    csrw    mepc, t0
    mret

.Lnext_boundary_case:
    addi    s0, s0, BOUND_SIZE
    la      t0, boundary_cases_end
    beq     s0, t0, .Lstart_access_suite
    addi    s2, s2, 1
    j       .Lstart_boundary_case

.Lstart_access_suite:
    la      s0, access_cases
    li      s2, 1
.Lstart_access_case:
    /* s5 selects disabled/outside, enabled/inside, then enabled/outside. */
    li      s5, 0
.Lstart_access_scenario:
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    ld      t0, ACCESS_TRUSTED_PC(s0)
    ld      t1, ACCESS_UNTRUSTED_PC(s0)
    call    set_main_bound
    beqz    s5, .Laccess_configured
    call    enable_domain
.Laccess_configured:
    call    prepare_lib_cfg
    /* Snapshot after configuration, since MainCfg/MainBound may be read. */
    ld      t0, ACCESS_READER_PC(s0)
    jalr    ra, t0, 0
    mv      s4, t0

    /* Ordinary privilege failures are expected in all three scenarios. */
    li      s1, 10
    ld      t1, ACCESS_MIN_PRIV(s0)
    bltu    s3, t1, .Lenter_access
    li      t1, 2
    beq     s5, t1, .Lenter_access
    li      s1, 9
.Lenter_access:
    call    get_access_pc
    mv      t0, t1
    j       enter_lower_mode

.Laccess_allowed:
    li      a2, 21
    call    get_access_pc
    addi    t1, t1, 4
    bne     t0, t1, exit_test
    li      a2, 22
    bne     a0, s4, exit_test
    ld      t0, ACCESS_READER_PC(s0)
    jalr    ra, t0, 0
    li      a2, 23
    bne     t0, s4, exit_test
    call    check_protection_state
    j       .Lnext_access_scenario

.Laccess_illegal:
    li      a2, 13
    call    get_access_pc
    bne     t0, t1, exit_test
    li      a2, 14
    lwu     t1, 0(t0)
    csrr    t0, mtval
    bne     t0, t1, exit_test
    j       .Laccess_rejected

.Laccess_resumed:
    li      a2, 21
    call    get_access_pc
    addi    t1, t1, 4
    bne     t0, t1, exit_test
.Laccess_rejected:
    call    check_rejected_state
    ld      t0, ACCESS_READER_PC(s0)
    jalr    ra, t0, 0
    li      a2, 23
    bne     t0, s4, exit_test
    li      t0, 11
    beq     s1, t0, .Lnext_access_scenario
    li      s1, 11
    csrr    t0, mepc
    addi    t0, t0, 4
    csrw    mepc, t0
    mret

.Lnext_access_scenario:
    addi    s5, s5, 1
    li      t0, 3
    bltu    s5, t0, .Lstart_access_scenario
    addi    s0, s0, ACCESS_SIZE
    la      t0, access_cases_end
    beq     s0, t0, .Lstart_ordinary_controls
    addi    s2, s2, 1
    j       .Lstart_access_case

.Lstart_ordinary_controls:
    /* Empty active bounds make both ordinary controls untrusted. */
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    li      t0, 0
    li      t1, 0
    call    set_main_bound
    call    enable_domain
    /* Permit cycle reads through the standard counter-access mechanism. */
    li      t0, 1
    csrw    mcounteren, t0
    csrw    scounteren, t0
    call    prepare_lib_cfg
    li      s1, 12
    li      s2, 1
    la      t0, ordinary_cycle_probe
    j       enter_lower_mode

.Lordinary_cycle:
    li      a2, 24
    la      t1, ordinary_cycle_ecall
    bne     t0, t1, exit_test
    li      a2, 25
    li      t0, RD_SENTINEL
    beq     a0, t0, exit_test
    call    check_protection_state
    beqz    s3, .Lnext_domain

    li      t0, LIB_CFG_INITIAL
    csrw    sscratch, t0
    call    prepare_lib_cfg
    li      a1, LIB_CFG_SOURCE
    li      s1, 13
    li      s2, 2
    la      t0, ordinary_sscratch_probe
    j       enter_lower_mode

.Lordinary_sscratch:
    li      a2, 26
    la      t1, ordinary_sscratch_ecall
    bne     t0, t1, exit_test
    li      a2, 27
    li      t0, LIB_CFG_INITIAL
    bne     a0, t0, exit_test
    li      a2, 28
    csrr    t0, sscratch
    li      t1, LIB_CFG_SOURCE
    bne     t0, t1, exit_test
    call    check_protection_state
    j       .Lnext_domain

.Lnext_domain:
    li      t0, PRV_S
    beq     s3, t0, .Lsuccess
    li      s3, PRV_S
    j       .Lstart_domain

.Lsuccess:
    li      a2, 0
    j       exit_test

get_access_pc:
    /* Return the selected probe PC in t1 without clobbering trap PC t0. */
    li      t1, 1
    beq     s5, t1, .Lget_trusted_access_pc
    ld      t1, ACCESS_UNTRUSTED_PC(s0)
    ret
.Lget_trusted_access_pc:
    ld      t1, ACCESS_TRUSTED_PC(s0)
    ret

set_main_bound:
    /* t0/t1 hold the lower/upper bounds for the selected domain. */
    beqz    s3, .Lset_u_bounds
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t1
    ret
.Lset_u_bounds:
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t1
    ret

enable_domain:
    /* ECALL signals completion to the harness through ordinary traps. */
    li      t0, DASICS_UENA | DASICS_CUET
    beqz    s3, .Lenable_domain
    li      t0, DASICS_SENA | DASICS_CSET
.Lenable_domain:
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    ret

check_allowed_state:
    /* t0/t1 supply the expected a0/LibCfg values; both are scratch. */
    li      a2, 10
    bne     a0, t0, exit_test
    li      a2, 11
    csrr    t0, CSR_DASICS_LIB_CFG
    bne     t0, t1, exit_test
    li      a2, 12
    csrr    t0, CSR_DASICS_FREASON
    li      t1, FREASON_SENTINEL
    bne     t0, t1, exit_test
    ret

check_rejected_state:
    li      a2, 15
    li      t0, RD_SENTINEL
    bne     a0, t0, exit_test
check_protection_state:
    /* Read-only and ordinary controls preserve these DASICS sentinels. */
    li      a2, 16
    csrr    t0, CSR_DASICS_LIB_CFG
    li      t1, LIB_CFG_INITIAL
    bne     t0, t1, exit_test
    li      a2, 17
    csrr    t0, CSR_DASICS_FREASON
    li      t1, FREASON_SENTINEL
    bne     t0, t1, exit_test
    ret

prepare_lib_cfg:
    /* M mode resets each case independently, including the CSR operands. */
    li      t0, LIB_CFG_INITIAL
    csrw    CSR_DASICS_LIB_CFG, t0
    li      t0, FREASON_SENTINEL
    csrw    CSR_DASICS_FREASON, t0
    li      a0, RD_SENTINEL
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
