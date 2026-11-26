/* SPDX-License-Identifier: BSD-3-Clause */

    .equ CSR_DASICS_S_MAIN_CFG,      0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3
    .equ CSR_DASICS_PROREG_MASK,    0x8B5
    .equ DASICS_SENA, 1 << 0
    .equ DASICS_UENA, 1 << 1
    .equ PRV_U, 0
    .equ PRV_S, 1
    .equ ILLEGAL, 2
    .equ BREAKPOINT, 3
    .equ MSTATUS_MPP, 3 << 11
    .equ MSTATUS_FS, 3 << 13
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
    .equ PROREG_F_I_ZERO, 0x0000400B
    .equ PROREG_F_I_FS3, 0x0080400B
    .equ PROREG_F_I_FS11, 0x8000400B
    .equ PROREG_F_I_FS3_FS11, 0x8080400B
    .equ PROREG_G_C, 0x0000308B
    .equ PROREG_F_C, 0x0000408B
    .equ CLR_G_ZERO, 0x0000200B
    .equ CLR_G_T3,   0x0080200B
    .equ CLR_G_T6,   0x0400200B
    .equ CLR_G_ALL,  0x07F0200B
    .equ CLR_F_ZERO, 0x0000600B
    .equ CLR_F_FT0,  0x0010600B
    .equ CLR_F_FT6,  0x0400600B
    .equ CLR_F_ALL,  0x07F0600B
    .equ CALLER_FS3, -1
    .equ CALLER_FS11, 0x8000000000000000
    .equ CONTROL_FS2, 0x6b3
    .equ LOCAL_FS3, -2
    .equ LEAVE, 0x0000500B
    .equ REUSE_ROUNDS, 192
    .equ GENERATION_ROUNDS, 32
    .equ GENERATION_SEED, 0x35
    .equ GENERATION_LOCAL, 0x2b
    .equ GENERATION_FP_SEED, 0x4008000000000031
    .equ GENERATION_FP_LOCAL, 0x80000000000000b4
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

    li      t0, MSTATUS_FS
    csrs    mstatus, t0
    li      t0, CALLER_FS3
    fmv.d.x fs3, t0
    li      t0, CALLER_FS11
    fmv.d.x fs11, t0
    li      t0, CONTROL_FS2
    fmv.d.x fs2, t0

    la      s0, cases
    li      s9, 1
    li      s7, CALLER_S7
start_case:
    ld      t0, 0(s0)               /* Probe entry PC. */
    ld      s2, 8(s0)               /* Expected mstatus[14:11] (FS and MPP). */
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
    li      t0, MSTATUS_MPP | MSTATUS_FS
    csrc    mstatus, t0
    slli    t0, s2, 11
    csrs    mstatus, t0
    mret

    /* Paired G and F candidates have opposite, nonzero caller values. */
    .macro CHECK_CSR_VIEW x31_expected, x12_expected
    bne     t6, \x31_expected, .Lcsr_mask_fail
    bne     a2, \x12_expected, .Lcsr_mask_fail
    fmv.x.d t3, ft0
    neg     t2, \x31_expected
    bne     t3, t2, .Lcsr_mask_fail
    fmv.x.d t3, ft11
    neg     t2, \x12_expected
    bne     t3, t2, .Lcsr_mask_fail
    .endm

    .macro CALL_WITH_UNWRITTEN_T6 seed, protect
    .if \protect
    li      t0, 1 << 31              /* PROREG.G.C selects x31 (t6). */
    csrw    CSR_DASICS_PROREG_MASK, t0
    .endif
    li      t6, \seed
    beqz    t6, .Lclr_fail
    li      a0, -1                   /* B must replace this with its sample. */
    la      t0, sample_t6
    .word   CLR_G_T6
    .if \protect
    .word   PROREG_G_C
    .endif
    .insn   i 0x0b, 1, ra, t0, 0     /* DASICSCALL.JR */
    .if \protect
    .word   LEAVE
    .endif
    bnez    a0, .Lclr_fail
    bnez    t6, .Lclr_fail
    j       csr_masks_break
    .endm

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
    .word   PROREG_F_I_FS3_FS11
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

    /* Each iteration ends with both caller mappings saved and local values
     * visible in s3 (x19) and fs3 (f19).
     */
generation_caller:
    fmv.x.d a2, fs3                 /* Preserve the value for later probes. */
    li      s3, GENERATION_SEED
    li      t4, GENERATION_FP_SEED
    fmv.d.x fs3, t4
    li      t5, GENERATION_FP_LOCAL
    .word   PROREG_G_I_S3
    .word   PROREG_F_I_FS3
    li      s3, GENERATION_LOCAL
    fmv.d.x fs3, t5
    addi    t4, t4, 1              /* Next caller's 64-bit FP pattern. */
    li      t1, GENERATION_ROUNDS
generation_leave:
    .word   LEAVE
generation_write:
    addi    s3, s3, 1
generation_proreg:
    .word   PROREG_G_I_S3
generation_fp_write:
    fmv.d.x fs3, t4
generation_fp_proreg:
    .word   PROREG_F_I_FS3
    addi    s3, s3, GENERATION_LOCAL
    fmv.d.x fs3, t5
    addi    t4, t4, 1
    addi    t1, t1, -1
generation_branch:
    bnez    t1, generation_leave
generation_exit:
    mv      t2, s3
generation_fp_read_local:
    fmv.x.d a1, fs3
generation_final_leave:
    .word   LEAVE
    li      t0, GENERATION_LOCAL
    bne     t2, t0, .Lgeneration_fail
    li      t0, GENERATION_SEED + GENERATION_ROUNDS
    bne     s3, t0, .Lgeneration_fail
    bne     a1, t5, .Lgeneration_fail
generation_fp_read_caller:
    fmv.x.d a1, fs3
    li      t0, GENERATION_FP_SEED + GENERATION_ROUNDS
    bne     a1, t0, .Lgeneration_fail
    fmv.d.x fs3, a2
generation_break:
    ebreak
.Lgeneration_fail:
    ebreak

occupied_caller:
    li      s3, OCCUPIED_S3
    li      s11, DISJOINT_S11
    .word   PROREG_G_I_S3
    /* An empty FP request may follow an integer protection. */
    .word   PROREG_F_I_ZERO
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

    /* The same FP instruction is reached in either trust domain. */
    .if \trusted_cases
fp_mixed:
    .word   PROREG_G_I_S3
fp_trusted:
    .else
fp_untrusted:
    .endif
    .word   PROREG_F_I_FS3
    addi    a5, zero, 1             /* Retires only when access is allowed. */
    .if \trusted_cases
fp_trusted_break:
    .endif
    ebreak
    .if \trusted_cases
fp_occupied_zero:
    .word   PROREG_F_I_ZERO
fp_occupied_disjoint:
    .word   PROREG_F_I_FS11
    addi    a5, zero, 1
    ebreak

    /* Recover the active G/F call with FS=Off, then reuse the FP bank. */
fp_leave_off:
    li      s3, 0x2b
    .word   LEAVE
    mv      a3, s3
    .word   PROREG_G_I_ZERO
    .word   PROREG_F_I_FS3
    .word   LEAVE                   /* Only the FP bank is occupied. */
    .word   PROREG_F_I_ZERO
fp_leave_off_break:
    ebreak

csr_occupied:
    csrw    CSR_DASICS_PROREG_MASK, zero
csr_occupied_g:
    .word   PROREG_G_C
csr_occupied_f:
    .word   PROREG_F_C

csr_masks:
    /* Select x31/f0, then x12/f31 at the same two instruction PCs. */
    li      t0, 1 << 31
    li      t1, 1 << 32
    li      a0, 0                   /* Expected view of x31 on entry. */
    li      a1, 0x731               /* Expected view of x12 on entry. */
.Lcsr_mask_round:
    li      t6, 0x731
    mv      a2, t6
    neg     t2, t6
    fmv.d.x ft0, t2
    fmv.d.x ft11, t2
    csrw    CSR_DASICS_PROREG_MASK, t0
    .word   PROREG_G_C
    csrw    CSR_DASICS_PROREG_MASK, t1
    .word   PROREG_F_C
    CHECK_CSR_VIEW a0, a1
    /* LEAVE restores only the selected values over these four zero writes. */
    li      t6, 0
    li      a2, 0
    fmv.d.x ft0, zero
    fmv.d.x ft11, zero
    .word   LEAVE
    CHECK_CSR_VIEW a1, a0
    bnez    a0, csr_masks_break
    mv      a0, a1
    li      a1, 0
    li      t0, 1 << 12
    li      t1, 1 << 63
    j       .Lcsr_mask_round
csr_masks_break:
    /* Self-checking CSR probes use this breakpoint to report success. */
    ebreak
.Lcsr_mask_fail:
    ebreak

csr_shared_mask:
    /* One policy selects x31 and f0; x12 and f31 remain visible. */
    li      a0, 0x731
    li      a1, 0x412
    mv      t6, a0
    mv      a2, a1
    neg     t2, a0
    fmv.d.x ft0, t2
    neg     t2, a1
    fmv.d.x ft11, t2
    li      t0, (1 << 31) | (1 << 32)
    csrw    CSR_DASICS_PROREG_MASK, t0
    .word   PROREG_G_C
    .word   PROREG_F_C
    CHECK_CSR_VIEW zero, a1
    csrr    t1, CSR_DASICS_PROREG_MASK
    bne     t1, t0, .Lcsr_mask_fail
    li      t6, 1
    fmv.d.x ft0, t6
    /* Clearing B's local mappings must preserve A's saved values. */
    .word   CLR_G_T6
    .word   CLR_F_FT0
    CHECK_CSR_VIEW zero, a1
    .word   LEAVE
    CHECK_CSR_VIEW a0, a1
    csrr    t1, CSR_DASICS_PROREG_MASK
    bne     t1, t0, .Lcsr_mask_fail
    j       csr_masks_break

csr_fs_off_protect:
    /* While FS is off, a second FP request observes the live f0 slot. */
    li      t0, 1 << 32
    csrw    CSR_DASICS_PROREG_MASK, t0
    .word   PROREG_F_C
    .word   CLR_F_ZERO              /* Neither request depends on FS or slots. */
    .word   CLR_F_FT0
csr_fs_off_conflict:
    .word   PROREG_F_I_ZERO
csr_fs_off_leave:
    .word   LEAVE
    .word   PROREG_F_I_ZERO         /* Succeeds only with an empty FP bank. */
    j       csr_masks_break

clear_temporaries:
    li      a0, 0x257
    fmv.d.x ft7, a0                 /* Controls outside the two masks. */
    .irp i,0,1,2,3,4,5,6
    li      t\i, (0x41 + \i)
    fmv.d.x ft\i, t\i
    .endr
    .word   CLR_G_ALL
    .word   CLR_F_ALL
    .word   CLR_G_ALL
    .word   CLR_F_ALL
    addi    t0, t0, 7               /* Read zero and create local values. */
    fmv.x.d a1, ft0
    addi    a1, a1, 9
    fmv.d.x ft0, a1
    .word   CLR_G_ZERO
    .word   CLR_F_ZERO
    .word   LEAVE                   /* Standalone clears have no saved slots. */
    li      a1, 7
    bne     t0, a1, .Lclr_fail
    li      a1, 9
    fmv.x.d a2, ft0
    bne     a2, a1, .Lclr_fail
    .irp i,1,2,3,4,5,6
    bnez    t\i, .Lclr_fail
    fmv.x.d a1, ft\i
    bnez    a1, .Lclr_fail
    .endr
    li      a1, 0x257
    bne     a0, a1, .Lclr_fail
    fmv.x.d a2, ft7
    bne     a2, a1, .Lclr_fail
    j       csr_masks_break

clear_rollback:
    li      t0, (1 << 31) | (1 << 32)   /* Save t6 and ft0 with PROREG.C. */
    csrw    CSR_DASICS_PROREG_MASK, t0
    li      a0, 0x521               /* Physical bits hidden in A. */
    li      a1, 0x732               /* Values visible to B. */
    li      t3, 0x243
    li      a2, GENERATION_ROUNDS
    /* Keep the three wrong-path operations in one fetch block. */
    .balign 32
clr_rollback_clear:
    .word   CLR_G_T3
clr_rollback_write:
    fmv.d.x ft6, a0
clr_rollback_leave:
    .word   LEAVE
    mv      t6, a0
    fmv.d.x ft0, a0
    .word   CLR_G_T6
    .word   CLR_F_FT0
    .word   PROREG_G_C
    .word   PROREG_F_C
    mv      t6, a1
    fmv.d.x ft0, a1
    li      t3, 0x243
    .word   CLR_F_FT6
    addi    a2, a2, -1
clr_rollback_branch:
    bnez    a2, clr_rollback_clear
clr_rollback_exit:
    /* Undo the wrong-path G clear, F write and mixed LEAVE, in reverse. */
    li      t1, 0x243
    bne     t3, t1, .Lclr_fail
    fmv.x.d t1, ft6
    bnez    t1, .Lclr_fail
    bne     t6, a1, .Lclr_fail
    fmv.x.d t1, ft0
    bne     t1, a1, .Lclr_fail
    .word   LEAVE
    bnez    t6, .Lclr_fail
    fmv.x.d t1, ft0
    bnez    t1, .Lclr_fail
    j       csr_masks_break
.Lclr_fail:
    ebreak

clear_t6_call:
    CALL_WITH_UNWRITTEN_T6 0x431, 0
clear_protect_t6_call:
    CALL_WITH_UNWRITTEN_T6 0x632, 1
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
    fmv.x.d t1, fs3
    fmv.x.d t2, fs11
    or      t1, t1, t2
    bnez    t1, .Lsparse_fp_fail
    li      t0, LOCAL_FS3
    fmv.d.x fs3, t0                 /* fs11 stays on its hidden mapping. */
    fmv.x.d t1, fs3
    bne     t1, t0, .Lsparse_fp_fail
    ret
.Lsparse_fp_fail:
    ebreak

    /* Untrusted code samples the raw 64-bit register view. */
fp_read_write:
    fmv.x.d a3, fs3
    fmv.x.d a4, fs2
    li      t0, LOCAL_FS3
    fmv.d.x fs3, t0
    fmv.x.d a6, fs3
fp_read_write_break:
    ebreak

csr_untrusted_g:
    .word   PROREG_G_C
csr_untrusted_f:
    .word   PROREG_F_C
clr_untrusted_g:
    .word   CLR_G_ALL
clr_untrusted_f:
    .word   CLR_F_ALL

    /* Outside both trusted ranges, B reports t6 without writing it. */
    .balign 8
sample_t6:
    mv      a0, t6
    ret

    .balign 4
machine_trap:
    csrr    t0, mstatus
    srli    t0, t0, 11
    andi    t0, t0, 15
    bne     t0, s2, fail            /* Check source privilege and FS. */
    csrr    t0, mcause
    bne     t0, s4, fail
    csrr    t0, mepc
    bne     t0, s5, fail
    la      t1, sparse_break
    beq     t0, t1, check_sparse
    la      t1, reuse_break
    beq     t0, t1, case_passed
    la      t1, csr_masks_break
    beq     t0, t1, case_passed
    la      t1, generation_break
    beq     t0, t1, case_passed
    la      t1, occupied_zero
    beq     t0, t1, resume_occupied
    la      t1, occupied_disjoint
    beq     t0, t1, resume_occupied
    la      t1, occupied_break
    beq     t0, t1, check_occupied
    la      t1, fp_read_write_break
    beq     t0, t1, check_fp_view
    la      t1, fp_leave_off_break
    beq     t0, t1, check_fp_leave_off
    li      t0, BREAKPOINT
    bne     s4, t0, check_illegal
    li      t0, 1
    bne     a5, t0, fail
    li      t0, PROREG_F_I_FS3
    beq     s8, t0, case_passed
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
check_fp_view:
    bnez    a3, fail
    li      t0, CONTROL_FS2
    bne     a4, t0, fail
    li      t0, LOCAL_FS3
    bne     a6, t0, fail
    j       case_passed
check_fp_leave_off:
    li      t0, CALLER_S3
    bne     a3, t0, fail
    /* The handler has checked FS=Off; enable FP only to inspect A's bits. */
    li      t0, MSTATUS_FS
    csrs    mstatus, t0
    fmv.x.d t1, fs3
    li      t0, CALLER_FS3
    bne     t1, t0, fail
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
    fmv.x.d t1, fs3
    CHECK_SPARSE t1, CALLER_FS3, after_leave, fs3
    fmv.x.d t1, fs11
    CHECK_SPARSE t1, CALLER_FS11, after_leave, fs11
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
    .dword sparse_caller, PRV_U | (MSTATUS_FS >> 11), BREAKPOINT, sparse_break
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
    .dword sparse_caller, PRV_S | (MSTATUS_FS >> 11), BREAKPOINT, sparse_break
    .dword sparse_call_failure, PROREG_G_I_S1_S3_S11
#else
#error "Select a U or S boot for the PROREG test"
#endif
    .dword reuse_caller, BOOT_PRIV, BREAKPOINT, reuse_break
    .dword reuse_failure, PROREG_G_I_S3
    .dword generation_caller, BOOT_PRIV | (MSTATUS_FS >> 11)
    .dword BREAKPOINT, generation_break
    .dword generation_failure, PROREG_G_I_S3
    .dword occupied_caller, BOOT_PRIV, ILLEGAL, occupied_zero
    .dword occupied_zero_failure, PROREG_G_I_ZERO
    .dword fp_untrusted, BOOT_PRIV, ILLEGAL, fp_untrusted
    .dword fp_untrusted_failure, PROREG_F_I_FS3
    .dword fp_mixed, BOOT_PRIV, BREAKPOINT, fp_trusted_break
    .dword fp_trusted_failure, PROREG_F_I_FS3
    .dword fp_occupied_zero, BOOT_PRIV, ILLEGAL, fp_occupied_zero
    .dword fp_occupied_failure, PROREG_F_I_ZERO
    .dword fp_occupied_disjoint, BOOT_PRIV, ILLEGAL, fp_occupied_disjoint
    .dword fp_occupied_failure, PROREG_F_I_FS11
    .dword csr_occupied, BOOT_PRIV, ILLEGAL, csr_occupied_g
    .dword csr_occupied_failure, PROREG_G_C
    .dword csr_occupied_f, BOOT_PRIV, ILLEGAL, csr_occupied_f
    .dword csr_occupied_failure, PROREG_F_C
    /* The preceding F requests ran with FS=Off; enable it for fmv.d.x/x.d. */
    .dword fp_read_write, BOOT_PRIV | (MSTATUS_FS >> 11)
    .dword BREAKPOINT, fp_read_write_break, fp_view_failure, 0
    .dword fp_leave_off, BOOT_PRIV, BREAKPOINT, fp_leave_off_break
    .dword fp_leave_failure, LEAVE
    .dword csr_masks, BOOT_PRIV | (MSTATUS_FS >> 11), BREAKPOINT
    .dword csr_masks_break, csr_masks_failure, 0
    .dword csr_shared_mask, BOOT_PRIV | (MSTATUS_FS >> 11), BREAKPOINT
    .dword csr_masks_break, csr_shared_mask_failure, 0
    /* The live FP slot carries across these two FS=Off cases. */
    .dword csr_fs_off_protect, BOOT_PRIV, ILLEGAL, csr_fs_off_conflict
    .dword csr_fs_off_failure, PROREG_F_I_ZERO
    .dword csr_fs_off_leave, BOOT_PRIV, BREAKPOINT, csr_masks_break
    .dword csr_fs_off_failure, 0
    .dword csr_untrusted_g, BOOT_PRIV, ILLEGAL, csr_untrusted_g
    .dword csr_untrusted_failure, PROREG_G_C
    .dword csr_untrusted_f, BOOT_PRIV, ILLEGAL, csr_untrusted_f
    .dword csr_untrusted_failure, PROREG_F_C
    .dword clear_temporaries, BOOT_PRIV | (MSTATUS_FS >> 11), BREAKPOINT
    .dword csr_masks_break, clr_view_failure, 0
    .dword clear_rollback, BOOT_PRIV | (MSTATUS_FS >> 11), BREAKPOINT
    .dword csr_masks_break, clr_rollback_failure, 0
    .dword clr_untrusted_g, BOOT_PRIV, ILLEGAL, clr_untrusted_g
    .dword clr_untrusted_failure, CLR_G_ALL
    .dword clr_untrusted_f, BOOT_PRIV, ILLEGAL, clr_untrusted_f
    .dword clr_untrusted_failure, CLR_F_ALL
    .dword clear_t6_call, BOOT_PRIV, BREAKPOINT, csr_masks_break
    .dword clear_t6_call_failure, 0
    .dword clear_protect_t6_call, BOOT_PRIV, BREAKPOINT, csr_masks_break
    .dword clear_protect_t6_call_failure, 0
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
generation_failure: .asciz "PROREG: wrong G/F mapping at loop exit\n"
occupied_zero_failure: .asciz "PROREG: occupied zero-mask rejection failed\n"
disjoint_failure: .asciz "PROREG: occupied disjoint-mask rejection failed\n"
occupied_restore_failure: .asciz "PROREG: state after conflicts failed\n"
fp_untrusted_failure: .asciz "PROREG.F.I: untrusted denial failed\n"
fp_trusted_failure: .asciz "PROREG.F.I: trusted access failed\n"
fp_occupied_failure: .asciz "PROREG.F.I: occupied FP slot conflict failed\n"
fp_view_failure: .asciz "PROREG.F.I: incorrect floating-point register view\n"
fp_leave_failure: .asciz "LEAVE: mixed restore or FP slot reuse failed\n"
csr_masks_failure: .asciz "PROREG.C: wrong register view after CSR write or LEAVE\n"
csr_shared_mask_failure: .asciz "PROREG.C: shared G/F policy or mapping mismatch\n"
csr_fs_off_failure: .asciz "PROREG.F.C: FP slot lifetime with FS off failed\n"
csr_untrusted_failure: .asciz "PROREG.C: untrusted denial failed\n"
csr_occupied_failure: .asciz "PROREG.C: occupied zero-mask denial failed\n"
clr_view_failure:    .asciz "CLR: incorrect register view\n"
clr_rollback_failure: .asciz "CLR: incorrect mapping or saved view after rollback\n"
clr_untrusted_failure: .asciz "CLR: untrusted denial failed\n"
clear_t6_call_failure: .asciz "CLR: unwritten t6 changed across call\n"
clear_protect_t6_call_failure: .asciz "CLR/PROREG: unwritten t6 changed across call\n"

    .section .data
    .balign 8
exit_args:
    .dword  0x20026, 0
