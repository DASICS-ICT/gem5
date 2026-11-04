/* SPDX-License-Identifier: BSD-3-Clause */
#include "reg_protection.h"
#include <gem5/asm/generic/m5ops.h>

    .option push
    .option norelax
    .text

    /* a6 remains a valid context pointer across the private callees.
     * No protected register is consumed to address its own save slot. */
    .macro STORE_G base
    .set .Lg_offset, \base
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    sd \reg, .Lg_offset(a6)
    .set .Lg_offset, .Lg_offset + 8
    .endr
    .endm

    .macro LOAD_G base
    .set .Lg_offset, \base
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    ld \reg, .Lg_offset(a6)
    .set .Lg_offset, .Lg_offset + 8
    .endr
    .endm

    .macro STORE_F base
    .set .Lf_offset, \base
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fsd \reg, .Lf_offset(a6)
    .set .Lf_offset, .Lf_offset + 8
    .endr
    .endm

    .macro LOAD_F base
    .set .Lf_offset, \base
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fld \reg, .Lf_offset(a6)
    .set .Lf_offset, .Lf_offset + 8
    .endr
    .endm

    .macro CLEAR_G
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    li \reg, 0
    .endr
    .endm

    .macro CLEAR_F
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fmv.d.x \reg, zero
    .endr
    .endm

    /* Whole-register transfers ignore vl/vtype, but require the normal
     * call-boundary vstart=0 precondition. Each group spans 8*vlenb bytes. */
    .macro VECTOR_STORE pointer
    ld a0, \pointer(a6)
    ld a1, CTX_VECTOR_STRIDE(a6)
    vs8r.v v0, (a0)
    add a0, a0, a1
    vs8r.v v8, (a0)
    add a0, a0, a1
    vs8r.v v16, (a0)
    add a0, a0, a1
    vs8r.v v24, (a0)
    .endm

    .macro VECTOR_LOAD pointer
    ld a0, \pointer(a6)
    ld a1, CTX_VECTOR_STRIDE(a6)
    vl8re8.v v0, (a0)
    add a0, a0, a1
    vl8re8.v v8, (a0)
    add a0, a0, a1
    vl8re8.v v16, (a0)
    add a0, a0, a1
    vl8re8.v v24, (a0)
    .endm

    .macro VECTOR_CONTROL clear
    csrr a0, vl
    sd a0, CTX_VL(a6)
    csrr a0, vtype
    sd a0, CTX_VTYPE(a6)
    /* rd!=zero with rs1=zero requests VLMAX, rather than keep-vl. */
    vsetvli a0, zero, e8, m8, ta, ma
    .if \clear
    vmv.v.i v0, 0
    vmv.v.i v8, 0
    vmv.v.i v16, 0
    vmv.v.i v24, 0
    .endif
    ld a0, CTX_VL(a6)
    ld a1, CTX_VTYPE(a6)
    vsetvl zero, a0, a1
    .endm

    /* All variants share control/result traffic and the identical call/ret.
     * SR performs only data moves; SCR adds sanitization before the callee.
     * Vector configuration is restored before entry, so legitimate callee
     * changes to vl/vtype/vcsr survive return. */
    .macro GATE name, g=0, f=0, v=0, clear=0, vctl=0
    .balign 64
    .global reg_gate_\name
    .type reg_gate_\name, @function
reg_gate_\name:
    sd ra, CTX_RA(a6)
    sd sp, CTX_SP(a6)
    sd gp, CTX_GP(a6)
    sd tp, CTX_TP(a6)
    sd a0, CTX_ARG0(a6)
    sd a1, CTX_ARG1(a6)
    .if \g
    STORE_G CTX_GPR_SAVE
    .endif
    .if \f
    STORE_F CTX_FPR_SAVE
    .endif
    .if \v
    VECTOR_STORE CTX_VECTOR_SAVE
    .endif
    .if \vctl
    VECTOR_CONTROL 0
    .elseif \v && \clear
    VECTOR_CONTROL 1
    .endif
    .if \clear && \f
    CLEAR_F
    .endif
    .if \clear && \g
    CLEAR_G
    .endif
    ld a0, CTX_ARG0(a6)
    ld a1, CTX_ARG1(a6)
    mv ra, a7
    jalr ra, ra, 0
    sd a0, CTX_RESULT0(a6)
    sd a1, CTX_RESULT1(a6)
    .if \v
    VECTOR_LOAD CTX_VECTOR_SAVE
    .endif
    .if \f
    LOAD_F CTX_FPR_SAVE
    .endif
    .if \g
    LOAD_G CTX_GPR_SAVE
    .endif
    ld ra, CTX_RA(a6)
    ld sp, CTX_SP(a6)
    ld gp, CTX_GP(a6)
    ld tp, CTX_TP(a6)
    ld a0, CTX_RESULT0(a6)
    ld a1, CTX_RESULT1(a6)
    ret
    .size reg_gate_\name, .-reg_gate_\name
    .endm

    GATE B
    GATE G_SR, g=1
    GATE G_SCR, g=1, clear=1
    GATE F_SR, f=1
    GATE F_SCR, f=1, clear=1
    GATE GF_SR, g=1, f=1
    GATE GF_SCR, g=1, f=1, clear=1
    GATE V_SR, v=1
    GATE V_SCR, v=1, clear=1
    GATE GFV_SR, g=1, f=1, v=1
    GATE GFV_SCR, g=1, f=1, v=1, clear=1
    GATE VCTL, vctl=1

    .balign 64
    .global reg_batch
    .type reg_batch, @function
reg_batch:
    /* A 256-byte C ABI frame is never exposed as the callee's save area.
     * Gate sp is unchanged; vector data uses separately sized storage. */
    addi sp, sp, -256
    sd ra, 248(sp)
    .set .Labi_offset, 0
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    sd \reg, .Labi_offset(sp)
    .set .Labi_offset, .Labi_offset + 8
    .endr
    .irp reg,fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fsd \reg, .Labi_offset(sp)
    .set .Labi_offset, .Labi_offset + 8
    .endr
    mv a6, a0
    mv a5, a1
    mv a7, a2
    mv a4, a3
    sd sp, CTX_BATCH_SP(a6)
    sd gp, CTX_BATCH_GP(a6)
    sd tp, CTX_BATCH_TP(a6)
    csrw vstart, zero
    VECTOR_LOAD CTX_VECTOR_SEED
    vsetivli zero, 7, e32, m1, tu, mu
    csrwi vcsr, 0
    LOAD_G CTX_GPR_SEED
    LOAD_F CTX_FPR_SEED
    li a2, ARG2_VALUE
    li a3, ARG3_VALUE
    ld a0, CTX_MEASURE(a6)
    beqz a0, .Lbatch_loop
    li a0, 0
    li a1, 0
    /* Same encoding as util/m5/src/abi/riscv/m5op.S. */
    .long 0x0000007b | (M5OP_WORK_BEGIN << 25)
.Lbatch_loop:
    li a0, ARG0_VALUE
    li a1, ARG1_VALUE
    jalr ra, a5, 0
    addi a4, a4, -1
    bnez a4, .Lbatch_loop
    ld a0, CTX_MEASURE(a6)
    beqz a0, .Lbatch_capture
    li a0, 0
    li a1, 0
    .long 0x0000007b | (M5OP_WORK_END << 25)
.Lbatch_capture:
    sd sp, CTX_SP(a6)
    sd gp, CTX_GP(a6)
    sd tp, CTX_TP(a6)
    STORE_G CTX_GPR_AFTER
    STORE_F CTX_FPR_AFTER
    VECTOR_STORE CTX_VECTOR_AFTER
    csrr a0, vl
    sd a0, CTX_AFTER_VL(a6)
    csrr a0, vtype
    sd a0, CTX_AFTER_VTYPE(a6)
    csrr a0, vcsr
    sd a0, CTX_AFTER_VCSR(a6)
    csrr a0, vstart
    sd a0, CTX_AFTER_VSTART(a6)
    .set .Labi_offset, 0
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    ld \reg, .Labi_offset(sp)
    .set .Labi_offset, .Labi_offset + 8
    .endr
    .irp reg,fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fld \reg, .Labi_offset(sp)
    .set .Labi_offset, .Labi_offset + 8
    .endr
    ld ra, 248(sp)
    addi sp, sp, 256
    ret
    .size reg_batch, .-reg_batch

    .balign 64
    .global reg_callee_empty
    .type reg_callee_empty, @function
reg_callee_empty:
    ret
    .size reg_callee_empty, .-reg_callee_empty

    .balign 64
    .global reg_callee_compute
    .type reg_callee_compute, @function
reg_callee_compute:
    mv t0, a0
    /* Fixed dependency depth; no memory accesses or payload-dependent loop. */
    .rept 16
    add t0, t0, a1
    xori t0, t0, 123
    srli t0, t0, 1
    .endr
    mv a0, t0
    ret
    .size reg_callee_compute, .-reg_callee_compute

    .balign 64
    .global reg_callee_probe
    .type reg_callee_probe, @function
reg_callee_probe:
    /* Functional instrumentation is called only outside the timed region. */
    STORE_G CTX_GPR_SEEN
    STORE_F CTX_FPR_SEEN
    .set .Larg_offset, CTX_ARGS_SEEN
    .irp reg,a0,a1,a2,a3,a4,a5,a6,a7
    sd \reg, .Larg_offset(a6)
    .set .Larg_offset, .Larg_offset + 8
    .endr
    sd sp, CTX_SEEN_SP(a6)
    sd gp, CTX_SEEN_GP(a6)
    sd tp, CTX_SEEN_TP(a6)
    csrr a0, vl
    sd a0, CTX_SEEN_VL(a6)
    csrr a0, vtype
    sd a0, CTX_SEEN_VTYPE(a6)
    csrr a0, vcsr
    sd a0, CTX_SEEN_VCSR(a6)
    csrr a0, vstart
    sd a0, CTX_SEEN_VSTART(a6)
    VECTOR_STORE CTX_VECTOR_SEEN
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    li \reg, GPR_CLOBBER_VALUE
    .endr
    li a0, FPR_CLOBBER_VALUE
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fmv.d.x \reg, a0
    .endr
    vsetvli a0, zero, e8, m8, ta, ma
    vmv.v.i v0, -1
    vmv.v.i v8, -1
    vmv.v.i v16, -1
    vmv.v.i v24, -1
    /* These are legitimate callee changes, not caller state to roll back. */
    vsetivli zero, 3, e16, m2, ta, ma
    csrwi vcsr, 5
    li a0, RESULT0_VALUE
    li a1, RESULT1_VALUE
    li gp, 0
    li tp, 0
    li sp, 0
    ret
    .size reg_callee_probe, .-reg_callee_probe

    .global reg_vlenb
    .type reg_vlenb, @function
reg_vlenb:
    csrr a0, vlenb
    ret
    .size reg_vlenb, .-reg_vlenb

    .option pop
    .section .note.GNU-stack,"",@progbits
