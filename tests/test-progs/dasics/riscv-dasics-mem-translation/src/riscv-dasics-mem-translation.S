/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CSR_DASICS_S_MAIN_CFG, 0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3
    .equ CSR_DASICS_LIB_CFG, 0x880
    .equ CSR_DASICS_LIB_BOUND_LO0, 0x890
    .equ CSR_DASICS_LIB_BOUND_HI0, 0x891
    .equ CSR_DASICS_FREASON, 0x8B3
    .equ DASICS_SENA, (1 << 0)
    .equ DASICS_UENA, (1 << 1)
    .equ DASICS_CUET, (1 << 2)
    .equ DASICS_CUFT, (1 << 5)
    .equ DASICS_CSET, (1 << 6)
    .equ DASICS_CSFT, (1 << 9)
    /* Enable data protection in the source domain; bypass other checks. */
    .equ MAIN_CFG_U, DASICS_UENA | DASICS_CUET | DASICS_CUFT
    .equ MAIN_CFG_S, DASICS_SENA | DASICS_CSET | DASICS_CSFT
    .equ LIB_READ, 0xA
    .equ LIB_WRITE, 0x9
    .equ LIB_DENY, 0x8
    .equ FREASON_SENTINEL, 5
    .equ FREASON_LOAD, 2
    .equ FREASON_STORE, 3
    .equ CAUSE_U_ECALL, 8
    .equ CAUSE_LOAD_PAGE, 13
    .equ CAUSE_STORE_PAGE, 15
    .equ CAUSE_U_DASICS, 24
    .equ CAUSE_S_DASICS, 25
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ PAGE_SIZE, 4096
    .equ PROBE_CODE_VA, 0x40000000
    .equ DATA_VA, 0x40001000
    .equ LOAD_VALUE, 0x1122334455667788
    .equ STORE_VALUE, 0x0807060504030201
    .equ GPR_SENTINEL, 0xA5A5A5A5A5A5A5A5
    .equ FPR_SENTINEL, 0x8877665544332211
    .equ MSTATUS_FS_MASK, (3 << 13)
    .equ MSTATUS_FS_CLEAN, (2 << 13)
    .equ SATP_SV39, (8 << 60)
    .equ PTE_V, (1 << 0)
    .equ PTE_R, (1 << 1)
    .equ PTE_W, (1 << 2)
    .equ PTE_X, (1 << 3)
    .equ PTE_U, (1 << 4)
    .equ PTE_A, (1 << 6)
    .equ PTE_D, (1 << 7)
    .equ PTE_USER_RX, PTE_V | PTE_R | PTE_X | PTE_U | PTE_A | PTE_D
    .equ PTE_USER_RW, PTE_V | PTE_R | PTE_W | PTE_U | PTE_A | PTE_D
    .equ PTE_SUPERVISOR_RX, PTE_V | PTE_R | PTE_X | PTE_A | PTE_D
    .equ PTE_SUPERVISOR_RW, PTE_V | PTE_R | PTE_W | PTE_A | PTE_D
    .equ ENTRY_STATUS_CLEAR, (1 << 3) | (1 << 7) | (3 << 11) \
                            | (1 << 17) | (1 << 18) | (1 << 19)

    .equ CASE_PROBE, 0
    .equ CASE_ECALL, 8
    .equ CASE_ADDRESS, 16
    .equ CASE_PTE_FLAGS, 24
    .equ CASE_LIB_CFG, 32
    .equ CASE_CAUSE, 40
    .equ CASE_FREASON, 48
    .equ CASE_IS_STORE, 56
    .equ CASE_IS_FP, 64
    .equ CASE_SOURCE, 72
    .equ CASE_SIZE, 80

    .equ FAIL_DASICS_CONFIG, 1
    .equ FAIL_SATP, 2
    .equ FAIL_CAUSE, 3
    .equ FAIL_SOURCE, 4
    .equ FAIL_EPC, 5
    .equ FAIL_TVAL, 6
    .equ FAIL_COMPLETION, 7
    .equ FAIL_GPR, 8
    .equ FAIL_MEMORY, 9
    .equ FAIL_FREASON, 10
    .equ FAIL_FPR, 11
    .equ FAIL_FS, 12

    /*
     * s0 holds expected SATP; s1 is the probe completion marker.
     * s2/s3 identify the case row and ID; s4/s5 hold expected cause/FReason.
     * s6/s7 identify store/FP probes and select expected side effects.
     * A zero expected cause means normal completion through ECALL.
     * s8/s9 hold the probe and completion ECALL virtual PCs.
     * s10 holds the source privilege for page permissions, MRET and MPP.
     * a0 is the load destination, a1 the data VA, and a2 the store source.
     * fa0/fa2 are the corresponding FP destination/source registers.
     * The M handler preserves these registers until checking them.
     * No stack or translated M-mode data access is used.
     */
    .option norelax
    .option nopic
    .option norvc
    .section .text.init
    .globl _start
_start:
    li      s3, 0
    la      t0, machine_trap_handler
    csrw    mtvec, t0
    csrw    mie, zero
    csrw    mideleg, zero
    csrw    medeleg, zero
    csrw    satp, zero
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0

    /* Keep setup in M mode and leave no trusted U/S instruction interval. */
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, zero
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, zero
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, zero
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, zero

    /* TOR permits physical addresses below 0x90000000, including the image. */
    li      t0, (0x90000000 >> 2)
    csrw    pmpaddr0, t0
    li      t0, 0x0F
    csrw    pmpcfg0, t0

    /* Code and all data virtual pages use VPN[2]=1 and VPN[1]=0. */
    la      t0, root_table
    la      t1, level1_table
    srli    t1, t1, 12
    slli    t1, t1, 10
    ori     t1, t1, PTE_V
    sd      t1, 8(t0)

    la      t0, level1_table
    la      t1, level0_table
    srli    t1, t1, 12
    slli    t1, t1, 10
    ori     t1, t1, PTE_V
    sd      t1, 0(t0)

    la      s0, root_table
    srli    s0, s0, 12
    li      t0, SATP_SV39
    or      s0, s0, t0
    la      s2, cases
    li      s3, 1
start_case:
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0
    ld      a1, CASE_ADDRESS(s2)
    ld      s4, CASE_CAUSE(s2)
    ld      s5, CASE_FREASON(s2)
    ld      s6, CASE_IS_STORE(s2)
    ld      s7, CASE_IS_FP(s2)
    ld      s10, CASE_SOURCE(s2)
    ld      s8, CASE_PROBE(s2)
    ld      s9, CASE_ECALL(s2)
    la      t0, probe_code_page
    sub     s8, s8, t0
    sub     s9, s9, t0
    li      t0, PROBE_CODE_VA
    add     s8, s8, t0
    add     s9, s9, t0

    /* The code leaf stays valid; its U bit matches the source privilege. */
    la      t0, level0_table
    la      t1, probe_code_page
    srli    t1, t1, 12
    slli    t1, t1, 10
    li      t2, PTE_USER_RX
    beqz    s10, .Lcode_flags_ready
    li      t2, PTE_SUPERVISOR_RX
.Lcode_flags_ready:
    or      t1, t1, t2
    sd      t1, 0(t0)

    /* Invalid data leaves still require a full walk through valid parents. */
    srli    t0, a1, 12
    andi    t0, t0, 0x1FF
    slli    t0, t0, 3
    la      t1, level0_table
    add     t0, t0, t1
    la      t1, test_data_page
    srli    t1, t1, 12
    slli    t1, t1, 10
    ld      t2, CASE_PTE_FLAGS(s2)
    or      t1, t1, t2
    sd      t1, 0(t0)

    /* DASICS bounds describe the virtual access, not its physical page. */
    csrw    CSR_DASICS_LIB_BOUND_LO0, a1
    addi    t0, a1, 8
    csrw    CSR_DASICS_LIB_BOUND_HI0, t0
    ld      t1, CASE_LIB_CFG(s2)
    csrw    CSR_DASICS_LIB_CFG, t1
    li      t6, FAIL_DASICS_CONFIG
    csrr    t2, CSR_DASICS_LIB_CFG
    bne     t1, t2, fail
    li      t0, FREASON_SENTINEL
    csrw    CSR_DASICS_FREASON, t0
    li      t0, MAIN_CFG_U
    beqz    s10, .Lmain_cfg_ready
    li      t0, MAIN_CFG_S
.Lmain_cfg_ready:
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t0, t1, fail

    la      t0, test_data_page
    li      t1, LOAD_VALUE
    sd      t1, 0(t0)
    /* Publish the PTE and data, then remove cached translations per case. */
    fence   rw, rw
    csrw    satp, s0
    sfence.vma zero, zero
    li      t6, FAIL_SATP
    csrr    t0, satp
    bne     t0, s0, fail

    li      a0, GPR_SENTINEL
    li      a2, STORE_VALUE
    li      t0, MSTATUS_FS_MASK
    csrs    mstatus, t0
    li      t0, FPR_SENTINEL
    fmv.d.x fa0, t0
    fmv.d.x fa2, a2
    /* Rejected FP loads must preserve both the destination and clean FS. */
    li      t0, MSTATUS_FS_MASK
    csrc    mstatus, t0
    li      t0, MSTATUS_FS_CLEAN
    csrs    mstatus, t0
    li      s1, 0
    csrw    mepc, s8
    slli    t0, s10, 11
    csrs    mstatus, t0
    mret

    .balign 4
machine_trap_handler:
    /* M mode uses physical addresses even while SATP selects Sv39. */
    li      t6, FAIL_CAUSE
    csrr    t0, mcause
    mv      t1, s4
    bnez    t1, .Lexpected_cause
    /* U/S privilege encodings 0/1 select ECALL causes 8/9. */
    addi    t1, s10, CAUSE_U_ECALL
.Lexpected_cause:
    bne     t0, t1, fail
    li      t6, FAIL_SOURCE
    csrr    t0, mstatus
    srli    t0, t0, 11
    andi    t0, t0, 3
    bne     t0, s10, fail
    li      t6, FAIL_EPC
    csrr    t0, mepc
    mv      t1, s8
    bnez    s4, .Lexpected_epc
    mv      t1, s9
.Lexpected_epc:
    bne     t0, t1, fail
    li      t6, FAIL_TVAL
    csrr    t0, mtval
    li      t1, 0
    beqz    s4, .Lexpected_tval
    mv      t1, a1
.Lexpected_tval:
    bne     t0, t1, fail
    li      t6, FAIL_COMPLETION
    seqz    t0, s4
    bne     s1, t0, fail
    li      t6, FAIL_GPR
    li      t0, GPR_SENTINEL
    bnez    s4, .Lexpected_value
    bnez    s6, .Lexpected_value
    bnez    s7, .Lexpected_value
    li      t0, LOAD_VALUE
.Lexpected_value:
    bne     a0, t0, fail
    li      t0, STORE_VALUE
    bne     a2, t0, fail
    /* Check FS before any FP instruction used to inspect register values. */
    li      t6, FAIL_FS
    csrr    t0, mstatus
    srli    t0, t0, 13
    andi    t0, t0, 3
    li      t1, 2
    bnez    s4, .Lexpected_fs
    bnez    s6, .Lexpected_fs
    beqz    s7, .Lexpected_fs
    li      t1, 3
.Lexpected_fs:
    bne     t0, t1, fail
    li      t6, FAIL_FPR
    li      t0, FPR_SENTINEL
    bnez    s4, .Lexpected_fpr
    bnez    s6, .Lexpected_fpr
    beqz    s7, .Lexpected_fpr
    li      t0, LOAD_VALUE
.Lexpected_fpr:
    fmv.x.d t1, fa0
    bne     t0, t1, fail
    fmv.x.d t1, fa2
    li      t0, STORE_VALUE
    bne     t0, t1, fail
    li      t6, FAIL_MEMORY
    li      t0, LOAD_VALUE
    bnez    s4, .Lexpected_memory
    beqz    s6, .Lexpected_memory
    li      t0, STORE_VALUE
.Lexpected_memory:
    la      t1, test_data_page
    ld      t1, 0(t1)
    bne     t0, t1, fail
    li      t6, FAIL_FREASON
    csrr    t0, CSR_DASICS_FREASON
    bne     t0, s5, fail
    li      t6, FAIL_SATP
    csrr    t0, satp
    bne     t0, s0, fail
    addi    s2, s2, CASE_SIZE
    la      t0, cases_end
    beq     s2, t0, pass
    addi    s3, s3, 1
    j       start_case

pass:
    li      a2, 0
    j       exit_test

fail:
    /* Report the failed check before returning its nonzero exit status. */
    li      t0, 10
    la      t3, failure_case
    divu    t1, s3, t0
    remu    t2, s3, t0
    addi    t1, t1, '0'
    addi    t2, t2, '0'
    sb      t1, 0(t3)
    sb      t2, 1(t3)
    la      t3, failure_reason
    divu    t1, t6, t0
    remu    t2, t6, t0
    addi    t1, t1, '0'
    addi    t2, t2, '0'
    sb      t1, 0(t3)
    sb      t2, 1(t3)
    fence   rw, rw
    li      a0, 0x04
    la      a1, failure_message
    .balign 16
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
    mv      a2, t6
exit_test:
    la      a1, exit_args
    sd      a2, 8(a1)
    fence   rw, rw
    li      a0, 0x20
    .balign 16
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
halt:
    j       halt

    /* Keep all U/S probes in one page mapped with each case's privilege. */
    .balign PAGE_SIZE
probe_code_page:
    .macro PROBE name, instruction=ld, operand=a0
\name:
    \instruction \operand, 0(a1)
    li      s1, 1
\name\()_ecall:
    ecall
    ebreak
    .endm
    PROBE u_ld_mapped_allow
    PROBE u_ld_mapped_deny
    PROBE u_ld_page_fault_allow
    PROBE u_ld_page_fault_deny
    PROBE u_sd_mapped_allow, sd, a2
    PROBE u_sd_mapped_deny, sd, a2
    PROBE u_sd_page_fault_allow, sd, a2
    PROBE u_sd_page_fault_deny, sd, a2
    PROBE u_fld_mapped_allow, fld, fa0
    PROBE u_fld_mapped_deny, fld, fa0
    PROBE u_fld_page_fault_allow, fld, fa0
    PROBE u_fld_page_fault_deny, fld, fa0
    PROBE u_fsd_mapped_allow, fsd, fa2
    PROBE u_fsd_mapped_deny, fsd, fa2
    PROBE u_fsd_page_fault_allow, fsd, fa2
    PROBE u_fsd_page_fault_deny, fsd, fa2
    PROBE s_ld_mapped_allow
    PROBE s_ld_mapped_deny
    PROBE s_ld_page_fault_allow
    PROBE s_ld_page_fault_deny
    PROBE s_sd_mapped_allow, sd, a2
    PROBE s_sd_mapped_deny, sd, a2
    PROBE s_sd_page_fault_allow, sd, a2
    PROBE s_sd_page_fault_deny, sd, a2
    PROBE s_fld_mapped_allow, fld, fa0
    PROBE s_fld_mapped_deny, fld, fa0
    PROBE s_fld_page_fault_allow, fld, fa0
    PROBE s_fld_page_fault_deny, fld, fa0
    PROBE s_fsd_mapped_allow, fsd, fa2
    PROBE s_fsd_mapped_deny, fsd, fa2
    PROBE s_fsd_page_fault_allow, fsd, fa2
    PROBE s_fsd_page_fault_deny, fsd, fa2
    .if (.-probe_code_page) > PAGE_SIZE
    .error "Probe code exceeds its mapped page"
    .endif
    .balign PAGE_SIZE

    .section .rodata
    .balign 8
    .macro CASE probe, address, flags, lib, cause, reason, is_store=0, \
                is_fp=0, source=PRV_U
    .dword  \probe, \probe\()_ecall, \address, \flags, \lib
    .dword  \cause, \reason, \is_store, \is_fp, \source
    .endm
cases:
    CASE u_ld_mapped_allow, DATA_VA, PTE_USER_RW, LIB_READ, 0, \
         FREASON_SENTINEL
    CASE u_ld_mapped_deny, (DATA_VA + PAGE_SIZE), PTE_USER_RW, LIB_DENY, \
         CAUSE_U_DASICS, FREASON_LOAD
    CASE u_ld_page_fault_allow, (DATA_VA + 2 * PAGE_SIZE), 0, LIB_READ, \
         CAUSE_LOAD_PAGE, FREASON_SENTINEL
    CASE u_ld_page_fault_deny, (DATA_VA + 3 * PAGE_SIZE), 0, LIB_DENY, \
         CAUSE_LOAD_PAGE, FREASON_SENTINEL
    CASE u_sd_mapped_allow, (DATA_VA + 4 * PAGE_SIZE), PTE_USER_RW, \
         LIB_WRITE, 0, FREASON_SENTINEL, 1
    CASE u_sd_mapped_deny, (DATA_VA + 5 * PAGE_SIZE), PTE_USER_RW, \
         LIB_DENY, CAUSE_U_DASICS, FREASON_STORE, 1
    CASE u_sd_page_fault_allow, (DATA_VA + 6 * PAGE_SIZE), 0, LIB_WRITE, \
         CAUSE_STORE_PAGE, FREASON_SENTINEL, 1
    CASE u_sd_page_fault_deny, (DATA_VA + 7 * PAGE_SIZE), 0, LIB_DENY, \
         CAUSE_STORE_PAGE, FREASON_SENTINEL, 1
    CASE u_fld_mapped_allow, (DATA_VA + 8 * PAGE_SIZE), PTE_USER_RW, \
         LIB_READ, 0, FREASON_SENTINEL, 0, 1
    CASE u_fld_mapped_deny, (DATA_VA + 9 * PAGE_SIZE), PTE_USER_RW, \
         LIB_DENY, CAUSE_U_DASICS, FREASON_LOAD, 0, 1
    CASE u_fld_page_fault_allow, (DATA_VA + 10 * PAGE_SIZE), 0, \
         LIB_READ, CAUSE_LOAD_PAGE, FREASON_SENTINEL, 0, 1
    CASE u_fld_page_fault_deny, (DATA_VA + 11 * PAGE_SIZE), 0, LIB_DENY, \
         CAUSE_LOAD_PAGE, FREASON_SENTINEL, 0, 1
    CASE u_fsd_mapped_allow, (DATA_VA + 12 * PAGE_SIZE), PTE_USER_RW, \
         LIB_WRITE, 0, FREASON_SENTINEL, 1, 1
    CASE u_fsd_mapped_deny, (DATA_VA + 13 * PAGE_SIZE), PTE_USER_RW, \
         LIB_DENY, CAUSE_U_DASICS, FREASON_STORE, 1, 1
    CASE u_fsd_page_fault_allow, (DATA_VA + 14 * PAGE_SIZE), 0, \
         LIB_WRITE, CAUSE_STORE_PAGE, FREASON_SENTINEL, 1, 1
    CASE u_fsd_page_fault_deny, (DATA_VA + 15 * PAGE_SIZE), 0, LIB_DENY, \
         CAUSE_STORE_PAGE, FREASON_SENTINEL, 1, 1
    CASE s_ld_mapped_allow, (DATA_VA + 16 * PAGE_SIZE), \
         PTE_SUPERVISOR_RW, LIB_READ, 0, FREASON_SENTINEL, 0, 0, PRV_S
    CASE s_ld_mapped_deny, (DATA_VA + 17 * PAGE_SIZE), \
         PTE_SUPERVISOR_RW, LIB_DENY, CAUSE_S_DASICS, FREASON_LOAD, 0, 0, PRV_S
    CASE s_ld_page_fault_allow, (DATA_VA + 18 * PAGE_SIZE), 0, \
         LIB_READ, CAUSE_LOAD_PAGE, FREASON_SENTINEL, 0, 0, PRV_S
    CASE s_ld_page_fault_deny, (DATA_VA + 19 * PAGE_SIZE), 0, \
         LIB_DENY, CAUSE_LOAD_PAGE, FREASON_SENTINEL, 0, 0, PRV_S
    CASE s_sd_mapped_allow, (DATA_VA + 20 * PAGE_SIZE), \
         PTE_SUPERVISOR_RW, LIB_WRITE, 0, FREASON_SENTINEL, 1, 0, PRV_S
    CASE s_sd_mapped_deny, (DATA_VA + 21 * PAGE_SIZE), \
         PTE_SUPERVISOR_RW, LIB_DENY, CAUSE_S_DASICS, FREASON_STORE, \
         1, 0, PRV_S
    CASE s_sd_page_fault_allow, (DATA_VA + 22 * PAGE_SIZE), 0, \
         LIB_WRITE, CAUSE_STORE_PAGE, FREASON_SENTINEL, 1, 0, PRV_S
    CASE s_sd_page_fault_deny, (DATA_VA + 23 * PAGE_SIZE), 0, \
         LIB_DENY, CAUSE_STORE_PAGE, FREASON_SENTINEL, 1, 0, PRV_S
    CASE s_fld_mapped_allow, (DATA_VA + 24 * PAGE_SIZE), \
         PTE_SUPERVISOR_RW, LIB_READ, 0, FREASON_SENTINEL, 0, 1, PRV_S
    CASE s_fld_mapped_deny, (DATA_VA + 25 * PAGE_SIZE), \
         PTE_SUPERVISOR_RW, LIB_DENY, CAUSE_S_DASICS, FREASON_LOAD, 0, 1, PRV_S
    CASE s_fld_page_fault_allow, (DATA_VA + 26 * PAGE_SIZE), 0, \
         LIB_READ, CAUSE_LOAD_PAGE, FREASON_SENTINEL, 0, 1, PRV_S
    CASE s_fld_page_fault_deny, (DATA_VA + 27 * PAGE_SIZE), 0, \
         LIB_DENY, CAUSE_LOAD_PAGE, FREASON_SENTINEL, 0, 1, PRV_S
    CASE s_fsd_mapped_allow, (DATA_VA + 28 * PAGE_SIZE), \
         PTE_SUPERVISOR_RW, LIB_WRITE, 0, FREASON_SENTINEL, 1, 1, PRV_S
    CASE s_fsd_mapped_deny, (DATA_VA + 29 * PAGE_SIZE), \
         PTE_SUPERVISOR_RW, LIB_DENY, CAUSE_S_DASICS, FREASON_STORE, \
         1, 1, PRV_S
    CASE s_fsd_page_fault_allow, (DATA_VA + 30 * PAGE_SIZE), 0, \
         LIB_WRITE, CAUSE_STORE_PAGE, FREASON_SENTINEL, 1, 1, PRV_S
    CASE s_fsd_page_fault_deny, (DATA_VA + 31 * PAGE_SIZE), 0, \
         LIB_DENY, CAUSE_STORE_PAGE, FREASON_SENTINEL, 1, 1, PRV_S
cases_end:
    .if ((cases_end - cases) / CASE_SIZE) > 99
    .error "Case IDs must fit the two-digit diagnostic field"
    .endif

    .section .data
    .balign PAGE_SIZE
root_table:
    .zero   PAGE_SIZE
level1_table:
    .zero   PAGE_SIZE
level0_table:
    .zero   PAGE_SIZE
test_data_page:
    .zero   PAGE_SIZE
exit_args:
    .dword  0x20026
    .dword  0
failure_message:
    .ascii  "DASICS translation: case="
failure_case:
    .ascii  "00 reason="
failure_reason:
    .asciz  "00\n"
