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
    .equ CALLER_S3, 0x53
    .equ CALLER_S7, 0x57
    /* PROREG.G.I uses custom-0, funct3=3, rd=rs1=0 and mask bit N for sN. */
    .equ PROREG_G_I_S3, 0x0080300B
    .equ PROREG_G_I_S4, 0x0100300B
    .equ PROREG_G_I_S7, 0x0800300B
    .equ PROREG_G_I_S1_S3_S11, 0x80A0300B
    .equ PROREG_G_I_ZERO, 0x0000300B
    .equ PROREG_G_I_S11, 0x8000300B
    .equ PROREG_G_I_S3_S11, 0x8080300B
    .equ LEAVE, 0x0000500B
    .equ REUSE_ROUNDS, 192
    .equ GENERATION_ROUNDS, 32
    .equ GENERATION_SEED, 0x35
    .equ GENERATION_LOCAL, 0x2b
    .equ OCCUPIED_S3, 0x43
    .equ DISJOINT_S11, 0x6b
    .equ UPDATED_S11, 0x78

    .option norelax
    .option nopic
    .option norvc
    .section .text.init
    .globl _start
_start:
    li      s9, 255                 /* Keep the exit code outside the mask. */
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
    li      s9, 1
    li      s7, CALLER_S7
start_case:
    ld      t0, 0(s0)               /* Probe entry PC. */
    ld      s2, 8(s0)               /* Expected source privilege. */
    ld      s4, 16(s0)              /* Expected mcause. */
    ld      s5, 24(s0)              /* Expected mepc. */
    ld      s6, 32(s0)              /* Failure message. */
    ld      s8, 40(s0)              /* Expected probe opcode. */
    li      s3, CALLER_S3
    li      a3, -1
    li      a4, -1
    li      a5, 0
    li      a6, -1
    li      a7, -1
    csrw    mepc, t0
    li      t0, MSTATUS_MPP
    csrc    mstatus, t0
    slli    t0, s2, 11
    csrs    mstatus, t0
    mret

    .macro PROBE name, trusted_cases
    .balign 8
\name:
    .word   PROREG_G_I_S3
    mv      a3, s3
    addi    s3, s3, 1
    mv      a4, s3
    .word   LEAVE
    .word   PROREG_G_I_S4
    mv      a6, s3                  /* Restored caller mapping. */
    mv      a7, s4                  /* Hidden, never written by this probe. */
    .word   LEAVE
    .word   LEAVE                   /* Empty restore state. */
    .word   PROREG_G_I_S7           /* Held across the untrusted LEAVE. */
    addi    a5, zero, 1
\name\()_break:
    ebreak
\name\()_leave:
    .word   LEAVE
    mv      a3, s7
    addi    a5, zero, 1
\name\()_leave_break:
    ebreak
    .if \trusted_cases
sparse_caller:
    li      s1, 0x11
    li      s3, 0x33
    li      s11, 0xbb
    li      s10, 0x5a
    la      t0, sparse_callee
    .word   PROREG_G_I_S1_S3_S11
    .insn   i 0x0b, 1, ra, t0, 0     /* DASICSCALL.JR ra, t0, 0 */
sparse_return:
    .word   LEAVE
    mv      t2, s1
    mv      t3, s3
    mv      t4, s11
    mv      t5, s10
sparse_break:
    ebreak

reuse_caller:
    li      t2, 0x31
    li      t3, REUSE_ROUNDS
.Lreuse_round:
    mv      s3, t2
    addi    t4, t2, 0x100
    mv      s11, t4
    .word   PROREG_G_I_S3
    mv      a0, s3
    addi    s3, s3, 1
    mv      a1, s3
    .word   LEAVE
    .word   PROREG_G_I_S3_S11       /* Capture the same caller s3 again. */
    mv      a2, s3
    mv      a3, s11
    addi    s3, s3, 2
    mv      a4, s3
    mv      a5, s11                 /* Still hidden until LEAVE. */
    .word   LEAVE
    bnez    a0, .Lreuse_fail
    li      t0, 1
    bne     a1, t0, .Lreuse_fail
    bnez    a2, .Lreuse_fail
    bnez    a3, .Lreuse_fail
    li      t0, 2
    bne     a4, t0, .Lreuse_fail
    bnez    a5, .Lreuse_fail
    bne     s3, t2, .Lreuse_fail
    bne     s11, t4, .Lreuse_fail
    addi    t2, t2, 17
    addi    t3, t3, -1
    bnez    t3, .Lreuse_round
reuse_break:
    ebreak
.Lreuse_fail:
    ebreak                          /* Unexpected mepc identifies a failure. */

    /* Each iteration ends with a live slot and a different visible s3. */
generation_caller:
    li      s3, GENERATION_SEED
    .word   PROREG_G_I_S3
    li      s3, GENERATION_LOCAL
    li      t1, GENERATION_ROUNDS
generation_leave:
    .word   LEAVE
generation_write:
    addi    s3, s3, 1
generation_proreg:
    .word   PROREG_G_I_S3
    addi    s3, s3, GENERATION_LOCAL
    addi    t1, t1, -1
generation_branch:
    bnez    t1, generation_leave
generation_exit:
    mv      t2, s3
generation_final_leave:
    .word   LEAVE
    li      t0, GENERATION_LOCAL
    bne     t2, t0, .Lgeneration_fail
    li      t0, GENERATION_SEED + GENERATION_ROUNDS
    bne     s3, t0, .Lgeneration_fail
generation_break:
    ebreak
.Lgeneration_fail:
    ebreak

occupied_caller:
    li      s3, OCCUPIED_S3
    li      s11, DISJOINT_S11
    .word   PROREG_G_I_S3
occupied_zero:
    .word   PROREG_G_I_ZERO
    addi    a5, a5, 1               /* Executed only upon trap return. */
occupied_disjoint:
    .word   PROREG_G_I_S11
    addi    a5, a5, 1
    mv      a3, s3
    mv      a4, s11
    li      s3, 0x24
    li      s11, UPDATED_S11
    .word   LEAVE
    mv      a6, s3
    mv      a7, s11
occupied_break:
    ebreak
    .endif
    .balign 8
\name\()_end:
    .endm
#if defined(PROREG_TEST_U)
    PROBE probe_a, 1
    PROBE probe_b, 0
#else
    PROBE probe_a, 0
    PROBE probe_b, 1
#endif

    /* This leaf is outside both trusted ranges and uses only registers. */
    .balign 8
sparse_callee:
    mv      a0, s1
    mv      a1, s3
    mv      a2, s11
    mv      a3, s10
    li      s3, 0xa3
    li      s11, 0xab
    li      s10, 0x6a
    mv      a4, s1
    mv      a5, s3
    mv      a6, s11
    mv      a7, s10
    ret

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
    la      t1, sparse_break
    beq     t0, t1, check_sparse
    la      t1, reuse_break
    beq     t0, t1, case_passed
    la      t1, generation_break
    beq     t0, t1, case_passed
    la      t1, occupied_zero
    beq     t0, t1, resume_occupied
    la      t1, occupied_disjoint
    beq     t0, t1, resume_occupied
    la      t1, occupied_break
    beq     t0, t1, check_occupied
    li      t0, BREAKPOINT
    bne     s4, t0, check_illegal
    li      t0, 1
    bne     a5, t0, fail
    li      t0, LEAVE
    beq     s8, t0, check_trusted_leave
    bnez    a3, fail
    li      t0, 1
    bne     a4, t0, fail
    li      t0, CALLER_S3
    bne     a6, t0, fail
    bnez    a7, fail
    bnez    s7, fail
    j       case_passed
check_trusted_leave:
    li      t0, CALLER_S7
    bne     a3, t0, fail
    j       case_passed
check_illegal:
    bnez    a5, fail
    li      t0, -1
    bne     a3, t0, fail
    bne     a4, t0, fail
    li      t0, CALLER_S3
    bne     s3, t0, fail
    csrr    t0, mtval
    bne     t0, s8, fail
    li      t0, LEAVE
    bne     s8, t0, case_passed
    bnez    s7, fail                /* Denial preserved the hidden mapping. */
case_passed:
    addi    s0, s0, 48
    addi    s9, s9, 1
    la      t0, cases_end
    bne     s0, t0, start_case
    li      a2, 0
    j       exit_test

resume_occupied:
    csrr    t1, mtval
    bne     t1, s8, fail
    bnez    s3, fail
    li      t1, DISJOINT_S11
    bne     s11, t1, fail
    addi    t0, t0, 4               /* Resume just past this failed PROREG. */
    csrw    mepc, t0
    li      t1, PROREG_G_I_ZERO
    bne     s8, t1, .Lafter_disjoint
    bnez    a5, fail
    la      s5, occupied_disjoint
    li      s8, PROREG_G_I_S11
    la      s6, disjoint_failure
    mret
.Lafter_disjoint:
    li      t1, 1
    bne     a5, t1, fail
    li      s4, BREAKPOINT
    la      s5, occupied_break
    la      s6, occupied_restore_failure
    mret

check_occupied:
    li      t0, 2
    bne     a5, t0, fail
    bnez    a3, fail
    li      t0, DISJOINT_S11
    bne     a4, t0, fail
    li      t0, OCCUPIED_S3
    bne     a6, t0, fail
    li      t0, UPDATED_S11
    bne     a7, t0, fail
    j       case_passed

    .macro CHECK_SPARSE observed, expected, stage, reg
    .pushsection .rodata
.Lsparse_failure\@:
    .asciz "Sparse protection: \stage \reg failed\n"
    .popsection
    la      s6, .Lsparse_failure\@
    li      t0, \expected
    bne     \observed, t0, fail
    .endm

check_sparse:
    CHECK_SPARSE a0,  0,    entry, s1
    CHECK_SPARSE a1,  0,    entry, s3
    CHECK_SPARSE a2,  0,    entry, s11
    CHECK_SPARSE a3,  0x5a, entry, s10
    CHECK_SPARSE a4,  0,    after_write, s1
    CHECK_SPARSE a5,  0xa3, after_write, s3
    CHECK_SPARSE a6,  0xab, after_write, s11
    CHECK_SPARSE a7,  0x6a, after_write, s10
    CHECK_SPARSE t2,  0x11, after_leave, s1
    CHECK_SPARSE t3,  0x33, after_leave, s3
    CHECK_SPARSE t4,  0xbb, after_leave, s11
    CHECK_SPARSE t5,  0x6a, after_leave, s10
    j       case_passed

fail:
    li      a0, 0x04                /* SYS_WRITE0 */
    mv      a1, s6
    .balign 16
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
    mv      a2, s9
    bnez    a2, exit_test
    li      a2, 255
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
    /* Deny PROREG with empty slots, then deny LEAVE while s7 is protected. */
#if defined(PROREG_TEST_U)
    .equ BOOT_PRIV, PRV_U
    .dword probe_b, PRV_U, ILLEGAL, probe_b
    .dword untrusted_u_failure, PROREG_G_I_S3
    .dword probe_a, PRV_U, BREAKPOINT, probe_a_break
    .dword trusted_u_failure, PROREG_G_I_S3
    .dword probe_b_leave, PRV_U, ILLEGAL, probe_b_leave
    .dword untrusted_leave_failure, LEAVE
    .dword probe_a_leave, PRV_U, BREAKPOINT, probe_a_leave_break
    .dword trusted_leave_failure, LEAVE
    .dword sparse_caller, PRV_U, BREAKPOINT, sparse_break
    .dword sparse_call_failure, PROREG_G_I_S1_S3_S11
#elif defined(PROREG_TEST_S)
    .equ BOOT_PRIV, PRV_S
    .dword probe_a, PRV_S, ILLEGAL, probe_a
    .dword untrusted_s_failure, PROREG_G_I_S3
    .dword probe_b, PRV_S, BREAKPOINT, probe_b_break
    .dword trusted_s_failure, PROREG_G_I_S3
    .dword probe_a_leave, PRV_S, ILLEGAL, probe_a_leave
    .dword untrusted_leave_failure, LEAVE
    .dword probe_b_leave, PRV_S, BREAKPOINT, probe_b_leave_break
    .dword trusted_leave_failure, LEAVE
    .dword sparse_caller, PRV_S, BREAKPOINT, sparse_break
    .dword sparse_call_failure, PROREG_G_I_S1_S3_S11
#else
#error "Select a U or S boot for the PROREG test"
#endif
    .dword reuse_caller, BOOT_PRIV, BREAKPOINT, reuse_break
    .dword reuse_failure, PROREG_G_I_S3
    .dword generation_caller, BOOT_PRIV, BREAKPOINT, generation_break
    .dword generation_failure, PROREG_G_I_S3
    .dword occupied_caller, BOOT_PRIV, ILLEGAL, occupied_zero
    .dword occupied_zero_failure, PROREG_G_I_ZERO
cases_end:
setup_failure:       .asciz "PROREG.G.I: setup failed\n"
trusted_u_failure:   .asciz "PROREG.G.I: trusted U failed\n"
trusted_s_failure:   .asciz "PROREG.G.I: trusted S failed\n"
untrusted_u_failure: .asciz "PROREG.G.I: untrusted U failed\n"
untrusted_s_failure: .asciz "PROREG.G.I: untrusted S failed\n"
trusted_leave_failure:   .asciz "LEAVE: trusted restore failed\n"
untrusted_leave_failure: .asciz "LEAVE: untrusted denial failed\n"
sparse_call_failure: .asciz "Sparse protection: unexpected trap\n"
reuse_failure: .asciz "PROREG: repeated s3 mapping reuse failed\n"
generation_failure: .asciz "PROREG: wrong s3 generation at loop exit\n"
occupied_zero_failure: .asciz "PROREG: occupied zero-mask rejection failed\n"
disjoint_failure: .asciz "PROREG: occupied disjoint-mask rejection failed\n"
occupied_restore_failure: .asciz "PROREG: state after conflicts failed\n"

    .section .data
    .balign 8
exit_args:
    .dword  0x20026, 0
