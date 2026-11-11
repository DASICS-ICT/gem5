/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CSR_USTATUS, 0x000
    .equ CSR_UTVEC, 0x005
    .equ CSR_USCRATCH, 0x040
    .equ CSR_UEPC, 0x041
    .equ CSR_UCAUSE, 0x042
    .equ CSR_UTVAL, 0x043
    .equ CSR_SEDELEG, 0x102
    .equ CSR_DASICS_S_MAIN_CFG, 0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3
    .equ CSR_DASICS_FREASON, 0x8B3
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ PRV_M, 3
    .equ USTATUS_MASK, 0x11
    /* Enable U/S, close scalar/jump checks, keep U ECALL checks open. */
    .equ MAIN_CFG, 3 | (7 << 3) | (15 << 6)
    .equ FREASON_SENTINEL, 5
    .equ FREASON_ECALL, 1
    .equ GPR_SENTINEL, 0x0123456789ABCDEF
    .equ ARG_SENTINEL, 0xFEDCBA9876543210
    .equ RA_SENTINEL, 0xA5A5A5A5A5A5A5A5
    .equ U_SCRATCH_SENTINEL, 0x1111222233334444
    .equ S_SCRATCH_SENTINEL, 0x2222333344445555
    .equ M_SCRATCH_SENTINEL, 0x3333444455556666
    .equ U_EPC_SENTINEL, 0x80000100
    .equ S_EPC_SENTINEL, 0x80000200
    .equ U_CAUSE_SENTINEL, 0x55
    .equ S_CAUSE_SENTINEL, 0x66
    .equ U_TVAL_SENTINEL, 0x1122334455667788
    .equ S_TVAL_SENTINEL, 0x8877665544332211
    .equ ENTRY_STATUS_CLEAR, (1 << 1) | (1 << 3) | (1 << 5) | (1 << 7) \
                            | (1 << 8) | (3 << 11) | (1 << 17) \
                            | (1 << 22)
    .equ STAGE_SETUP, 0
    .equ STAGE_PROBE, 1
    .equ STAGE_RESUME, 2

    .equ CASE_PC, 0
    .equ CASE_CAUSE, 8
    .equ CASE_MEDELEG, 16
    .equ CASE_SEDELEG, 24
    .equ CASE_ROUTE, 32
    .equ CASE_USTATUS, 40
    .equ CASE_SIZE, 48

    .equ FAIL_DELEGATION, 1
    .equ FAIL_SOURCE, 2
    .equ FAIL_ROUTE, 3
    .equ FAIL_STAGE, 4
    .equ FAIL_CAUSE, 5
    .equ FAIL_EPC, 6
    .equ FAIL_TVAL, 7
    .equ FAIL_FREASON, 8
    .equ FAIL_GPR, 9
    .equ FAIL_FALLTHROUGH, 10
    .equ FAIL_RESUME, 11
    .equ FAIL_USTATUS, 12
    .equ FAIL_U_TRAP_STATE, 13
    .equ FAIL_S_TRAP_STATE, 14
    .equ FAIL_SCRATCH_VECTORS, 15
    .equ FAIL_MPRV, 16

    /*
     * s0: case row; s1: case ID; s2: expected first-trap mode;
     * s3: initial USTATUS; s4: expected cause; s5: stage;
     * s6: first-trap count; s7/s8: fallthrough/resume markers;
     * s9: expected FReason; s10: source PC; s11: expected TVAL.
     * a0/a1/ra are observed sentinels. Handlers use t0/t1/t2/t6;
     * t6 carries a diagnostic through the U/S failure breakpoint.
     * No stack, call/ret, virtual addressing or guest modes are used.
     */
    .option norelax
    .option nopic
    .option norvc
    .section .text.init
    .globl _start
_start:
    li      s1, 0
    li      s5, STAGE_SETUP
    la      t0, machine_trap_handler
    csrw    mtvec, t0
    csrw    mie, zero
    csrw    mideleg, zero
    csrw    medeleg, zero
    csrw    satp, zero
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0
    /* TOR permits all probe, handler and data addresses in this image. */
    li      t0, 0x24000000
    csrw    pmpaddr0, t0
    li      t0, 0x0F
    csrw    pmpcfg0, t0
    la      s0, cases
    li      s1, 1
start_case:
    li      s5, STAGE_SETUP
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    /* Clear the previous row before changing its machine delegation. */
    csrw    CSR_SEDELEG, zero
    csrw    medeleg, zero
    ld      s10, CASE_PC(s0)
    ld      s4, CASE_CAUSE(s0)
    ld      s2, CASE_ROUTE(s0)
    ld      s3, CASE_USTATUS(s0)
    li      s6, 0
    li      s7, 0
    li      s8, 0
    li      s11, 0
    li      s9, FREASON_ECALL
    li      t0, 2
    bne     s4, t0, .Lprobe_metadata_ready
    lwu     s11, 0(s10)
    li      s9, FREASON_SENTINEL
.Lprobe_metadata_ready:
    la      t0, user_trusted_begin
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    la      t0, user_trusted_end
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t0
    la      t0, supervisor_trusted_begin
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    la      t0, supervisor_trusted_end
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    la      t0, user_trap_handler
    csrw    CSR_UTVEC, t0
    la      t0, supervisor_trap_handler
    csrw    stvec, t0
    li      t0, U_SCRATCH_SENTINEL
    csrw    CSR_USCRATCH, t0
    li      t0, S_SCRATCH_SENTINEL
    csrw    sscratch, t0
    li      t0, M_SCRATCH_SENTINEL
    csrw    mscratch, t0
    li      t0, U_EPC_SENTINEL
    csrw    CSR_UEPC, t0
    li      t0, S_EPC_SENTINEL
    csrw    sepc, t0
    li      t0, U_CAUSE_SENTINEL
    csrw    CSR_UCAUSE, t0
    li      t0, S_CAUSE_SENTINEL
    csrw    scause, t0
    li      t0, U_TVAL_SENTINEL
    csrw    CSR_UTVAL, t0
    li      t0, S_TVAL_SENTINEL
    csrw    stval, t0

    li      t2, 1
    sll     t2, t2, s4
    ld      t0, CASE_SEDELEG(s0)
    beqz    t0, .Lset_final_medeleg
    /* Establish SD=1 legally, including the row that later clears MD. */
    csrw    medeleg, t2
    csrw    CSR_SEDELEG, t2
.Lset_final_medeleg:
    ld      t0, CASE_MEDELEG(s0)
    li      t1, 0
    beqz    t0, .Lwrite_final_medeleg
    mv      t1, t2
.Lwrite_final_medeleg:
    csrw    medeleg, t1
    li      t6, FAIL_DELEGATION
    csrr    t0, medeleg
    bne     t0, t1, fail
    ld      t0, CASE_SEDELEG(s0)
    li      t1, 0
    beqz    t0, .Lcheck_sedeleg
    mv      t1, t2
.Lcheck_sedeleg:
    csrr    t0, CSR_SEDELEG
    bne     t0, t1, fail

    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0
    csrw    CSR_USTATUS, s3
    li      t0, FREASON_SENTINEL
    csrw    CSR_DASICS_FREASON, t0
    li      a0, GPR_SENTINEL
    li      a1, ARG_SENTINEL
    li      ra, RA_SENTINEL
    li      t0, MAIN_CFG
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      s5, STAGE_PROBE
    csrw    mepc, s10
    mret

    .macro ENTER_FIRST_TRAP failure
    li      t6, FAIL_STAGE
    li      t0, STAGE_PROBE
    bne     s5, t0, \failure
    bnez    s6, \failure
    li      t6, FAIL_FALLTHROUGH
    bnez    s7, \failure
    li      t6, FAIL_RESUME
    bnez    s8, \failure
    /* Count before CSR inspection so a nested fault can report failure. */
    li      s6, 1
    .endm

    .macro CHECK_CONTEXT failure
    li      t6, FAIL_FREASON
    csrr    t0, CSR_DASICS_FREASON
    bne     t0, s9, \failure
    li      t6, FAIL_GPR
    li      t0, GPR_SENTINEL
    bne     a0, t0, \failure
    li      t0, ARG_SENTINEL
    bne     a1, t0, \failure
    li      t0, RA_SENTINEL
    bne     ra, t0, \failure
    .endm

    .balign 8
user_trusted_begin:
illegal_probe:
    csrr    a0, mstatus
    li      s7, 1
    ebreak

    .balign 8
user_trap_handler:
    li      t6, FAIL_ROUTE
    li      t0, PRV_U
    bne     s2, t0, user_failure_break
    ENTER_FIRST_TRAP user_failure_break
    li      t6, FAIL_CAUSE
    csrr    t0, CSR_UCAUSE
    bne     t0, s4, user_failure_break
    li      t6, FAIL_EPC
    csrr    t0, CSR_UEPC
    bne     t0, s10, user_failure_break
    li      t6, FAIL_TVAL
    csrr    t0, CSR_UTVAL
    bne     t0, s11, user_failure_break
    li      t6, FAIL_USTATUS
    csrr    t0, CSR_USTATUS
    andi    t1, s3, 1
    slli    t1, t1, 4
    bne     t0, t1, user_failure_break
    CHECK_CONTEXT user_failure_break
    la      t0, resume_entry
    csrw    CSR_UEPC, t0
    li      s5, STAGE_RESUME
user_uret:
    .word   0x00200073
    li      t6, FAIL_RESUME
    j       user_failure_break

    .balign 8
resume_entry:
    li      s8, 1
    li      t6, FAIL_STAGE
    li      t0, STAGE_RESUME
    bne     s5, t0, user_failure_break
    li      t0, 1
    bne     s6, t0, user_failure_break
    li      t6, FAIL_FALLTHROUGH
    bnez    s7, user_failure_break
    li      t6, FAIL_USTATUS
    mv      t1, s3
    bnez    s2, .Lresume_status_ready
    andi    t1, s3, 1
    ori     t1, t1, 0x10
.Lresume_status_ready:
    csrr    t0, CSR_USTATUS
    bne     t0, t1, user_failure_break
    CHECK_CONTEXT user_failure_break
resume_break:
    /* Cause 3 is never delegated; this observes the restored U context. */
    ebreak
    li      t6, FAIL_RESUME
user_failure_break:
    ebreak
    j       user_failure_break
    .balign 8
user_trusted_end:

ecall_probe:
    ecall
    li      s7, 1
    ebreak

    .balign 8
supervisor_trusted_begin:
supervisor_trap_handler:
    li      t6, FAIL_ROUTE
    li      t0, PRV_S
    bne     s2, t0, supervisor_failure_break
    ENTER_FIRST_TRAP supervisor_failure_break
    li      t6, FAIL_SOURCE
    csrr    t0, sstatus
    andi    t0, t0, (1 << 8)
    bnez    t0, supervisor_failure_break
    li      t6, FAIL_CAUSE
    csrr    t0, scause
    bne     t0, s4, supervisor_failure_break
    li      t6, FAIL_EPC
    csrr    t0, sepc
    bne     t0, s10, supervisor_failure_break
    li      t6, FAIL_TVAL
    csrr    t0, stval
    bne     t0, s11, supervisor_failure_break
    li      t6, FAIL_USTATUS
    csrr    t0, CSR_USTATUS
    bne     t0, s3, supervisor_failure_break
    CHECK_CONTEXT supervisor_failure_break
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    sepc, t0
    sret
    li      t6, FAIL_RESUME
supervisor_failure_break:
    ebreak
    j       supervisor_failure_break
    .balign 8
supervisor_trusted_end:

machine_trap_handler:
    /* Preserve the lower handler's diagnostic before installing M checks. */
    csrr    t0, mepc
    la      t1, user_failure_break
    beq     t0, t1, fail
    la      t1, supervisor_failure_break
    beq     t0, t1, fail
    li      t6, FAIL_STAGE
    beqz    s5, fail
    li      t6, FAIL_SOURCE
    csrr    t0, mstatus
    srli    t0, t0, 11
    andi    t0, t0, 3
    bnez    t0, fail
    csrr    t0, mcause
    li      t1, 3
    beq     t0, t1, .Lcompletion_trap
    li      t6, FAIL_ROUTE
    li      t0, PRV_M
    bne     s2, t0, fail
    ENTER_FIRST_TRAP fail
    li      t6, FAIL_CAUSE
    csrr    t0, mcause
    bne     t0, s4, fail
    li      t6, FAIL_EPC
    csrr    t0, mepc
    bne     t0, s10, fail
    li      t6, FAIL_TVAL
    csrr    t0, mtval
    bne     t0, s11, fail
    li      t6, FAIL_USTATUS
    csrr    t0, CSR_USTATUS
    bne     t0, s3, fail
    CHECK_CONTEXT fail
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    mepc, t0
    mret

.Lcompletion_trap:
    li      t6, FAIL_STAGE
    li      t0, STAGE_RESUME
    bne     s5, t0, fail
    li      t0, 1
    bne     s6, t0, fail
    li      t6, FAIL_RESUME
    bne     s8, t0, fail
    li      t6, FAIL_FALLTHROUGH
    bnez    s7, fail
    li      t6, FAIL_EPC
    la      t1, resume_break
    csrr    t0, mepc
    bne     t0, t1, fail
    li      t6, FAIL_TVAL
    csrr    t0, mtval
    bne     t0, t1, fail
    CHECK_CONTEXT fail

    li      t6, FAIL_U_TRAP_STATE
    li      t1, U_CAUSE_SENTINEL
    bnez    s2, .Lexpected_ucause
    mv      t1, s4
.Lexpected_ucause:
    csrr    t0, CSR_UCAUSE
    bne     t0, t1, fail
    li      t1, U_TVAL_SENTINEL
    bnez    s2, .Lexpected_utval
    mv      t1, s11
.Lexpected_utval:
    csrr    t0, CSR_UTVAL
    bne     t0, t1, fail
    li      t1, U_EPC_SENTINEL
    bnez    s2, .Lexpected_uepc
    la      t1, resume_entry
.Lexpected_uepc:
    csrr    t0, CSR_UEPC
    bne     t0, t1, fail

    li      t6, FAIL_S_TRAP_STATE
    li      t2, PRV_S
    li      t1, S_CAUSE_SENTINEL
    bne     s2, t2, .Lexpected_scause
    mv      t1, s4
.Lexpected_scause:
    csrr    t0, scause
    bne     t0, t1, fail
    li      t1, S_TVAL_SENTINEL
    bne     s2, t2, .Lexpected_stval
    mv      t1, s11
.Lexpected_stval:
    csrr    t0, stval
    bne     t0, t1, fail
    li      t1, S_EPC_SENTINEL
    bne     s2, t2, .Lexpected_sepc
    la      t1, resume_entry
.Lexpected_sepc:
    csrr    t0, sepc
    bne     t0, t1, fail

    li      t6, FAIL_SCRATCH_VECTORS
    csrr    t0, CSR_USCRATCH
    li      t1, U_SCRATCH_SENTINEL
    bne     t0, t1, fail
    csrr    t0, sscratch
    li      t1, S_SCRATCH_SENTINEL
    bne     t0, t1, fail
    csrr    t0, mscratch
    li      t1, M_SCRATCH_SENTINEL
    bne     t0, t1, fail
    csrr    t0, CSR_UTVEC
    la      t1, user_trap_handler
    bne     t0, t1, fail
    csrr    t0, stvec
    la      t1, supervisor_trap_handler
    bne     t0, t1, fail
    csrr    t0, mtvec
    la      t1, machine_trap_handler
    bne     t0, t1, fail
    /* Completion EBREAK overwrites M trap fields; check only retained MPRV. */
    li      t6, FAIL_MPRV
    csrr    t0, mstatus
    li      t1, (1 << 17)
    and     t0, t0, t1
    bnez    t0, fail
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

    .section .rodata
    .balign 8
    .macro ROUTES probe, cause
    .dword  \probe, \cause, 0, 0, PRV_M, 1
    .dword  \probe, \cause, 1, 0, PRV_S, 1
    .dword  \probe, \cause, 1, 1, PRV_U, 1
    .dword  \probe, \cause, 0, 1, PRV_M, 1
    .endm
cases:
    /* Probe PC, cause, final MD, stored SD, handler mode, initial USTATUS. */
    ROUTES illegal_probe, 2
    ROUTES ecall_probe, 24
cases_uie_off:
    .dword  illegal_probe, 2, 1, 1, PRV_U, 0x10
    .dword  ecall_probe, 24, 1, 1, PRV_U, 0x10
cases_end:
    .if ((cases_end - cases) / CASE_SIZE) != 10
    .error "The user-trap test requires exactly ten cases"
    .endif

    .section .data
    .balign 8
exit_args:
    .dword  0x20026
    .dword  0
failure_message:
    .ascii  "DASICS user-trap: case="
failure_case:
    .ascii  "000 reason="
failure_reason:
    .asciz  "00\n"
