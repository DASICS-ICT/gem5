/* SPDX-License-Identifier: BSD-3-Clause */
/* clang-format off */

/* The boundary reference retains control state but omits data protection. */
#if (USE_INT_PROREG || USE_FP_PROREG) && GATE_MODE != GATE_SOFTWARE
#error The PROREG gate requires the full register protection policy
#endif
#if VECTOR_ABI == 2
    .variant_cc protected_gate
#endif
protected_gate:
    csrr    t0, CSR_DASICS_CONTEXT_BASE
    sd      ra, CTX_RA(t0)
    sd      sp, CTX_SP(t0)
    sd      gp, CTX_GP(t0)
    sd      tp, CTX_TP(t0)
    csrr    t1, fcsr
    sd      t1, CTX_FCSR(t0)
#if GATE_MODE >= GATE_SAVE
#if !USE_INT_PROREG
    .set .Lsave_offset, CTX_GPR_SAVE
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    sd      \reg, .Lsave_offset(t0)
    .set .Lsave_offset, .Lsave_offset + 8
    .endr
#endif
#if !USE_FP_PROREG
    .set .Lsave_offset, CTX_FPR_SAVE
    .irp reg,fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fsd     \reg, .Lsave_offset(t0)
    .set .Lsave_offset, .Lsave_offset + 8
    .endr
#endif
#endif

    /* All slots are invalid while their address pairs are updated. */
    csrw    CSR_DASICS_LIB_BOUND_LO0, a0
    slli    t1, a2, 4
    add     t1, a0, t1
    csrw    CSR_DASICS_LIB_BOUND_HI0, t1
    csrw    CSR_DASICS_LIB_BOUND_LO1, a1
    la      t1, output_buffer_end
    csrw    CSR_DASICS_LIB_BOUND_HI1, t1
    la      t1, b_stack_bottom
    csrw    CSR_DASICS_LIB_BOUND_LO2, t1
    la      sp, b_stack_top
    csrw    CSR_DASICS_LIB_BOUND_HI2, sp
    li      t1, LIB_ENABLED
    csrw    CSR_DASICS_LIB_CFG, t1
    csrw    fcsr, zero
#if VECTOR_PROTECTED
#if VECTOR_ABI == 2
    /* t0 still holds ContextBase. The 15 whole registers fit in the
     * private page even at VLEN=1024 (1920 bytes).
     */
    lui     t1, %hi(vector_page_offset)
    add     t1, t0, t1
    vs8r.v  v24, (t1)
    addi    t1, t1, (8 * VEC_BYTES)
    vs4r.v  v4, (t1)
    addi    t1, t1, (4 * VEC_BYTES)
    vs2r.v  v2, (t1)
    addi    t1, t1, (2 * VEC_BYTES)
    vs1r.v  v1, (t1)
#endif
    /* Cover every bit even if A entered with a short active length. */
    vsetvli t1, zero, e8, m8, ta, ma
    vmv.v.i v0, 0
#if VECTOR_ABI == 1
    vmv.v.i v8, 0
#endif
    vmv.v.i v16, 0
    vmv.v.i v24, 0
    vsetivli zero, VEC_LANES, e64, m1, tu, mu
#if VECTOR_ABI == 2
    /* v8 is an authorized argument. Clear v9-v15 at LMUL=1. */
    .irp n,9,10,11,12,13,14,15
    vmv.v.i v\n, 0
    .endr
#endif
#endif
    li      gp, 0
    li      tp, 0
#if GATE_MODE == GATE_SOFTWARE
#if USE_INT_PROREG
    .irp reg,t0,t1,t2,a3,a4,a5,a6,a7,t3,t4,t5,t6
#else
    .irp reg,t0,t1,t2,s0,s1,a3,a4,a5,a6,a7,\
             s2,s3,s4,s5,s6,s7,s8,s9,s10,s11,t3,t4,t5,t6
#endif
    li      \reg, 0
    .endr
#if USE_FP_PROREG
    /* The gate clears ft0-ft11 and fa1-fa7; fa0 carries the argument. */
    .irp num,0,1,2,3,4,5,6,7,11,12,13,14,15,16,17,28,29,30,31
#else
    .irp num,0,1,2,3,4,5,6,7,8,9,11,12,13,14,15,\
             16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
#endif
    fmv.d.x f\num, zero
    .endr
#if USE_INT_PROREG
    .word   0xfff0300b              /* PROREG.G.I 0xfff: protect s0-s11. */
#endif
#if USE_FP_PROREG
    .word   0xfff0400b              /* PROREG.F.I 0xfff: protect fs0-fs11. */
#endif
#endif
    .globl gate_call, return_gate
gate_call:
    .word   dasics_call_encoding
return_gate:
    /* No load or stack access may precede recovery of the trusted base. */
    csrr    t0, CSR_DASICS_CONTEXT_BASE
    li      t1, LIB_VALID_MASK
    csrc    CSR_DASICS_LIB_CFG, t1
#if VECTOR_ABI
    /* Both arms normalize the return boundary before any vector restore. */
    csrwi   vstart, 0
#endif
#if VECTOR_ABI == 2 && VECTOR_PROTECTED
    lui     t1, %hi(vector_page_offset)
    add     t1, t0, t1
    vl8re8.v v24, (t1)
    addi    t1, t1, (8 * VEC_BYTES)
    vl4re8.v v4, (t1)
    addi    t1, t1, (4 * VEC_BYTES)
    vl2re8.v v2, (t1)
    addi    t1, t1, (2 * VEC_BYTES)
    vl1re8.v v1, (t1)
#endif
#if GATE_MODE >= GATE_RESTORE
#if USE_INT_PROREG || USE_FP_PROREG
    .word   0x0000500b              /* One LEAVE restores both active banks. */
#endif
#if !USE_INT_PROREG
    .set .Lrestore_offset, CTX_GPR_SAVE
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    ld      \reg, .Lrestore_offset(t0)
    .set .Lrestore_offset, .Lrestore_offset + 8
    .endr
#endif
#if !USE_FP_PROREG
    .set .Lrestore_offset, CTX_FPR_SAVE
    .irp reg,fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fld     \reg, .Lrestore_offset(t0)
    .set .Lrestore_offset, .Lrestore_offset + 8
    .endr
#endif
#endif
    ld      t1, CTX_FCSR(t0)
    csrw    fcsr, t1
    ld      gp, CTX_GP(t0)
    ld      tp, CTX_TP(t0)
    ld      sp, CTX_SP(t0)
    ld      ra, CTX_RA(t0)
    ret
    /* clang-format on */
