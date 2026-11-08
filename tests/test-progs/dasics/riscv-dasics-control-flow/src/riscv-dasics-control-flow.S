/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CSR_DASICS_S_MAIN_CFG, 0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3
    .equ CSR_DASICS_MAIN_CALL_ENTRY, 0x8B0
    .equ CSR_DASICS_RETURN_PC, 0x8B1
    .equ CSR_DASICS_ACTIVE_ZONE_RETURN_PC, 0x8B2
    .equ CSR_DASICS_FREASON, 0x8B3
    .equ CSR_DASICS_JUMP_BOUND_LO0, 0x8C0
    .equ CSR_DASICS_JUMP_BOUND_HI0, 0x8C1
    .equ CSR_DASICS_JUMP_CFG, 0x8C8

    .equ DASICS_SENA, (1 << 0)
    .equ DASICS_UENA, (1 << 1)
    .equ DASICS_CUET, (1 << 2)
    .equ DASICS_CUST, (1 << 3)
    .equ DASICS_CULT, (1 << 4)
    .equ DASICS_CSET, (1 << 6)
    .equ DASICS_CSST, (1 << 7)
    .equ DASICS_CSLT, (1 << 8)
    /* Keep U/S control-flow checks enabled; isolate other check classes. */
    .equ MAIN_CFG, DASICS_SENA | DASICS_UENA | DASICS_CUET | DASICS_CUST \
                  | DASICS_CULT | DASICS_CSET | DASICS_CSST | DASICS_CSLT
    .equ FREASON_SENTINEL, 5
    .equ FREASON_JUMP, 4
    .equ RA_SENTINEL, 0xA5A5A5A5A5A5A5A5
    .equ TARGET_MARKER, 0x1234
    .equ RESUME_MARKER, 0x5678
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ PRV_M, 3
    .equ CAUSE_U_ECALL, 8
    .equ CAUSE_U_DASICS, 24

    .equ MSTATUS_SIE, (1 << 1)
    .equ MSTATUS_MIE, (1 << 3)
    .equ MSTATUS_SPIE, (1 << 5)
    .equ MSTATUS_MPIE, (1 << 7)
    .equ MSTATUS_MPP, (3 << 11)
    .equ MSTATUS_MPRV, (1 << 17)
    .equ MSTATUS_TSR, (1 << 22)
    .equ ENTRY_STATUS_CLEAR, MSTATUS_SIE | MSTATUS_MIE | MSTATUS_SPIE \
                            | MSTATUS_MPIE | MSTATUS_MPP | MSTATUS_MPRV \
                            | MSTATUS_TSR

    .equ CASE_SOURCE, 0
    .equ CASE_DELEGATED, 8
    .equ CASE_COMPLETES, 16
    .equ CASE_PROBE, 24
    .equ CASE_RS1, 32
    .equ CASE_RS2, 40
    .equ CASE_SIZE, 48
    .equ PROBE_JALR, 0
    .equ PROBE_BEQ, 1
    .equ PROBE_BNE, 2
    .equ PROBE_BLT, 3
    .equ PROBE_BGE, 4
    .equ PROBE_BLTU, 5
    .equ PROBE_BGEU, 6
    .equ PROBE_PC, 0
    .equ PROBE_TARGET, 8
    .equ PROBE_END, 16
    .equ PROBE_ECALL, 24
    .equ PROBE_LINK, 32
    .equ PROBE_SIZE, 40
    .equ STAGE_SETUP, 0
    .equ STAGE_PROBE, 1
    .equ STAGE_RESUME, 2

    /* Print the reason separately; exit status identifies the failed case. */
    .equ FAIL_DELEGATION, 1
    .equ FAIL_SOURCE, 2
    .equ FAIL_ROUTE, 3
    .equ FAIL_STAGE, 4
    .equ FAIL_CAUSE, 5
    .equ FAIL_EPC, 6
    .equ FAIL_TVAL, 7
    .equ FAIL_FREASON, 8
    .equ FAIL_LINK, 9
    .equ FAIL_TARGET_GPR, 10
    .equ FAIL_TARGET_MEMORY, 11
    .equ FAIL_RESUME, 12

    /*
     * s0: case row; s1: one-based case ID; s2: source privilege;
     * s3: delegate to S; s4: completes without DASICS; s5: execution stage;
     * s6: accepted DASICS trap count; s7: target GPR marker;
     * s8: resume marker; s9: target memory marker address; s10: probe kind;
     * s11: probe PC; a3: expected ra after completion without DASICS.
     * a4/a5: branch operands; a6: target PC; a7: completion ECALL PC.
     * M initializes the expected state; both handlers preserve it.
     * ra remains observable throughout the test: no call/ret is used.
     * a2 carries a failure reason, including across the S failure ECALL.
     */
    .option norelax
    .option nopic
    .option norvc
    .section .text.init
    .globl _start
_start:
    li      s1, 0
    li      s2, PRV_M
    li      s5, STAGE_SETUP
    la      t0, machine_trap_handler
    csrw    mtvec, t0
    la      t0, supervisor_trap_handler
    csrw    stvec, t0
    csrw    mie, zero
    csrw    mideleg, zero
    csrw    medeleg, zero
    csrw    satp, zero
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0

    /* TOR permits lower modes to access code and data below 0x90000000. */
    li      t0, 0x24000000
    csrw    pmpaddr0, t0
    li      t0, 0x0f
    csrw    pmpcfg0, t0

    la      s0, cases
    li      s1, 1
    la      s9, target_memory_marker
start_case:
    li      s5, STAGE_SETUP
    ld      s2, CASE_SOURCE(s0)
    ld      s3, CASE_DELEGATED(s0)
    ld      s4, CASE_COMPLETES(s0)
    ld      s10, CASE_PROBE(s0)
    ld      a4, CASE_RS1(s0)
    ld      a5, CASE_RS2(s0)
    li      s6, 0
    li      s7, 0
    li      s8, 0
    sd      zero, 0(s9)

    csrw    CSR_DASICS_S_MAIN_CFG, zero
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, zero
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, zero
    /* The complete S handler is trusted; probe/target/resume are outside. */
    la      t0, supervisor_trusted_begin
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    la      t0, supervisor_trusted_end
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    csrw    CSR_DASICS_MAIN_CALL_ENTRY, zero
    csrw    CSR_DASICS_RETURN_PC, zero
    csrw    CSR_DASICS_ACTIVE_ZONE_RETURN_PC, zero

    /* Each probe has its own adjacent target and completion ECALL. */
    li      t0, PROBE_SIZE
    mul     t0, s10, t0
    la      t1, probes
    add     t0, t0, t1
    ld      s11, PROBE_PC(t0)
    ld      a6, PROBE_TARGET(t0)
    ld      t1, PROBE_END(t0)
    ld      a7, PROBE_ECALL(t0)
    ld      a3, PROBE_LINK(t0)
    csrw    CSR_DASICS_JUMP_BOUND_LO0, a6
    csrw    CSR_DASICS_JUMP_BOUND_HI0, t1
    /* Conditional targets remain unauthorized for either outcome. */
    li      t0, 0
    bnez    s10, .Lwrite_jump_cfg
    mv      t0, s4
.Lwrite_jump_cfg:
    /* Writing 0 or 1 leaves groups 1-3 invalid in every case. */
    csrw    CSR_DASICS_JUMP_CFG, t0

    /* Only the selected DASICS cause is delegated; ECALLs always reach M. */
    li      t0, 0
    beqz    s3, .Lwrite_delegation
    addi    t1, s2, CAUSE_U_DASICS
    li      t0, 1
    sll     t0, t0, t1
.Lwrite_delegation:
    csrw    medeleg, t0
    csrr    t1, medeleg
    li      a2, FAIL_DELEGATION
    bne     t0, t1, fail

    li      t0, FREASON_SENTINEL
    csrw    CSR_DASICS_FREASON, t0
    li      t0, MAIN_CFG
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      ra, RA_SENTINEL
    /* JALR clears bit 0 before checking or reporting its actual target. */
    ori     a1, a6, 1
    li      s5, STAGE_PROBE
    csrw    mepc, s11
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0
    slli    t0, s2, 11
    csrs    mstatus, t0
    mret

    .balign 8
jump_probe:
    jalr    ra, a1, 0
jump_link:
    /* Falling through the probe is never a successful test outcome. */
    ecall
    ebreak

    .macro BRANCH_PROBE name, instruction
    .balign 8
    /* Keep the target aligned without padding after the branch. */
    nop
\name\()_probe:
    /* Same next PC for both outcomes; only a taken branch must fault. */
    \instruction a4, a5, \name\()_target
\name\()_target:
    li      s7, TARGET_MARKER
    sd      s7, 0(s9)
\name\()_ecall:
    ecall
    ebreak
    .balign 8
\name\()_end:
    .endm

    BRANCH_PROBE beq, beq
    BRANCH_PROBE bne, bne
    BRANCH_PROBE blt, blt
    BRANCH_PROBE bge, bge
    BRANCH_PROBE bltu, bltu
    BRANCH_PROBE bgeu, bgeu

resume_entry:
    li      s8, RESUME_MARKER
resume_ecall:
    ecall
    ebreak

    /* Shared checks preserve ra and all case metadata in both trap modes. */
    .macro CHECK_REJECTED_STATE failure
    li      a2, FAIL_FREASON
    csrr    t0, CSR_DASICS_FREASON
    li      t1, FREASON_JUMP
    bne     t0, t1, \failure
    li      a2, FAIL_LINK
    li      t0, RA_SENTINEL
    bne     ra, t0, \failure
    li      a2, FAIL_TARGET_GPR
    bnez    s7, \failure
    li      a2, FAIL_TARGET_MEMORY
    ld      t0, 0(s9)
    bnez    t0, \failure
    .endm

    .balign 8
machine_trap_handler:
    /* Preserve the S handler's reason before installing M diagnostics. */
    csrr    t0, mepc
    la      t1, supervisor_failure_ecall
    beq     t0, t1, fail

    li      a2, FAIL_SOURCE
    csrr    t0, mstatus
    srli    t0, t0, 11
    andi    t0, t0, 3
    bne     t0, s2, fail
    csrr    t0, mcause
    addi    t1, s2, CAUSE_U_ECALL
    beq     t0, t1, .Lmachine_ecall
    li      a2, FAIL_CAUSE
    addi    t1, s2, CAUSE_U_DASICS
    bne     t0, t1, fail

    li      a2, FAIL_ROUTE
    bnez    s3, fail
    li      a2, FAIL_STAGE
    bnez    s4, fail
    li      t0, STAGE_PROBE
    bne     s5, t0, fail
    bnez    s6, fail
    li      a2, FAIL_EPC
    csrr    t0, mepc
    bne     t0, s11, fail
    li      a2, FAIL_TVAL
    csrr    t0, mtval
    bne     t0, a6, fail
    CHECK_REJECTED_STATE fail
    li      a2, FAIL_RESUME
    bnez    s8, fail
    li      s6, 1
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    mepc, t0
    mret

.Lmachine_ecall:
    beqz    s4, .Lcheck_resumed
    li      a2, FAIL_STAGE
    li      t0, STAGE_PROBE
    bne     s5, t0, fail
    bnez    s6, fail
    li      a2, FAIL_EPC
    csrr    t0, mepc
    bne     t0, a7, fail
    li      a2, FAIL_FREASON
    csrr    t0, CSR_DASICS_FREASON
    li      t1, FREASON_SENTINEL
    bne     t0, t1, fail
    li      a2, FAIL_LINK
    bne     ra, a3, fail
    li      a2, FAIL_TARGET_GPR
    li      t0, TARGET_MARKER
    bne     s7, t0, fail
    li      a2, FAIL_TARGET_MEMORY
    ld      t1, 0(s9)
    bne     t1, t0, fail
    li      a2, FAIL_RESUME
    bnez    s8, fail
    j       .Lcase_passed

.Lcheck_resumed:
    li      a2, FAIL_STAGE
    li      t0, STAGE_RESUME
    bne     s5, t0, fail
    li      t0, 1
    bne     s6, t0, fail
    li      a2, FAIL_EPC
    csrr    t0, mepc
    la      t1, resume_ecall
    bne     t0, t1, fail
    CHECK_REJECTED_STATE fail
    li      a2, FAIL_RESUME
    li      t0, RESUME_MARKER
    bne     s8, t0, fail

.Lcase_passed:
    addi    s0, s0, CASE_SIZE
    la      t0, cases_end
    beq     s0, t0, pass
    addi    s1, s1, 1
    j       start_case

    .balign 8
supervisor_trusted_begin:
supervisor_trap_handler:
    li      a2, FAIL_ROUTE
    li      t0, 1
    bne     s3, t0, supervisor_failure_ecall
    li      a2, FAIL_STAGE
    bnez    s4, supervisor_failure_ecall
    li      t0, STAGE_PROBE
    bne     s5, t0, supervisor_failure_ecall
    bnez    s6, supervisor_failure_ecall
    li      a2, FAIL_SOURCE
    csrr    t0, sstatus
    srli    t0, t0, 8
    andi    t0, t0, 1
    bne     t0, s2, supervisor_failure_ecall
    li      a2, FAIL_CAUSE
    csrr    t0, scause
    addi    t1, s2, CAUSE_U_DASICS
    bne     t0, t1, supervisor_failure_ecall
    li      a2, FAIL_EPC
    csrr    t0, sepc
    bne     t0, s11, supervisor_failure_ecall
    li      a2, FAIL_TVAL
    csrr    t0, stval
    bne     t0, a6, supervisor_failure_ecall
    CHECK_REJECTED_STATE supervisor_failure_ecall
    li      a2, FAIL_RESUME
    bnez    s8, supervisor_failure_ecall
    li      s6, 1
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    sepc, t0
    sret

supervisor_failure_ecall:
    /* S cannot use the M exit path directly; ECALL preserves a2 for M. */
    ecall
    ebreak
    .balign 8
supervisor_trusted_end:

pass:
    li      a2, 0
    j       exit_test
fail:
    /* Two decimal digits cover all cases and diagnostic reasons. */
    li      t0, 10
    la      t3, failure_case
    divu    t1, s1, t0
    remu    t2, s1, t0
    addi    t1, t1, '0'
    addi    t2, t2, '0'
    sb      t1, 0(t3)
    sb      t2, 1(t3)
    la      t3, failure_reason
    divu    t1, a2, t0
    remu    t2, a2, t0
    addi    t1, t1, '0'
    addi    t2, t2, '0'
    sb      t1, 0(t3)
    sb      t2, 1(t3)
    /* Publish the diagnostic before the host reads guest memory. */
    fence   rw, rw
    la      a1, failure_message
    li      a0, 0x04
    .balign 16
semihost_write:
    slli    zero, zero, 0x1f
    ebreak
    srai    zero, zero, 7
    mv      a2, s1
    bnez    a2, exit_test
    /* Initialization must not use the successful exit status. */
    li      a2, 255
exit_test:
    la      a1, exit_args
    sd      a2, 8(a1)
    fence   rw, rw
    li      a0, 0x20
    /* Keep the semihosting marker in a single fetch page. */
    .balign 16
semihost_exit:
    slli    zero, zero, 0x1f
    ebreak
    srai    zero, zero, 7
halt:
    j       halt

    .section .rodata
    .balign 8
probes:
    /* Source PC, target, exclusive end, completion ECALL, expected ra. */
    .dword  jump_probe, beq_target, beq_end, beq_ecall, jump_link
    .dword  beq_probe, beq_target, beq_end, beq_ecall, RA_SENTINEL
    .dword  bne_probe, bne_target, bne_end, bne_ecall, RA_SENTINEL
    .dword  blt_probe, blt_target, blt_end, blt_ecall, RA_SENTINEL
    .dword  bge_probe, bge_target, bge_end, bge_ecall, RA_SENTINEL
    .dword  bltu_probe, bltu_target, bltu_end, bltu_ecall, RA_SENTINEL
    .dword  bgeu_probe, bgeu_target, bgeu_end, bgeu_ecall, RA_SENTINEL

    .macro CASE_PAIR probe, normal_lhs, normal_rhs, fault_lhs, fault_rhs
    .dword  PRV_U, 0, 1, \probe, \normal_lhs, \normal_rhs
    .dword  PRV_U, 0, 0, \probe, \fault_lhs, \fault_rhs
    .dword  PRV_U, 1, 1, \probe, \normal_lhs, \normal_rhs
    .dword  PRV_U, 1, 0, \probe, \fault_lhs, \fault_rhs
    .dword  PRV_S, 0, 1, \probe, \normal_lhs, \normal_rhs
    .dword  PRV_S, 0, 0, \probe, \fault_lhs, \fault_rhs
    .dword  PRV_S, 1, 1, \probe, \normal_lhs, \normal_rhs
    .dword  PRV_S, 1, 0, \probe, \fault_lhs, \fault_rhs
    .endm

    .macro EQUALITY_CASES probe, completes
    .dword  PRV_U, 0, \completes, \probe, 1, 1
    .dword  PRV_U, 1, \completes, \probe, 1, 1
    .dword  PRV_S, 0, \completes, \probe, 1, 1
    .dword  PRV_S, 1, \completes, \probe, 1, 1
    .endm

cases:
    /* Source, delegation, normal completion, probe kind, lhs, rhs. */
    CASE_PAIR PROBE_JALR, 0, 0, 0, 0
    CASE_PAIR PROBE_BEQ, 1, 0, 0, 0
    CASE_PAIR PROBE_BNE, 1, 1, 1, 0
    CASE_PAIR PROBE_BLT, 1, -1, -1, 1
    CASE_PAIR PROBE_BGE, -1, 1, 1, -1
    CASE_PAIR PROBE_BLTU, -1, 1, 1, -1
    CASE_PAIR PROBE_BGEU, 1, -1, -1, 1

    /* Equality distinguishes strict comparisons from inclusive ones. */
    EQUALITY_CASES PROBE_BLT, 1
    EQUALITY_CASES PROBE_BGE, 0
    EQUALITY_CASES PROBE_BLTU, 1
    EQUALITY_CASES PROBE_BGEU, 0
cases_end:

    .section .data
    .balign 8
target_memory_marker:
    .dword  0
exit_args:
    .dword  0x20026
    .dword  0
failure_message:
    .ascii  "DASICS control-flow: case="
failure_case:
    .ascii  "00 reason="
failure_reason:
    .asciz  "00\n"
