/* SPDX-License-Identifier: BSD-3-Clause */
#include "../riscv-dasics-reg-protection/src/context.h"

    .equ context_base, 0x8b4
    .equ lib_cfg, 0x880
    .option norelax
    .option norvc

#if PROTECTED
    .macro grant_symbols slot, lower, upper
    lla     t1, \lower
    csrw    (0x890 + 2 * \slot), t1
    lla     t1, \upper
    csrw    (0x891 + 2 * \slot), t1
    .endm
#endif

    .section .text.printf_gate,"ax",@progbits
    .balign 8
    .globl run_printf
    .type run_printf,@function
run_printf:
    /* Keep the C caller's ABI state outside B's data windows. */
    addi    sp, sp, -32
    sd      ra, 0(sp)
    sd      s3, 8(sp)
    fsd     fs3, 16(sp)
    frcsr   t1
    sd      t1, 24(sp)
#if PROTECTED
    csrr    t0, context_base
#else
    lla     t0, __dasics_context_base
#endif
    sd      sp, CTX_SP(t0)
    sd      gp, CTX_GP(t0)
    sd      tp, CTX_TP(t0)
    li      s3, 0x531
    li      t1, 0x4008000000000053
    fmv.d.x fs3, t1
    li      t6, 0x76
    csrwi   fcsr, 0
#if PROTECTED
    grant_symbols 0, __dasics_b_ro_start, __dasics_b_ro_end
    grant_symbols 1, __dasics_b_got_start, __dasics_b_got_end
    grant_symbols 2, __dasics_b_data_start, __dasics_b_data_end
    grant_symbols 3, __dasics_stack_bottom, __dasics_stack_top
    grant_symbols 4, __dasics_b_ptr_start, __dasics_b_ptr_end
    lla     t1, b_stdout
    ld      t2, 0(t1)
    csrw    0x89a, t2
    lla     t1, b_file_hi
    ld      t2, 0(t1)
    csrw    0x89b, t2
    /* RO: B constants, GOT entries, stdout pointer. RW: B data, stack, stream. */
    li      t1, 0xbabbaa
    csrw    lib_cfg, t1
#else
    sd      s3, CTX_GPR_SAVE(t0)
    fsd     fs3, CTX_FPR_SAVE(t0)
#endif
    lla     sp, __dasics_stack_top
    lla     tp, __dasics_b_tp        /* The fixed formatting path reads B's errno. */
    li      t1, 0
    li      t2, 0
    lla     t0, probe_b_entry
    .globl gate_proreg_g, gate_proreg_f, gate_clr_g
gate_proreg_g:
#if PROTECTED
    .word   0x0080300b              /* proreg.g.i s3 */
#else
    li      s3, 0
#endif
gate_proreg_f:
#if PROTECTED
    .word   0x0080400b              /* proreg.f.i fs3 */
#else
    fmv.d.x fs3, zero
#endif
gate_clr_g:
#if PROTECTED
    .word   0x0400200b              /* clr.g.i t6 */
#else
    li      t6, 0
#endif
    .globl gate_call, gate_return, gate_leave, a_result
gate_call:
#if PROTECTED
    .insn   i 0x0b, 1, ra, t0, 0    /* DASICSCALL.JR ra,t0,0 */
#else
    jalr    ra, 0(t0)
#endif
gate_return:
#if PROTECTED
    csrw    lib_cfg, zero
    csrr    t0, context_base
#else
    lla     t0, __dasics_context_base
#endif
gate_leave:
#if PROTECTED
    .word   0x0000500b              /* LEAVE consumes both saved slots. */
#else
    ld      s3, CTX_GPR_SAVE(t0)
    fld     fs3, CTX_FPR_SAVE(t0)
#endif
a_result:
    li      t1, 0x531
    bne     s3, t1, .Lbad_restore
    fmv.x.d t2, fs3
    li      t1, 0x4008000000000053
    beq     t1, t2, .Lrestore_abi
.Lbad_restore:
    li      a0, -2
.Lrestore_abi:
    ld      sp, CTX_SP(t0)
    ld      gp, CTX_GP(t0)
    ld      tp, CTX_TP(t0)
    ld      ra, 0(sp)
    ld      s3, 8(sp)
    fld     fs3, 16(sp)
    ld      t1, 24(sp)
    fscsr   t1
    addi    sp, sp, 32
    ret
    .size run_printf, .-run_printf

    .section .dasics.printf.entry,"ax",@progbits
    .balign 8
    .globl probe_b_entry, probe_b_clobber, probe_b_return
    .type probe_b_entry,@function
probe_b_entry:
    /* Sample the register view before libc can save or reuse any register. */
    fmv.x.d t0, fs3
    or      t0, t0, s3
    or      t0, t0, t6
    bnez    t0, .Lbad_entry
    addi    sp, sp, -16
    sd      ra, 8(sp)
    call    b_printf
probe_b_clobber:
    /* Force LEAVE to restore A even when libc follows the calling convention. */
    li      s3, 0x713
    fmv.d.x fs3, s3
    ld      ra, 8(sp)
    addi    sp, sp, 16
probe_b_return:
    ret
.Lbad_entry:
    li      a0, -1
    ret
    .size probe_b_entry, .-probe_b_entry

    .section .note.GNU-stack,"",@progbits
