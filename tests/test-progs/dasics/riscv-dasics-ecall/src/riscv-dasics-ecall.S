/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CSR_DASICS_S_MAIN_CFG, 0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3
    .equ CSR_DASICS_FREASON, 0x8B3
    .equ DASICS_SENA, (1 << 0)
    .equ DASICS_UENA, (1 << 1)
    .equ DASICS_CUET, (1 << 2)
    .equ DASICS_CSET, (1 << 6)
    /* Close U/S data and control-flow checks; leave ECALL checks open. */
    .equ MAIN_CFG, DASICS_SENA | DASICS_UENA | (7 << 3) | (7 << 7)
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ PRV_M, 3
    .equ FREASON_SENTINEL, 5
    .equ FREASON_ECALL, 1
    .equ GPR_SENTINEL, 0x0123456789ABCDEF
    .equ ARG_SENTINEL, 0xFEDCBA9876543210
    .equ RA_SENTINEL, 0xA5A5A5A5A5A5A5A5
    .equ ENTRY_STATUS_CLEAR, (1 << 1) | (1 << 3) | (1 << 5) | (1 << 7) \
                            | (3 << 11) | (1 << 17) | (1 << 22)
    .equ STAGE_SETUP, 0
    .equ STAGE_PROBE, 1
    .equ STAGE_RESUME, 2

    .equ CASE_SOURCE, 0
    .equ CASE_DELEGATED, 8
    .equ CASE_MAIN_CFG, 16
    .equ CASE_PC, 24
    .equ CASE_LOWER, 32
    .equ CASE_UPPER, 40
    .equ CASE_CAUSE, 48
    .equ CASE_MEDELEG, 56
    .equ CASE_SIZE, 64

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

    /*
     * s0: case row; s1: case ID; s2: source mode; s3: expected S handler;
     * s4: expected ECALL cause; s5: stage; s6: accepted ECALL trap count;
     * s7/s8: fallthrough/resume markers; s9: expected FReason; s10: ECALL PC.
     * a0, a1 and ra are observable sentinels. Handlers only use t0/t1/t6;
     * t6 carries the diagnostic reason through the S failure breakpoint.
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
    li      t0, 0x24000000
    csrw    pmpaddr0, t0
    li      t0, 0x0F
    csrw    pmpcfg0, t0
    la      s0, cases
    li      s1, 1
start_case:
    li      s5, STAGE_SETUP
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    ld      s2, CASE_SOURCE(s0)
    ld      s3, CASE_DELEGATED(s0)
    ld      s4, CASE_CAUSE(s0)
    ld      s10, CASE_PC(s0)
    li      s6, 0
    li      s7, 0
    li      s8, 0
    li      s9, FREASON_SENTINEL
    li      t0, 24
    bltu    s4, t0, .Lreason_ready
    li      s9, FREASON_ECALL
.Lreason_ready:
    /* Every interval includes the complete S handler. */
    ld      t0, CASE_LOWER(s0)
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    ld      t0, CASE_UPPER(s0)
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t0
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    ld      t0, CASE_MEDELEG(s0)
    csrw    medeleg, t0
    csrr    t1, medeleg
    li      t6, FAIL_DELEGATION
    bne     t0, t1, fail
    li      t0, FREASON_SENTINEL
    csrw    CSR_DASICS_FREASON, t0
    li      a0, GPR_SENTINEL
    li      a1, ARG_SENTINEL
    li      ra, RA_SENTINEL
    ld      t0, CASE_MAIN_CFG(s0)
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      s5, STAGE_PROBE
    csrw    mepc, s10
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0
    slli    t0, s2, 11
    csrs    mstatus, t0
    mret

    .macro CHECK_OBSERVABLE_STATE failure
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
    li      t6, FAIL_FALLTHROUGH
    bnez    s7, \failure
    .endm

    .macro CHECK_FIRST_TRAP failure
    li      t6, FAIL_STAGE
    li      t0, STAGE_PROBE
    bne     s5, t0, \failure
    bnez    s6, \failure
    li      t6, FAIL_RESUME
    bnez    s8, \failure
    CHECK_OBSERVABLE_STATE \failure
    .endm

    .balign 8
probes_begin:
    nop
    nop
probe_before:
    ecall
    j       unexpected_fallthrough
probe_before_end:
half_block:
    nop
probe_half:
    ecall
    j       unexpected_fallthrough

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
    bne     t0, s4, supervisor_failure_break
    li      t6, FAIL_EPC
    csrr    t0, sepc
    bne     t0, s10, supervisor_failure_break
    li      t6, FAIL_TVAL
    csrr    t0, stval
    bnez    t0, supervisor_failure_break
    CHECK_FIRST_TRAP supervisor_failure_break
    li      s6, 1
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    sepc, t0
    sret
supervisor_failure_break:
    /* Breakpoint is never delegated; preserve t6 for M diagnostics. */
    ebreak
    j       supervisor_failure_break
    .balign 8
supervisor_trusted_end:
probe_after:
    ecall
    j       unexpected_fallthrough

unexpected_fallthrough:
    li      s7, 1
    ebreak
    j       unexpected_fallthrough
resume_entry:
    li      s8, 1
resume_break:
    /* Ordinary ECALL may be delegated; breakpoint always returns to M. */
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
    li      t0, STAGE_RESUME
    beq     s5, t0, .Lcompletion_trap
    li      t6, FAIL_ROUTE
    bnez    s3, fail
    li      t6, FAIL_CAUSE
    csrr    t0, mcause
    bne     t0, s4, fail
    li      t6, FAIL_EPC
    csrr    t0, mepc
    bne     t0, s10, fail
    li      t6, FAIL_TVAL
    csrr    t0, mtval
    bnez    t0, fail
    CHECK_FIRST_TRAP fail
    li      s6, 1
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    mepc, t0
    mret

.Lcompletion_trap:
    li      t6, FAIL_STAGE
    li      t0, 1
    bne     s6, t0, fail
    li      t6, FAIL_CAUSE
    csrr    t0, mcause
    li      t1, 3
    bne     t0, t1, fail
    li      t6, FAIL_EPC
    la      t1, resume_break
    csrr    t0, mepc
    bne     t0, t1, fail
    li      t6, FAIL_TVAL
    csrr    t0, mtval
    bne     t0, t1, fail
    li      t6, FAIL_RESUME
    li      t0, 1
    bne     s8, t0, fail
    CHECK_OBSERVABLE_STATE fail
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
    .macro CASE mode, cfg, pc, lower, upper, protected, delegated
    .dword  \mode, \delegated, \cfg, \pc, \lower, \upper
    .if \protected
    .dword  (24 + \mode)
    .if \delegated
    .dword  (1 << (24 + \mode))
    .else
    .dword  (1 << (8 + \mode))
    .endif
    .else
    .dword  (8 + \mode)
    .if \delegated
    .dword  (1 << (8 + \mode))
    .else
    .dword  (1 << (24 + \mode))
    .endif
    .endif
    .endm

    /* The non-selected cause is delegated in each M-route case. */
    .macro ROUTES mode, cfg, pc, lower, upper, protected
    CASE \mode, \cfg, \pc, \lower, \upper, \protected, 0
    CASE \mode, \cfg, \pc, \lower, \upper, \protected, 1
    .endm
    .macro UNTRUSTED mode, cfg, protected
    ROUTES \mode, \cfg, probe_before, supervisor_trusted_begin, \
           supervisor_trusted_end, \protected
    .endm

cases:
    UNTRUSTED PRV_U, MAIN_CFG, 1
    UNTRUSTED PRV_U, (MAIN_CFG | DASICS_CUET), 0
    UNTRUSTED PRV_S, MAIN_CFG, 1
    UNTRUSTED PRV_S, (MAIN_CFG | DASICS_CSET), 0
cases_enable:
    UNTRUSTED PRV_U, (MAIN_CFG & ~DASICS_UENA), 0
    UNTRUSTED PRV_U, (MAIN_CFG & ~DASICS_SENA), 1
    UNTRUSTED PRV_S, (MAIN_CFG & ~DASICS_SENA), 0
    UNTRUSTED PRV_S, (MAIN_CFG & ~DASICS_UENA), 1
cases_other_close:
    UNTRUSTED PRV_U, (MAIN_CFG | DASICS_CSET), 1
    UNTRUSTED PRV_S, (MAIN_CFG | DASICS_CUET), 1
cases_pc_bounds:
    .irp mode, PRV_U, PRV_S
    /* One block below lower, at lower, +4 in that block, inside, at upper. */
    ROUTES \mode, MAIN_CFG, probe_before, probe_before_end, \
           supervisor_trusted_end, 1
    ROUTES \mode, MAIN_CFG, probe_before, probe_before, \
           supervisor_trusted_end, 0
    ROUTES \mode, MAIN_CFG, probe_half, half_block, \
           supervisor_trusted_end, 0
    ROUTES \mode, MAIN_CFG, probe_before, probes_begin, \
           supervisor_trusted_end, 0
    ROUTES \mode, MAIN_CFG, probe_after, supervisor_trusted_begin, \
           probe_after, 1
    .endr
cases_machine:
    /* M-mode ECALL cannot delegate down, even with all U/S bits set. */
    .dword  PRV_M, 0, MAIN_CFG, probe_before
    .dword  supervisor_trusted_begin, supervisor_trusted_end, 11
    .dword  (1 << 8) | (1 << 9) | (1 << 24) | (1 << 25)
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
    .ascii  "DASICS ecall: case="
failure_case:
    .ascii  "000 reason="
failure_reason:
    .asciz  "00\n"
