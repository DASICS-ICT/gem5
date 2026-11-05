/* SPDX-License-Identifier: BSD-3-Clause */
#include "reg_pressure.h"
#include <gem5/asm/generic/m5ops.h>

    .option push
    .option norelax
    .text

    .macro G_STORE base
    .set .Lg_offset, \base
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    sd \reg, .Lg_offset(a6)
    .set .Lg_offset, .Lg_offset + 8
    .endr
    .endm

    .macro G_LOAD base
    .set .Lg_offset, \base
    .irp reg,t0,t1,t2,t3,t4,t5,t6,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    ld \reg, .Lg_offset(a6)
    .set .Lg_offset, .Lg_offset + 8
    .endr
    .endm

    .macro F_STORE base
    .set .Lf_offset, \base
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fsd \reg, .Lf_offset(a6)
    .set .Lf_offset, .Lf_offset + 8
    .endr
    .endm

    .macro F_LOAD base
    .set .Lf_offset, \base
    .irp reg,ft0,ft1,ft2,ft3,ft4,ft5,ft6,ft7,ft8,ft9,ft10,ft11,\
             fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fld \reg, .Lf_offset(a6)
    .set .Lf_offset, .Lf_offset + 8
    .endr
    .endm

    .balign 64
    .global reg_pressure_batch
    .type reg_pressure_batch, @function
reg_pressure_batch:
    addi sp, sp, -256
    sd ra, 248(sp)
    sd a4, 192(sp)
    .set .Labi_offset, 0
    .irp reg,s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11
    sd \reg, .Labi_offset(sp)
    .set .Labi_offset, .Labi_offset + 8
    .endr
    .irp reg,fs0,fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,fs11
    fsd \reg, .Labi_offset(sp)
    .set .Labi_offset, .Labi_offset + 8
    .endr
    mv a7, a6
    mv a6, a0
    mv a4, a5
    mv a5, a1
    ld a0, CTX_MEASURE(a6)
    fmv.d.x fa0, a0
    fmv.d.x fa1, zero
    G_LOAD CTX_GPR_SEED
    F_LOAD CTX_FPR_SEED
    beqz a4, .Lpressure_begin
    .global reg_pressure_loop
reg_pressure_loop:
    mv a0, a2
    mv a1, a3
    .global reg_pressure_gate_call
reg_pressure_gate_call:
    jalr ra, a5, 0
    .global reg_pressure_after_gate
reg_pressure_after_gate:
    mv a2, a1
    addi a4, a4, -1
    bnez a4, reg_pressure_loop
    fmv.x.d a0, fa1
    bnez a0, .Lpressure_end
.Lpressure_begin:
    /* The only stack read between warmup and ROI is outside the markers.
     * The head and live payload are carried directly into the same loop. */
    ld a4, 192(sp)
    li a0, 1
    fmv.d.x fa1, a0
    fmv.x.d a0, fa0
    beqz a0, reg_pressure_loop
    li a0, 0
    li a1, 0
    .global reg_pressure_work_begin
reg_pressure_work_begin:
    .long 0x0000007b | (M5OP_WORK_BEGIN << 25)
    j reg_pressure_loop
.Lpressure_end:
    /* No control-state memory access is added to the timed interval. */
    fmv.x.d a0, fa0
    beqz a0, .Lpressure_capture
    li a0, 0
    li a1, 0
    .global reg_pressure_work_end
reg_pressure_work_end:
    .long 0x0000007b | (M5OP_WORK_END << 25)
.Lpressure_capture:
    G_STORE CTX_GPR_AFTER
    F_STORE CTX_FPR_AFTER
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
    .size reg_pressure_batch, .-reg_pressure_batch

    .balign 64
    .global reg_pressure_memory
    .type reg_pressure_memory, @function
reg_pressure_memory:
    mv t0, a0
    mv t1, a1
    li t2, 0
    /* Exactly K serial loads, independent of the active ring's capacity.
     * Returning the address sum gives the caller an analytical oracle. */
    .global reg_pressure_chain_load
reg_pressure_chain_load:
    ld t0, 0(t0)
    add t2, t2, t0
    addi t1, t1, -1
    bnez t1, reg_pressure_chain_load
    mv a0, t2
    mv a1, t0
    ret
    .size reg_pressure_memory, .-reg_pressure_memory

    .balign 64
    .global reg_pressure_probe
    .type reg_pressure_probe, @function
reg_pressure_probe:
    /* This entry is used only by verification outside all ROI markers. */
    G_STORE CTX_GPR_SEEN
    F_STORE CTX_FPR_SEEN
    .set .Larg_offset, CTX_ARGS_SEEN
    .irp reg,a0,a1,a2,a3,a4,a5,a6,a7
    sd \reg, .Larg_offset(a6)
    .set .Larg_offset, .Larg_offset + 8
    .endr
    j reg_pressure_memory
    .size reg_pressure_probe, .-reg_pressure_probe

    .option pop
    .section .note.GNU-stack,"",@progbits
