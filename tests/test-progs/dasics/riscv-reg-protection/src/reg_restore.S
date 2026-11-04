/* SPDX-License-Identifier: BSD-3-Clause */
#include "reg_restore.h"
#include <gem5/asm/generic/m5ops.h>

    .option push
    .option norelax
    .text

    .macro SAVE_ABI
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
    mv a5, a3
    mv a4, a1
    mv a3, a2
    mv a2, a0
    .endm

    .macro RESTORE_ABI
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
    .endm

    .macro G_LOAD
    .set .Lg_offset, CTX_GPR_SAVE
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    ld \reg, .Lg_offset(a2)
    .set .Lg_offset, .Lg_offset + 8
    .endr
    .endm

    .macro G_OBSERVE
    .set .Lg_offset, 0
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    sd \reg, .Lg_offset(a4)
    .set .Lg_offset, .Lg_offset + 8
    .endr
    .endm

    .macro F_LOAD
    .set .Lf_offset, CTX_FPR_SAVE
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fld \reg, .Lf_offset(a2)
    .set .Lf_offset, .Lf_offset + 8
    .endr
    .endm

    .macro F_OBSERVE
    .set .Lf_offset, 0
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fsd \reg, .Lf_offset(a4)
    .set .Lf_offset, .Lf_offset + 8
    .endr
    .endm

    .macro V_LOAD
    vl8re8.v v0, (a2)
    add a2, a2, a3
    vl8re8.v v8, (a2)
    add a2, a2, a3
    vl8re8.v v16, (a2)
    add a2, a2, a3
    vl8re8.v v24, (a2)
    .endm

    .macro V_OBSERVE
    vs8r.v v0, (a4)
    add a4, a4, a3
    vs8r.v v8, (a4)
    add a4, a4, a3
    vs8r.v v16, (a4)
    add a4, a4, a3
    vs8r.v v24, (a4)
    .endm

    .macro SAMPLE name, g=0, f=0, v=0
    .balign 64
    .global reg_restore_\name
    .type reg_restore_\name, @function
reg_restore_\name:
    SAVE_ABI
    /* Real scalar reads warm every source line and its translation. The
     * host PREP handler subsequently drains stores and selects residency. */
    .if \g
    ld a0, 128(a2)
    ld a0, 192(a2)
    ld a0, 256(a2)
    .elseif \f
    ld a0, 288(a2)
    ld a0, 320(a2)
    ld a0, 384(a2)
    ld a0, 448(a2)
    .else
    mv a0, a2
    srli a1, a3, 4
.Ltouch_\name:
    ld a7, 0(a0)
    addi a0, a0, 64
    addi a1, a1, -1
    bnez a1, .Ltouch_\name
    .endif
    /* Poison after the instruction warmup too: an omitted target load
     * must not pass because an earlier invocation left the right value. */
    .if \g
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    li \reg, 0
    .endr
    .elseif \f
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fmv.d.x \reg, zero
    .endr
    .elseif \v
    csrw vstart, zero
    vsetvli a0, zero, e8, m8, ta, ma
    vmv.v.i v0, 0
    vmv.v.i v8, 0
    vmv.v.i v16, 0
    vmv.v.i v24, 0
    .endif
    beqz a5, reg_restore_loads_\name
    li a0, 1
    li a1, 0
    .global reg_restore_prepare_\name
reg_restore_prepare_\name:
    .long 0x0000007b | (M5OP_WORK_BEGIN << 25)
    /* Non-speculative SerializeAfter prevents drain from consuming START.
     * This reads no memory and is outside the measured interval. */
    .global reg_restore_guard_\name
reg_restore_guard_\name:
    rdcycle a0
    .global reg_restore_after_guard_\name
reg_restore_after_guard_\name:
    li a0, 2
    li a1, 0
    .global reg_restore_start_\name
reg_restore_start_\name:
    .long 0x0000007b | (M5OP_WORK_BEGIN << 25)
    .global reg_restore_loads_\name
reg_restore_loads_\name:
    .if \g
    G_LOAD
    .elseif \f
    F_LOAD
    .elseif \v
    V_LOAD
    .endif
    /* A matched branch lets warmup execute these exact load addresses
     * without emitting protocol events. B includes the same branch. */
    beqz a5, .Lobserve_\name
    /* Workbegin returns through a0; END needs fresh work/thread IDs. */
    li a0, 2
    li a1, 0
    .global reg_restore_end_\name
reg_restore_end_\name:
    .long 0x0000007b | (M5OP_WORK_END << 25)
.Lobserve_\name:
    .if \g
    G_OBSERVE
    .elseif \f
    F_OBSERVE
    .elseif \v
    V_OBSERVE
    .endif
    RESTORE_ABI
    .size reg_restore_\name, .-reg_restore_\name
    .endm

    SAMPLE B
    SAMPLE G, g=1
    SAMPLE F, f=1
    SAMPLE V, v=1

    .global reg_restore_vlenb
    .type reg_restore_vlenb, @function
reg_restore_vlenb:
    csrr a0, vlenb
    ret
    .size reg_restore_vlenb, .-reg_restore_vlenb

    .option pop
    .section .note.GNU-stack,"",@progbits
