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
    .equ CSR_DASICS_JUMP_CFG, 0x8C8
    .equ DASICS_SENA, (1 << 0)
    .equ DASICS_UENA, (1 << 1)
    .equ DASICS_CUFT, (1 << 5)
    .equ DASICS_CSFT, (1 << 9)
    /* Data/ECALL checks are closed; ordinary jump checks remain open. */
    .equ MAIN_CFG, DASICS_SENA | DASICS_UENA | (7 << 2) | (7 << 6)
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ PRV_M, 3
    .equ FREASON_SENTINEL, 5
    .equ RETURN_SENTINEL, 0x1020304050607080
    .equ RA_SENTINEL, 0xA5A5A5A5A5A5A5A5
    .equ GPR_SENTINEL, 0x0123456789ABCDEF
    .equ SOURCE_SENTINEL, 0x1111222233334444
    .equ CAPTURE_SENTINEL, 0x5566778899AABBCC
    .equ ENTRY_STATUS_CLEAR, (1 << 1) | (1 << 3) | (1 << 5) | (1 << 7) \
                            | (3 << 11) | (1 << 17) | (1 << 22)
    .equ STAGE_SETUP, 0
    .equ STAGE_PROBE, 1
    .equ STAGE_RESUME, 2
    .equ RESULT_NONE, 0
    .equ RESULT_RA, 1
    .equ RESULT_A0, 2
    .equ RESULT_A1, 3
    .equ RESULT_SUM, 4

    .equ CASE_PROBE, 0
    .equ CASE_SOURCE, 8
    .equ CASE_DELEGATED, 16
    .equ CASE_MAIN_CFG, 24
    .equ CASE_TRUSTED, 32
    .equ CASE_ILLEGAL, 40
    .equ CASE_SIZE, 48
    .equ PROBE_PC, 0
    .equ PROBE_BREAK, 8
    .equ PROBE_TARGET, 16
    .equ PROBE_RS1, 24
    .equ PROBE_RESULT, 32
    .equ PROBE_MARKER, 40
    .equ PROBE_CAPTURE, 48
    .equ PROBE_CUSTOM, 56
    .equ PROBE_SIZE, 64

    .equ FAIL_DELEGATION, 1
    .equ FAIL_SOURCE, 2
    .equ FAIL_ROUTE, 3
    .equ FAIL_STAGE, 4
    .equ FAIL_CAUSE, 5
    .equ FAIL_EPC, 6
    .equ FAIL_TVAL, 7
    .equ FAIL_FREASON, 8
    .equ FAIL_RETURN_PC, 9
    .equ FAIL_RA, 10
    .equ FAIL_A0, 11
    .equ FAIL_RS1, 12
    .equ FAIL_TARGET, 13
    .equ FAIL_COMPLETION, 14
    .equ FAIL_CAPTURE, 15

    /*
     * s0: case row; s1: ID; s2: source mode; s3: illegal delegated to S;
     * s4: expect illegal; s5: stage; s6: accepted illegal trap count;
     * s7: target marker; s8: completion marker; s9: descriptor;
     * s10: instruction PC; s11: expected ReturnPC; a7: original word.
     * ra/a0/a1 are observed link/destination/source registers. a4 captures
     * ReturnPC in trusted targets. a6 holds PC+4 for the rd=x0 return.
     * t6 carries the failure reason through an S failure breakpoint.
     */
    .option norelax
    .option nopic
    .option norvc
    .section .text.init
    .globl _start
_start:
    /* Skip padding used to exercise both extremes of the DIJ immediate. */
    la      t0, initialize
    jalr    zero, t0, 0

    .macro TARGET name, marker, link=ra, capture=0
\name:
    .if \capture
    csrr    a4, CSR_DASICS_RETURN_PC
    .endif
    li      s7, \marker
    jalr    zero, \link, 0
    ebreak
    .endm

    /* Labels and differences stay in one section; no custom linker needed. */
    .org 0x1000
    TARGET j_min_target, 3
    .org 0x400FC0
    TARGET j_negative_target, 2

    .macro CALL_J name, displacement
\name\()_probe:
    .word 0x0B | (((\displacement) & 0x7FE) << 20) \
               | (((\displacement) & 0x7800) >> 3) \
               | ((\displacement) & 0x1F8000) \
               | (((\displacement) & 0x200000) >> 14) \
               | (((\displacement) & 0x400000) << 9)
\name\()_link:
    li      s8, 1
\name\()_break:
    ebreak
    .endm

    .macro CALL_JR name, rd, rs1, immediate
    .balign 8
\name\()_probe:
    .word 0x100B | ((\rd) << 7) | ((\rs1) << 15) \
                 | (((\immediate) & 0xFFF) << 20)
\name\()_link:
    li      s8, 1
\name\()_break:
    ebreak
    .endm

    .org 0x401000
trusted_begin:
    CALL_J j_min, -0x400000

initialize:
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
    li      t0, 0x24000000
    csrw    pmpaddr0, t0
    li      t0, 0x0F
    csrw    pmpcfg0, t0
    la      s0, cases
    li      s1, 1
start_case:
    li      s5, STAGE_SETUP
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    ld      s9, CASE_PROBE(s0)
    ld      s2, CASE_SOURCE(s0)
    ld      s3, CASE_DELEGATED(s0)
    ld      s4, CASE_ILLEGAL(s0)
    ld      s10, PROBE_PC(s9)
    lwu     a7, 0(s10)
    addi    a6, s10, 4
    li      s6, 0
    li      s7, 0
    li      s8, 0
    li      s11, RETURN_SENTINEL
    bnez    s4, .Lexpected_return_ready
    ld      t0, PROBE_CUSTOM(s9)
    beqz    t0, .Lexpected_return_ready
    mv      s11, a6
.Lexpected_return_ready:
    la      t0, trusted_begin
    la      t1, trusted_end
    ld      t2, CASE_TRUSTED(s0)
    bnez    t2, .Lbounds_ready
    /* Keep the S handler trusted even when the call source is untrusted. */
    la      t0, supervisor_trusted_begin
    la      t1, supervisor_trusted_end
.Lbounds_ready:
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t1
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t1
    csrw    CSR_DASICS_JUMP_CFG, zero
    csrw    CSR_DASICS_MAIN_CALL_ENTRY, zero
    csrw    CSR_DASICS_ACTIVE_ZONE_RETURN_PC, zero
    li      t0, RETURN_SENTINEL
    csrw    CSR_DASICS_RETURN_PC, t0
    li      t0, FREASON_SENTINEL
    csrw    CSR_DASICS_FREASON, t0
    slli    t0, s3, 2
    csrw    medeleg, t0
    csrr    t1, medeleg
    li      t6, FAIL_DELEGATION
    bne     t0, t1, fail
    li      ra, RA_SENTINEL
    li      a0, GPR_SENTINEL
    ld      a1, PROBE_RS1(s9)
    li      a4, CAPTURE_SENTINEL
    ld      t0, PROBE_RESULT(s9)
    li      t1, RESULT_SUM
    bne     t0, t1, .Larguments_ready
    li      a0, 1
    li      a2, 3
    li      a3, 4
    li      a4, 5
    li      a5, 6
.Larguments_ready:
    ld      t0, CASE_MAIN_CFG(s0)
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      s5, STAGE_PROBE
    csrw    mepc, s10
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0
    slli    t0, s2, 11
    csrs    mstatus, t0
    mret

    .balign 8
    CALL_J j_positive, j_positive_target - j_positive_probe
    .balign 8
    CALL_J j_negative, j_negative_target - j_negative_probe
    .balign 8
    CALL_J j_max, 0x3FFFFE
    CALL_JR jr_ra, 1, 11, 0
    CALL_JR jr_a0, 10, 11, 8
    CALL_JR jr_zero, 0, 11, 0
    CALL_JR jr_alias, 11, 11, 0
    CALL_JR jr_min, 1, 11, -2048
    CALL_JR jr_max, 1, 11, 2047
    .balign 8
    CALL_J j_trusted, trusted_target - j_trusted_probe
    CALL_JR jr_trusted, 1, 11, 0
    CALL_JR jr_zero_source, 1, 0, 0
    .balign 8
unknown_probe:
    .word 0x0000700B
unknown_link:
    li      s8, 1
unknown_break:
    ebreak

    .balign 8
jal_probe:
    jal     ra, trusted_target
jal_link:
    li      s8, 1
jal_break:
    ebreak
    .balign 8
jalr_probe:
    jalr    ra, a1, 0
jalr_link:
    li      s8, 1
jalr_break:
    ebreak
    .balign 8
m5_sum_probe:
    /* Keep custom-3 m5 operations distinct from custom-0 DASICS calls. */
    .word 0x7B | (0x23 << 25)
m5_sum_link:
    li      s8, 1
m5_sum_break:
    ebreak

    .balign 8
    TARGET trusted_target, 9, ra, 1

    .macro CHECK_REJECTED_STATE failure
    li      t6, FAIL_STAGE
    li      t0, 1
    bne     s4, t0, \failure
    bne     s5, t0, \failure
    bnez    s6, \failure
    li      t6, FAIL_TARGET
    bnez    s7, \failure
    li      t6, FAIL_COMPLETION
    bnez    s8, \failure
    li      t6, FAIL_RETURN_PC
    csrr    t0, CSR_DASICS_RETURN_PC
    bne     t0, s11, \failure
    li      t6, FAIL_FREASON
    csrr    t0, CSR_DASICS_FREASON
    li      t1, FREASON_SENTINEL
    bne     t0, t1, \failure
    .endm

    .balign 8
supervisor_trusted_begin:
supervisor_trap_handler:
    li      t6, FAIL_ROUTE
    li      t0, 1
    bne     s3, t0, supervisor_failure_break
    li      t6, FAIL_SOURCE
    csrr    t0, sstatus
    srli    t0, t0, 8
    andi    t0, t0, 1
    bne     t0, s2, supervisor_failure_break
    li      t6, FAIL_CAUSE
    csrr    t0, scause
    li      t1, 2
    bne     t0, t1, supervisor_failure_break
    li      t6, FAIL_EPC
    csrr    t0, sepc
    bne     t0, s10, supervisor_failure_break
    li      t6, FAIL_TVAL
    csrr    t0, stval
    bne     t0, a7, supervisor_failure_break
    CHECK_REJECTED_STATE supervisor_failure_break
    li      s6, 1
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    sepc, t0
    sret
supervisor_failure_break:
    ebreak
    j       supervisor_failure_break
    .balign 8
supervisor_trusted_end:

resume_entry:
    li      s8, 2
resume_break:
    ebreak
    j       resume_break

    .balign 8
machine_trap_handler:
    csrr    t0, mepc
    la      t1, supervisor_failure_break
    beq     t0, t1, fail
    li      t6, FAIL_STAGE
    beqz    s5, fail
    li      t6, FAIL_SOURCE
    csrr    t0, mstatus
    srli    t0, t0, 11
    andi    t0, t0, 3
    bne     t0, s2, fail
    csrr    t0, mcause
    li      t1, 3
    beq     t0, t1, .Lcompletion_trap
    li      t6, FAIL_CAUSE
    li      t1, 2
    bne     t0, t1, fail
    li      t6, FAIL_ROUTE
    bnez    s3, fail
    li      t6, FAIL_EPC
    csrr    t0, mepc
    bne     t0, s10, fail
    li      t6, FAIL_TVAL
    csrr    t0, mtval
    bne     t0, a7, fail
    CHECK_REJECTED_STATE fail
    li      s6, 1
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    mepc, t0
    mret

.Lcompletion_trap:
    bnez    s4, .Lrejected_completion
    li      t6, FAIL_STAGE
    li      t0, STAGE_PROBE
    bne     s5, t0, fail
    bnez    s6, fail
    li      t6, FAIL_COMPLETION
    li      t0, 1
    bne     s8, t0, fail
    ld      t1, PROBE_BREAK(s9)
    li      t6, FAIL_TARGET
    ld      t0, PROBE_MARKER(s9)
    bne     s7, t0, fail
    j       .Lcompletion_pc
.Lrejected_completion:
    li      t6, FAIL_STAGE
    li      t0, STAGE_RESUME
    bne     s5, t0, fail
    li      t0, 1
    bne     s6, t0, fail
    li      t6, FAIL_COMPLETION
    li      t0, 2
    bne     s8, t0, fail
    li      t6, FAIL_TARGET
    bnez    s7, fail
    la      t1, resume_break
.Lcompletion_pc:
    li      t6, FAIL_EPC
    csrr    t0, mepc
    bne     t0, t1, fail
    li      t6, FAIL_TVAL
    csrr    t0, mtval
    bne     t0, t1, fail
    li      t6, FAIL_RETURN_PC
    csrr    t0, CSR_DASICS_RETURN_PC
    bne     t0, s11, fail
    li      t6, FAIL_FREASON
    csrr    t0, CSR_DASICS_FREASON
    li      t1, FREASON_SENTINEL
    bne     t0, t1, fail

    li      t2, RESULT_NONE
    bnez    s4, .Lresult_kind_ready
    ld      t2, PROBE_RESULT(s9)
.Lresult_kind_ready:
    li      t0, RA_SENTINEL
    li      t1, RESULT_RA
    bne     t2, t1, .Lexpected_ra_ready
    mv      t0, a6
.Lexpected_ra_ready:
    li      t6, FAIL_RA
    bne     ra, t0, fail
    li      t0, GPR_SENTINEL
    li      t1, RESULT_A0
    bne     t2, t1, .Lcheck_sum_result
    mv      t0, a6
    j       .Lexpected_a0_ready
.Lcheck_sum_result:
    li      t1, RESULT_SUM
    bne     t2, t1, .Lexpected_a0_ready
    li      t0, 21
.Lexpected_a0_ready:
    li      t6, FAIL_A0
    bne     a0, t0, fail
    /* M5Op can overwrite a1; it is not a preserved source operand. */
    li      t1, RESULT_SUM
    beq     t2, t1, .Lcheck_capture
    ld      t0, PROBE_RS1(s9)
    li      t1, RESULT_A1
    bne     t2, t1, .Lexpected_rs1_ready
    mv      t0, a6
.Lexpected_rs1_ready:
    li      t6, FAIL_RS1
    bne     a1, t0, fail
.Lcheck_capture:
    li      t0, CAPTURE_SENTINEL
    bnez    s4, .Lexpected_capture_ready
    ld      t1, PROBE_CAPTURE(s9)
    beqz    t1, .Lcheck_sum_argument
    mv      t0, s11
    j       .Lexpected_capture_ready
.Lcheck_sum_argument:
    li      t1, RESULT_SUM
    bne     t2, t1, .Lexpected_capture_ready
    li      t0, 5
.Lexpected_capture_ready:
    li      t6, FAIL_CAPTURE
    bne     a4, t0, fail
    addi    s0, s0, CASE_SIZE
    la      t0, cases_end
    beq     s0, t0, pass
    addi    s1, s1, 1
    j       start_case

pass:
    li      a2, 0
    j       exit_test
fail:
    li      t0, 100
    la      t3, failure_case
    divu    t1, s1, t0
    remu    t2, s1, t0
    addi    t1, t1, '0'
    sb      t1, 0(t3)
    li      t0, 10
    divu    t1, t2, t0
    remu    t2, t2, t0
    addi    t1, t1, '0'
    addi    t2, t2, '0'
    sb      t1, 1(t3)
    sb      t2, 2(t3)
    la      t3, failure_reason
    divu    t1, t6, t0
    remu    t2, t6, t0
    addi    t1, t1, '0'
    addi    t2, t2, '0'
    sb      t1, 0(t3)
    sb      t2, 1(t3)
    fence   rw, rw
    la      a1, failure_message
    li      a0, 0x04
    .balign 16
semihost_write:
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
    mv      a2, s1
    bnez    a2, exit_test
    li      a2, 255
exit_test:
    la      a1, exit_args
    sd      a2, 8(a1)
    fence   rw, rw
    li      a0, 0x20
    .balign 16
semihost_exit:
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
halt:
    j       halt
    .balign 8
trusted_end:

    TARGET j_positive_target, 1
    .balign 8
    TARGET jr_ra_target, 5
    .balign 8
    TARGET jr_a0_target, 6, a0
    .balign 8
    TARGET jr_zero_target, 7, a6
    .balign 8
    TARGET jr_alias_target, 8, a1

    /* The largest even displacement deliberately lands at PC mod 4 = 2. */
    .org (j_max_probe - _start + 0x3FFFFE)
    TARGET j_max_target, 4

    .section .rodata
    .balign 8
    .macro DESCRIPTOR name, target, rs1, result, marker, capture=0, custom=1
\name\()_descriptor:
    .dword  \name\()_probe, \name\()_break, \target, \rs1
    .dword  \result, \marker, \capture, \custom
    .endm
probes:
    DESCRIPTOR j_positive, j_positive_target, SOURCE_SENTINEL, RESULT_RA, 1
    DESCRIPTOR j_negative, j_negative_target, SOURCE_SENTINEL, RESULT_RA, 2
    DESCRIPTOR j_min, j_min_target, SOURCE_SENTINEL, RESULT_RA, 3
    DESCRIPTOR j_max, j_max_target, SOURCE_SENTINEL, RESULT_RA, 4
    DESCRIPTOR jr_ra, jr_ra_target, (jr_ra_target + 1), RESULT_RA, 5
    DESCRIPTOR jr_a0, jr_a0_target, (jr_a0_target - 8), RESULT_A0, 6
    DESCRIPTOR jr_zero, jr_zero_target, jr_zero_target, RESULT_NONE, 7
    DESCRIPTOR jr_alias, jr_alias_target, jr_alias_target, RESULT_A1, 8
    DESCRIPTOR jr_min, jr_ra_target, (jr_ra_target + 2049), RESULT_RA, 5
    DESCRIPTOR jr_max, jr_ra_target, (jr_ra_target - 2047), RESULT_RA, 5
    DESCRIPTOR j_trusted, trusted_target, SOURCE_SENTINEL, RESULT_RA, 9, 1
    DESCRIPTOR jr_trusted, trusted_target, trusted_target, RESULT_RA, 9, 1
    DESCRIPTOR unknown, 0, SOURCE_SENTINEL, RESULT_NONE, 0
    DESCRIPTOR jr_zero_source, 0, SOURCE_SENTINEL, RESULT_RA, 0
    DESCRIPTOR jal, trusted_target, SOURCE_SENTINEL, RESULT_RA, 9, 1, 0
    DESCRIPTOR jalr, trusted_target, trusted_target, RESULT_RA, 9, 1, 0
    DESCRIPTOR m5_sum, 0, 2, RESULT_SUM, 0, 0, 0
probes_end:

    .macro CASE name, mode, delegated, cfg, trusted, illegal
    .dword  \name\()_descriptor, \mode, \delegated, \cfg, \trusted, \illegal
    .endm
    .macro SUCCESS_PAIR name
    CASE \name, PRV_U, 0, MAIN_CFG, 1, 0
    CASE \name, PRV_S, 0, MAIN_CFG, 1, 0
    .endm
cases:
    SUCCESS_PAIR j_positive
    SUCCESS_PAIR j_negative
    SUCCESS_PAIR j_min
    SUCCESS_PAIR j_max
    SUCCESS_PAIR jr_ra
    SUCCESS_PAIR jr_a0
    SUCCESS_PAIR jr_zero
    SUCCESS_PAIR jr_alias
    SUCCESS_PAIR jr_min
    SUCCESS_PAIR jr_max
cases_trusted_targets:
    SUCCESS_PAIR j_trusted
    SUCCESS_PAIR jr_trusted

    .macro PERMISSION_CASES name, mode, own, other, close
    CASE \name, \mode, 0, (MAIN_CFG & ~\own), 1, 1
    CASE \name, \mode, 1, (MAIN_CFG & ~\own), 1, 1
    CASE \name, \mode, 0, MAIN_CFG, 0, 1
    CASE \name, \mode, 1, MAIN_CFG, 0, 1
    CASE \name, \mode, 0, (MAIN_CFG | \close), 0, 1
    CASE \name, \mode, 1, (MAIN_CFG | \close), 0, 1
    CASE \name, \mode, 0, (MAIN_CFG & ~\other), 1, 0
    .endm
cases_permissions:
    PERMISSION_CASES j_positive, PRV_U, DASICS_UENA, DASICS_SENA, DASICS_CUFT
    PERMISSION_CASES j_positive, PRV_S, DASICS_SENA, DASICS_UENA, DASICS_CSFT
    PERMISSION_CASES jr_ra, PRV_U, DASICS_UENA, DASICS_SENA, DASICS_CUFT
    PERMISSION_CASES jr_ra, PRV_S, DASICS_SENA, DASICS_UENA, DASICS_CSFT
cases_machine:
    /* Negative immediates also check that TVAL preserves raw bit 31. */
    CASE j_min, PRV_M, 0, MAIN_CFG, 1, 1
    CASE jr_min, PRV_M, 0, MAIN_CFG, 1, 1
cases_unknown:
    CASE unknown, PRV_U, 0, MAIN_CFG, 1, 1
    CASE unknown, PRV_U, 1, MAIN_CFG, 1, 1
    CASE unknown, PRV_S, 0, MAIN_CFG, 1, 1
    CASE unknown, PRV_S, 1, MAIN_CFG, 1, 1
cases_zero_source:
    CASE jr_zero_source, PRV_U, 0, (MAIN_CFG & ~DASICS_UENA), 1, 1
    CASE jr_zero_source, PRV_U, 1, MAIN_CFG, 0, 1
    CASE jr_zero_source, PRV_S, 0, (MAIN_CFG & ~DASICS_SENA), 1, 1
    CASE jr_zero_source, PRV_S, 1, MAIN_CFG, 0, 1
cases_standard_jumps:
    SUCCESS_PAIR jal
    SUCCESS_PAIR jalr
cases_m5:
    CASE m5_sum, PRV_M, 0, MAIN_CFG, 1, 0
cases_end:
    .if ((cases_end - cases) / CASE_SIZE) >= 124
    .error "Case exit status must not collide with timeout 124"
    .endif

    .section .data
    .balign 8
exit_args:
    .dword  0x20026
    .dword  0
failure_message:
    .ascii  "DASICS call: case="
failure_case:
    .ascii  "000 reason="
failure_reason:
    .asciz  "00\n"
