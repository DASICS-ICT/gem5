/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CSR_DASICS_S_MAIN_CFG, 0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3
    .equ CSR_DASICS_LIB_CFG, 0x880
    .equ CSR_DASICS_LIB_BOUND_LO0, 0x890
    .equ CSR_DASICS_LIB_BOUND_HI0, 0x891
    .equ CSR_DASICS_LIB_BOUND_LO1, 0x892
    .equ CSR_DASICS_LIB_BOUND_HI1, 0x893
    .equ CSR_DASICS_LIB_BOUND_LO15, 0x8AE
    .equ CSR_DASICS_LIB_BOUND_HI15, 0x8AF
    .equ CSR_DASICS_FREASON, 0x8B3

    .equ DASICS_SENA, (1 << 0)
    .equ DASICS_UENA, (1 << 1)
    .equ DASICS_CUET, (1 << 2)
    .equ DASICS_CUST, (1 << 3)
    .equ DASICS_CULT, (1 << 4)
    .equ DASICS_CUFT, (1 << 5)
    .equ DASICS_CSET, (1 << 6)
    .equ DASICS_CSST, (1 << 7)
    .equ DASICS_CSLT, (1 << 8)
    .equ DASICS_CSFT, (1 << 9)
    /* Isolate scalar data protection from ECALL and control-flow checks. */
    .equ MAIN_CFG, DASICS_SENA | DASICS_UENA | DASICS_CUET | DASICS_CUFT \
                  | DASICS_CSET | DASICS_CSFT
    .equ LIB_READ, 0xA
    .equ LIB_WRITE, 0x9
    .equ LIB_RW, 0xB
    .equ LIB_U, 0x4
    .equ FREASON_SENTINEL, 5
    .equ FREASON_LOAD, 2
    .equ GPR_SENTINEL, 0x0123456789ABCDEF
    .equ FPR_SENTINEL, 0x8877665544332211
    .equ GPR_SOURCE, 0x0807060504030201
    .equ FPR_SOURCE, 0x1817161514131211
    .equ MEMORY_INITIAL, 0xF1F1F1F1F1F1F1F1
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ PRV_M, 3
    .equ CAUSE_U_ECALL, 8
    .equ CAUSE_U_DASICS, 24
    .equ EXPECT_DASICS, -1

    .equ MSTATUS_FS_MASK, (3 << 13)
    .equ MSTATUS_FS_CLEAN, (2 << 13)
    /* Disable interrupts, MPRV and SRET restrictions before each probe. */
    .equ ENTRY_STATUS_CLEAR, (1 << 1) | (1 << 3) | (1 << 5) | (1 << 7) \
                            | (3 << 11) | (1 << 17) | (1 << 22)
    .equ STAGE_SETUP, 0
    .equ STAGE_PROBE, 1
    .equ STAGE_RESUME, 2

    .equ CASE_PROBE, 0
    .equ CASE_SOURCE, 8
    .equ CASE_DELEGATED, 16
    .equ CASE_MAIN_CFG, 24
    .equ CASE_LIB_CFG, 32
    .equ CASE_LOWER, 40
    .equ CASE_UPPER, 48
    .equ CASE_ADDRESS, 56
    .equ CASE_CAUSE, 64
    .equ CASE_PMP_DENY, 72
    .equ CASE_TRUSTED, 80
    .equ CASE_SIZE, 88
    .equ PROBE_PC, 0
    .equ PROBE_ECALL, 8
    .equ PROBE_WRITE, 16
    .equ PROBE_BYTES, 24
    .equ PROBE_GPR, 32
    .equ PROBE_FPR, 40
    .equ PROBE_STORE_VALUE, 48
    .equ PROBE_FS, 56
    .equ PROBE_SIZE, 64

    .equ FAIL_DELEGATION, 1
    .equ FAIL_SOURCE, 2
    .equ FAIL_ROUTE, 3
    .equ FAIL_STAGE, 4
    .equ FAIL_CAUSE, 5
    .equ FAIL_EPC, 6
    .equ FAIL_TVAL, 7
    .equ FAIL_FREASON, 8
    .equ FAIL_GPR, 9
    .equ FAIL_FPR, 10
    .equ FAIL_MEMORY, 11
    .equ FAIL_FS, 12
    .equ FAIL_COMPLETION, 13
    .equ FAIL_RESUME, 14

    /*
     * s0: case row; s1: one-based ID; s2: source mode; s3: delegate to S;
     * s4: expected cause (zero means completion); s5: execution stage;
     * s6: accepted fault count; s7/s8: completion/resume markers;
     * s9: probe descriptor; s10: expected FReason; s11: probe PC.
     * a0/fa0 are load destinations; a2/fa2 are store sources; a1 is EA.
     * sp also holds EA for compressed stack forms; no stack is needed.
     * a7: completion ECALL PC; t6: failure reason across an S failure.
     * Handlers preserve all observed registers until M checks the effects.
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

    /*
     * Entry 0 can deny this 64-byte NAPOT data block without locking it.
     * Entry 1 stays OFF at zero so entry 2 TOR starts at address zero.
     * M bypasses the unlocked deny entry and can inspect every byte.
     */
    la      t0, test_memory
    srli    t0, t0, 2
    ori     t0, t0, 7
    csrw    pmpaddr0, t0
    csrw    pmpaddr1, zero
    li      t0, 0x24000000
    csrw    pmpaddr2, t0
    li      t0, 0x0F0000
    csrw    pmpcfg0, t0

    la      s0, cases
    li      s1, 1
start_case:
    li      s5, STAGE_SETUP
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    csrw    CSR_DASICS_LIB_CFG, zero
    ld      s9, CASE_PROBE(s0)
    ld      s2, CASE_SOURCE(s0)
    ld      s3, CASE_DELEGATED(s0)
    ld      s4, CASE_CAUSE(s0)
    li      t0, EXPECT_DASICS
    bne     s4, t0, .Lcause_ready
    addi    s4, s2, CAUSE_U_DASICS
.Lcause_ready:
    li      s10, FREASON_SENTINEL
    li      t0, CAUSE_U_DASICS
    bltu    s4, t0, .Lreason_ready
    ld      s10, PROBE_WRITE(s9)
    addi    s10, s10, FREASON_LOAD
.Lreason_ready:
    li      s6, 0
    li      s7, 0
    li      s8, 0
    ld      s11, PROBE_PC(s9)
    ld      a7, PROBE_ECALL(s9)
    la      t0, test_memory
    li      t1, MEMORY_INITIAL
    li      t2, 8
.Linitialize_memory:
    sd      t1, 0(t0)
    addi    t0, t0, 8
    addi    t2, t2, -1
    bnez    t2, .Linitialize_memory
    fence   rw, rw

    la      t2, access_base
    ld      t0, CASE_ADDRESS(s0)
    add     a1, t2, t0
    mv      sp, a1
    ld      t0, CASE_LOWER(s0)
    add     t0, t2, t0
    csrw    CSR_DASICS_LIB_BOUND_LO0, t0
    ld      t0, CASE_UPPER(s0)
    add     t0, t2, t0
    csrw    CSR_DASICS_LIB_BOUND_HI0, t0
    /* Adjacent slot 1 and distant slot 15 are enabled only by their rows. */
    addi    t0, t2, 8
    csrw    CSR_DASICS_LIB_BOUND_LO1, t0
    addi    t0, t2, 16
    csrw    CSR_DASICS_LIB_BOUND_HI1, t0
    csrw    CSR_DASICS_LIB_BOUND_LO15, t2
    addi    t0, t2, 8
    csrw    CSR_DASICS_LIB_BOUND_HI15, t0
    ld      t0, CASE_LIB_CFG(s0)
    csrw    CSR_DASICS_LIB_CFG, t0

    csrw    CSR_DASICS_U_MAIN_BOUND_LO, zero
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, zero
    la      t0, supervisor_trusted_begin
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    la      t0, supervisor_trusted_end
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    ld      t0, CASE_TRUSTED(s0)
    beqz    t0, .Ltrust_ready
    la      t0, probes_begin
    bnez    s2, .Ltrust_supervisor_probe
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    la      t0, probes_end
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t0
    j       .Ltrust_ready
.Ltrust_supervisor_probe:
    /* Include both the probe and the S handler in the trusted interval. */
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
.Ltrust_ready:
    li      t0, 0x0F0000
    ld      t1, CASE_PMP_DENY(s0)
    beqz    t1, .Lpmp_ready
    ori     t0, t0, 0x18
.Lpmp_ready:
    csrw    pmpcfg0, t0

    li      t0, 0
    beqz    s3, .Ldelegation_ready
    mv      t1, s4
    bnez    t1, .Ldelegate_cause
    addi    t1, s2, CAUSE_U_DASICS
.Ldelegate_cause:
    li      t0, 1
    sll     t0, t0, t1
.Ldelegation_ready:
    csrw    medeleg, t0
    csrr    t1, medeleg
    li      t6, FAIL_DELEGATION
    bne     t0, t1, fail

    li      t0, MSTATUS_FS_MASK
    csrs    mstatus, t0
    li      t0, FPR_SENTINEL
    fmv.d.x fa0, t0
    li      t0, FPR_SOURCE
    fmv.d.x fa2, t0
    /* Start clean so rejected FP loads must preserve both fa0 and FS. */
    li      t0, MSTATUS_FS_MASK
    csrc    mstatus, t0
    li      t0, MSTATUS_FS_CLEAN
    csrs    mstatus, t0
    li      a0, GPR_SENTINEL
    li      a2, GPR_SOURCE
    li      t0, FREASON_SENTINEL
    csrw    CSR_DASICS_FREASON, t0
    ld      t0, CASE_MAIN_CFG(s0)
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      s5, STAGE_PROBE
    csrw    mepc, s11
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0
    slli    t0, s2, 11
    csrs    mstatus, t0
    mret

    /* Each probe executes exactly one memory operation before its marker. */
    .macro PROBE name, instruction, operand, base=a1, compressed=0
    .balign 8
\name\()_probe:
    .option push
    .if \compressed
    .option rvc
    .endif
    \instruction \operand, 0(\base)
    .option pop
    li      s7, 1
\name\()_ecall:
    ecall
    ebreak
    .endm

    .balign 8
probes_begin:
    PROBE lb, lb, a0
    PROBE lbu, lbu, a0
    PROBE lh, lh, a0
    PROBE lhu, lhu, a0
    PROBE lw, lw, a0
    PROBE lwu, lwu, a0
    PROBE ld, ld, a0
    PROBE sb, sb, a2
    PROBE sh, sh, a2
    PROBE sw, sw, a2
    PROBE sd, sd, a2
    PROBE flw, flw, fa0
    PROBE fld, fld, fa0
    PROBE fsw, fsw, fa2
    PROBE fsd, fsd, fa2
    PROBE clw, c.lw, a0, a1, 1
    PROBE cld, c.ld, a0, a1, 1
    PROBE cfld, c.fld, fa0, a1, 1
    PROBE csw, c.sw, a2, a1, 1
    PROBE csd, c.sd, a2, a1, 1
    PROBE cfsd, c.fsd, fa2, a1, 1
    PROBE clwsp, c.lwsp, a0, sp, 1
    PROBE cldsp, c.ldsp, a0, sp, 1
    PROBE cfldsp, c.fldsp, fa0, sp, 1
    PROBE cswsp, c.swsp, a2, sp, 1
    PROBE csdsp, c.sdsp, a2, sp, 1
    PROBE cfsdsp, c.fsdsp, fa2, sp, 1
    .balign 8
probes_end:

resume_entry:
    li      s8, 1
resume_ecall:
    ecall
    ebreak

    /* No handler changes the load destination or performs a test store. */
    .macro CHECK_FAULT_STATE failure
    li      t6, FAIL_STAGE
    li      t0, STAGE_PROBE
    bne     s5, t0, \failure
    bnez    s6, \failure
    li      t6, FAIL_COMPLETION
    bnez    s7, \failure
    li      t6, FAIL_RESUME
    bnez    s8, \failure
    li      t6, FAIL_FREASON
    csrr    t0, CSR_DASICS_FREASON
    bne     t0, s10, \failure
    .endm

    .balign 8
machine_trap_handler:
    csrr    t0, mepc
    la      t1, supervisor_failure_ecall
    beq     t0, t1, fail
    li      t6, FAIL_STAGE
    beqz    s5, fail
    li      t6, FAIL_SOURCE
    csrr    t0, mstatus
    srli    t0, t0, 11
    andi    t0, t0, 3
    bne     t0, s2, fail
    csrr    t0, mcause
    addi    t1, s2, CAUSE_U_ECALL
    beq     t0, t1, .Lmachine_ecall
    li      t6, FAIL_CAUSE
    beqz    s4, fail
    bne     t0, s4, fail
    li      t6, FAIL_ROUTE
    bnez    s3, fail
    li      t6, FAIL_EPC
    csrr    t0, mepc
    bne     t0, s11, fail
    li      t6, FAIL_TVAL
    csrr    t0, mtval
    bne     t0, a1, fail
    CHECK_FAULT_STATE fail
    li      s6, 1
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    mepc, t0
    mret

.Lmachine_ecall:
    bnez    s4, .Lcheck_resumed
    li      t6, FAIL_STAGE
    li      t0, STAGE_PROBE
    bne     s5, t0, fail
    bnez    s6, fail
    li      t6, FAIL_EPC
    csrr    t0, mepc
    bne     t0, a7, fail
    li      t6, FAIL_COMPLETION
    li      t0, 1
    bne     s7, t0, fail
    li      t6, FAIL_RESUME
    bnez    s8, fail
    j       .Lcheck_effects
.Lcheck_resumed:
    li      t6, FAIL_STAGE
    li      t0, STAGE_RESUME
    bne     s5, t0, fail
    li      t0, 1
    bne     s6, t0, fail
    li      t6, FAIL_EPC
    csrr    t0, mepc
    la      t1, resume_ecall
    bne     t0, t1, fail
    li      t6, FAIL_COMPLETION
    bnez    s7, fail
    li      t6, FAIL_RESUME
    li      t0, 1
    bne     s8, t0, fail

.Lcheck_effects:
    li      t6, FAIL_FREASON
    csrr    t0, CSR_DASICS_FREASON
    bne     t0, s10, fail
    /* Observe FS before using an FP instruction to inspect fa0. */
    csrr    t0, mstatus
    srli    a3, t0, 13
    andi    a3, a3, 3
    li      t0, 2
    bnez    s4, .Lexpected_fs_ready
    ld      t0, PROBE_FS(s9)
.Lexpected_fs_ready:
    li      t6, FAIL_FS
    bne     a3, t0, fail
    li      t0, GPR_SENTINEL
    bnez    s4, .Lexpected_gpr_ready
    ld      t0, PROBE_GPR(s9)
.Lexpected_gpr_ready:
    li      t6, FAIL_GPR
    bne     a0, t0, fail
    fmv.x.d a4, fa0
    li      t0, FPR_SENTINEL
    bnez    s4, .Lexpected_fpr_ready
    ld      t0, PROBE_FPR(s9)
.Lexpected_fpr_ready:
    li      t6, FAIL_FPR
    bne     a4, t0, fail

    /* Compare all 64 bytes, including guards around the requested access. */
    fence   rw, rw
    la      t0, test_memory
    li      t1, 64
    li      t6, FAIL_MEMORY
.Lcheck_memory:
    li      t2, 0xF1
    bnez    s4, .Lexpected_byte_ready
    ld      t3, PROBE_WRITE(s9)
    beqz    t3, .Lexpected_byte_ready
    bltu    t0, a1, .Lexpected_byte_ready
    ld      t3, PROBE_BYTES(s9)
    add     t3, a1, t3
    bgeu    t0, t3, .Lexpected_byte_ready
    sub     t4, t0, a1
    slli    t4, t4, 3
    ld      t5, PROBE_STORE_VALUE(s9)
    srl     t2, t5, t4
    andi    t2, t2, 0xFF
.Lexpected_byte_ready:
    lbu     t3, 0(t0)
    bne     t2, t3, fail
    addi    t0, t0, 1
    addi    t1, t1, -1
    bnez    t1, .Lcheck_memory
    addi    s0, s0, CASE_SIZE
    la      t0, cases_end
    beq     s0, t0, pass
    addi    s1, s1, 1
    j       start_case

    .balign 8
supervisor_trusted_begin:
supervisor_trap_handler:
    li      t6, FAIL_ROUTE
    li      t0, 1
    bne     s3, t0, supervisor_failure_ecall
    li      t6, FAIL_SOURCE
    csrr    t0, sstatus
    srli    t0, t0, 8
    andi    t0, t0, 1
    bne     t0, s2, supervisor_failure_ecall
    li      t6, FAIL_CAUSE
    beqz    s4, supervisor_failure_ecall
    csrr    t0, scause
    bne     t0, s4, supervisor_failure_ecall
    li      t6, FAIL_EPC
    csrr    t0, sepc
    bne     t0, s11, supervisor_failure_ecall
    li      t6, FAIL_TVAL
    csrr    t0, stval
    bne     t0, a1, supervisor_failure_ecall
    CHECK_FAULT_STATE supervisor_failure_ecall
    li      s6, 1
    li      s5, STAGE_RESUME
    la      t0, resume_entry
    csrw    sepc, t0
    sret
supervisor_failure_ecall:
    /* ECALL reaches M and preserves t6 for the shared diagnostic. */
    ecall
    ebreak
    .balign 8
supervisor_trusted_end:

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
    beqz    a2, .Linitialization_failed
    /* Reserve exit status 124 for the shared runner's timeout command. */
    li      t0, 124
    bltu    a2, t0, exit_test
    addi    a2, a2, 1
    j       exit_test
.Linitialization_failed:
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
    .macro DESCRIPTOR name, write, bytes, gpr, fpr, store_value, fs
\name\()_descriptor:
    .dword  \name\()_probe, \name\()_ecall, \write, \bytes
    .dword  \gpr, \fpr, \store_value, \fs
    .endm

probes:
    DESCRIPTOR lb, 0, 1, -15, FPR_SENTINEL, 0, 2
    DESCRIPTOR lbu, 0, 1, 0xF1, FPR_SENTINEL, 0, 2
    DESCRIPTOR lh, 0, 2, 0xFFFFFFFFFFFFF1F1, FPR_SENTINEL, 0, 2
    DESCRIPTOR lhu, 0, 2, 0xF1F1, FPR_SENTINEL, 0, 2
    DESCRIPTOR lw, 0, 4, 0xFFFFFFFFF1F1F1F1, FPR_SENTINEL, 0, 2
    DESCRIPTOR lwu, 0, 4, 0xF1F1F1F1, FPR_SENTINEL, 0, 2
    DESCRIPTOR ld, 0, 8, MEMORY_INITIAL, FPR_SENTINEL, 0, 2
    DESCRIPTOR sb, 1, 1, GPR_SENTINEL, FPR_SENTINEL, GPR_SOURCE, 2
    DESCRIPTOR sh, 1, 2, GPR_SENTINEL, FPR_SENTINEL, GPR_SOURCE, 2
    DESCRIPTOR sw, 1, 4, GPR_SENTINEL, FPR_SENTINEL, GPR_SOURCE, 2
    DESCRIPTOR sd, 1, 8, GPR_SENTINEL, FPR_SENTINEL, GPR_SOURCE, 2
    DESCRIPTOR flw, 0, 4, GPR_SENTINEL, 0xFFFFFFFFF1F1F1F1, 0, 3
    DESCRIPTOR fld, 0, 8, GPR_SENTINEL, MEMORY_INITIAL, 0, 3
    DESCRIPTOR fsw, 1, 4, GPR_SENTINEL, FPR_SENTINEL, FPR_SOURCE, 2
    DESCRIPTOR fsd, 1, 8, GPR_SENTINEL, FPR_SENTINEL, FPR_SOURCE, 2
    DESCRIPTOR clw, 0, 4, 0xFFFFFFFFF1F1F1F1, FPR_SENTINEL, 0, 2
    DESCRIPTOR cld, 0, 8, MEMORY_INITIAL, FPR_SENTINEL, 0, 2
    DESCRIPTOR cfld, 0, 8, GPR_SENTINEL, MEMORY_INITIAL, 0, 3
    DESCRIPTOR csw, 1, 4, GPR_SENTINEL, FPR_SENTINEL, GPR_SOURCE, 2
    DESCRIPTOR csd, 1, 8, GPR_SENTINEL, FPR_SENTINEL, GPR_SOURCE, 2
    DESCRIPTOR cfsd, 1, 8, GPR_SENTINEL, FPR_SENTINEL, FPR_SOURCE, 2
    DESCRIPTOR clwsp, 0, 4, 0xFFFFFFFFF1F1F1F1, FPR_SENTINEL, 0, 2
    DESCRIPTOR cldsp, 0, 8, MEMORY_INITIAL, FPR_SENTINEL, 0, 2
    DESCRIPTOR cfldsp, 0, 8, GPR_SENTINEL, MEMORY_INITIAL, 0, 3
    DESCRIPTOR cswsp, 1, 4, GPR_SENTINEL, FPR_SENTINEL, GPR_SOURCE, 2
    DESCRIPTOR csdsp, 1, 8, GPR_SENTINEL, FPR_SENTINEL, GPR_SOURCE, 2
    DESCRIPTOR cfsdsp, 1, 8, GPR_SENTINEL, FPR_SENTINEL, FPR_SOURCE, 2
probes_table_end:

    .macro CASE name, mode, delegated, main, lib, lo, hi, ea, cause, \
                pmp=0, trusted=0
    .dword  \name\()_descriptor, \mode, \delegated, \main, \lib
    .dword  \lo, \hi, \ea, \cause, \pmp, \trusted
    .endm

    .macro BASIC_CASES name
    CASE \name, PRV_U, 0, MAIN_CFG, LIB_RW, 0, 8, 0, 0
    CASE \name, PRV_U, 0, MAIN_CFG, 0, 0, 8, 0, EXPECT_DASICS
    CASE \name, PRV_S, 1, MAIN_CFG, LIB_RW, 0, 8, 0, 0
    CASE \name, PRV_S, 1, MAIN_CFG, 0, 0, 8, 0, EXPECT_DASICS
    .endm

cases:
    /* Four rows per instruction: U allow/deny, then S allow/deny. */
    BASIC_CASES lb
    BASIC_CASES lbu
    BASIC_CASES lh
    BASIC_CASES lhu
    BASIC_CASES lw
    BASIC_CASES lwu
    BASIC_CASES ld
    BASIC_CASES sb
    BASIC_CASES sh
    BASIC_CASES sw
    BASIC_CASES sd
    BASIC_CASES flw
    BASIC_CASES fld
    BASIC_CASES fsw
    BASIC_CASES fsd
    BASIC_CASES clw
    BASIC_CASES cld
    BASIC_CASES cfld
    BASIC_CASES csw
    BASIC_CASES csd
    BASIC_CASES cfsd
    BASIC_CASES clwsp
    BASIC_CASES cldsp
    BASIC_CASES cfldsp
    BASIC_CASES cswsp
    BASIC_CASES csdsp
    BASIC_CASES cfsdsp
cases_routes:
    .irp name, ld, sd
    CASE \name, PRV_U, 1, MAIN_CFG, LIB_RW, 0, 8, 0, 0
    CASE \name, PRV_U, 1, MAIN_CFG, 0, 0, 8, 0, EXPECT_DASICS
    CASE \name, PRV_S, 0, MAIN_CFG, LIB_RW, 0, 8, 0, 0
    CASE \name, PRV_S, 0, MAIN_CFG, 0, 0, 8, 0, EXPECT_DASICS
    .endr
cases_machine:
    CASE ld, PRV_M, 0, MAIN_CFG, 0, 0, 8, 0, 0
    CASE sd, PRV_M, 0, MAIN_CFG, 0, 0, 8, 0, 0

    .macro ENABLE_CASES name, mode, delegated, own, other
    CASE \name, \mode, \delegated, (MAIN_CFG & ~\own), 0, 0, 8, 0, 0
    CASE \name, \mode, \delegated, (MAIN_CFG & ~\other), 0, 0, 8, 0, \
         EXPECT_DASICS
    .endm
cases_enable:
    ENABLE_CASES ld, PRV_U, 0, DASICS_UENA, DASICS_SENA
    ENABLE_CASES sd, PRV_U, 0, DASICS_UENA, DASICS_SENA
    ENABLE_CASES ld, PRV_S, 1, DASICS_SENA, DASICS_UENA
    ENABLE_CASES sd, PRV_S, 1, DASICS_SENA, DASICS_UENA

    .macro CLOSE_CASES name, mode, delegated, own, other
    CASE \name, \mode, \delegated, (MAIN_CFG | \own), 0, 0, 8, 0, 0
    CASE \name, \mode, \delegated, (MAIN_CFG | \other), 0, 0, 8, 0, \
         EXPECT_DASICS
    .endm
cases_close:
    CLOSE_CASES ld, PRV_U, 0, DASICS_CULT, DASICS_CUST
    CLOSE_CASES sd, PRV_U, 0, DASICS_CUST, DASICS_CULT
    CLOSE_CASES ld, PRV_S, 1, DASICS_CSLT, DASICS_CSST
    CLOSE_CASES sd, PRV_S, 1, DASICS_CSST, DASICS_CSLT
cases_other_domain:
    CASE ld, PRV_U, 0, (MAIN_CFG | DASICS_CSLT), 0, 0, 8, 0, EXPECT_DASICS
    CASE sd, PRV_U, 0, (MAIN_CFG | DASICS_CSST), 0, 0, 8, 0, EXPECT_DASICS
    CASE ld, PRV_S, 1, (MAIN_CFG | DASICS_CULT), 0, 0, 8, 0, EXPECT_DASICS
    CASE sd, PRV_S, 1, (MAIN_CFG | DASICS_CUST), 0, 0, 8, 0, EXPECT_DASICS
cases_trusted:
    CASE ld, PRV_U, 0, MAIN_CFG, 0, 0, 8, 0, 0, 0, 1
    CASE sd, PRV_U, 0, MAIN_CFG, 0, 0, 8, 0, 0, 0, 1
    CASE ld, PRV_S, 1, MAIN_CFG, 0, 0, 8, 0, 0, 0, 1
    CASE sd, PRV_S, 1, MAIN_CFG, 0, 0, 8, 0, 0, 0, 1

    .macro PERMISSION_CASES name, mode, delegated, own, other
    CASE \name, \mode, \delegated, MAIN_CFG, \other, 0, 8, 0, EXPECT_DASICS
    CASE \name, \mode, \delegated, MAIN_CFG, (\own | LIB_U), 0, 8, 0, 0
    CASE \name, \mode, \delegated, MAIN_CFG, (\own & ~8), 0, 8, 0, \
         EXPECT_DASICS
    .endm
cases_permissions:
    PERMISSION_CASES ld, PRV_U, 0, LIB_READ, LIB_WRITE
    PERMISSION_CASES sd, PRV_U, 0, LIB_WRITE, LIB_READ
    PERMISSION_CASES ld, PRV_S, 1, LIB_READ, LIB_WRITE
    PERMISSION_CASES sd, PRV_S, 1, LIB_WRITE, LIB_READ

    .macro BOUNDARY_CASES name, mode, delegated
    CASE \name, \mode, \delegated, MAIN_CFG, LIB_RW, 0, 0, 0, EXPECT_DASICS
    CASE \name, \mode, \delegated, MAIN_CFG, LIB_RW, 8, 0, 0, EXPECT_DASICS
    CASE \name, \mode, \delegated, MAIN_CFG, LIB_RW, 8, 16, 0, EXPECT_DASICS
    CASE \name, \mode, \delegated, MAIN_CFG, LIB_RW, 0, 8, 8, EXPECT_DASICS
    CASE \name, \mode, \delegated, MAIN_CFG, LIB_RW, 0, 8, 0, 0
    CASE \name, \mode, \delegated, MAIN_CFG, LIB_RW, 0, 8, 4, EXPECT_DASICS
    .endm
cases_boundaries:
    BOUNDARY_CASES ld, PRV_U, 0
    BOUNDARY_CASES sd, PRV_U, 0
    BOUNDARY_CASES ld, PRV_S, 1
    BOUNDARY_CASES sd, PRV_S, 1
cases_bound_alignment:
    CASE ld, PRV_U, 0, MAIN_CFG, LIB_RW, 4, 12, 0, 0
    CASE sd, PRV_U, 0, MAIN_CFG, LIB_RW, 4, 12, 0, 0
    CASE ld, PRV_S, 1, MAIN_CFG, LIB_RW, 4, 12, 0, 0
    CASE sd, PRV_S, 1, MAIN_CFG, LIB_RW, 4, 12, 0, 0
cases_high_address:
    /* Same low address bits as the allowed region, different full VA. */
    CASE ld, PRV_U, 0, MAIN_CFG, LIB_RW, 0, 8, (1 << 63), EXPECT_DASICS
    CASE sd, PRV_U, 0, MAIN_CFG, LIB_RW, 0, 8, (1 << 63), EXPECT_DASICS
    CASE ld, PRV_S, 1, MAIN_CFG, LIB_RW, 0, 8, (1 << 63), EXPECT_DASICS
    CASE sd, PRV_S, 1, MAIN_CFG, LIB_RW, 0, 8, (1 << 63), EXPECT_DASICS

    .macro PRIORITY_CASES name, mode, delegated, misaligned, access
    CASE \name, \mode, \delegated, MAIN_CFG, 0, 0, 16, 1, EXPECT_DASICS
    CASE \name, \mode, \delegated, MAIN_CFG, LIB_RW, 0, 16, 1, \misaligned
    CASE \name, \mode, \delegated, MAIN_CFG, 0, 0, 8, 0, EXPECT_DASICS, 1
    CASE \name, \mode, \delegated, MAIN_CFG, LIB_RW, 0, 8, 0, \access, 1
    .endm
cases_priority:
    PRIORITY_CASES ld, PRV_U, 0, 4, 5
    PRIORITY_CASES sd, PRV_U, 0, 6, 7
    PRIORITY_CASES fld, PRV_U, 0, 4, 5
    PRIORITY_CASES fsd, PRV_U, 0, 6, 7
    PRIORITY_CASES ld, PRV_S, 1, 4, 5
    PRIORITY_CASES sd, PRV_S, 1, 6, 7
    PRIORITY_CASES fld, PRV_S, 1, 4, 5
    PRIORITY_CASES fsd, PRV_S, 1, 6, 7
cases_adjacent:
    /* Neither adjacent range alone covers this eight-byte access. */
    CASE ld, PRV_U, 0, MAIN_CFG, 0xBB, 0, 8, 4, EXPECT_DASICS
    CASE sd, PRV_U, 0, MAIN_CFG, 0xBB, 0, 8, 4, EXPECT_DASICS
    CASE ld, PRV_S, 1, MAIN_CFG, 0xBB, 0, 8, 4, EXPECT_DASICS
    CASE sd, PRV_S, 1, MAIN_CFG, 0xBB, 0, 8, 4, EXPECT_DASICS
cases_last_slot:
    CASE ld, PRV_U, 0, MAIN_CFG, (LIB_READ << 60), 0, 8, 0, 0
    CASE sd, PRV_U, 0, MAIN_CFG, (LIB_WRITE << 60), 0, 8, 0, 0
    CASE ld, PRV_S, 1, MAIN_CFG, (LIB_READ << 60), 0, 8, 0, 0
    CASE sd, PRV_S, 1, MAIN_CFG, (LIB_WRITE << 60), 0, 8, 0, 0
cases_end:
    .if ((cases_end - cases) / CASE_SIZE) > 253
    .error "Case exit codes must reserve timeout 124 and initialization 255"
    .endif

    .section .data
    .balign 64
test_memory:
    .fill   16, 1, 0xF1
access_base:
    .fill   48, 1, 0xF1
exit_args:
    .dword  0x20026
    .dword  0
failure_message:
    .ascii  "DASICS memory: case="
failure_case:
    .ascii  "000 reason="
failure_reason:
    .asciz  "00\n"
