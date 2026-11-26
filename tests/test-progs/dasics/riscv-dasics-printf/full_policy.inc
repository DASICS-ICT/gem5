/* SPDX-License-Identifier: BSD-3-Clause */

/* clang-format off */
#define FULL_SAVED 0,1,2,3,4,5,6,7,8,9,10,11
#define FULL_TEMP  0,1,2,3,4,5,6

    .macro full_transfer ip, fp, base, int_offset, fp_offset
    .irp i,FULL_SAVED
    \ip     s\i,  (\int_offset + 8 * \i)(\base)
    \fp     fs\i, (\fp_offset + 8 * \i)(\base)
    .endr
    .endm

    .macro full_enter
    .globl roi_save_start, roi_save_end
    .globl gate_proreg_g, gate_proreg_f, gate_clr_g, gate_clr_f
roi_save_start:
    j       .Lfull_enter
    .word   0
#if !SOFTWARE_REGS
    .space  4 * (62 - 4)            /* Align the end of both entry policies. */
#endif
.Lfull_enter:
#if SOFTWARE_REGS
    full_transfer sd, fsd, ra, CTX_GPR_SAVE, CTX_FPR_SAVE
    .irp i,FULL_SAVED
    li      s\i, 0
    .endr
    .irp i,FULL_SAVED
    fmv.d.x fs\i, zero
    .endr
    .irp i,FULL_TEMP
    li      t\i, 0
    .endr
    .irp i,FULL_TEMP
    fmv.d.x ft\i, zero
    .endr
#else
gate_proreg_g:
    .word   0xfff0300b              /* PROREG.G.I s0-s11 */
gate_proreg_f:
    .word   0xfff0400b              /* PROREG.F.I fs0-fs11 */
gate_clr_g:
    .word   0x07f0200b              /* CLR.G.I t0-t6 */
gate_clr_f:
    .word   0x07f0600b              /* CLR.F.I ft0-ft6 */
#endif
roi_save_end:
#if SOFTWARE_REGS
    /* Corresponding hardware instruction PCs for the paired layout checker. */
    .set    gate_proreg_g, roi_save_end - 16
    .set    gate_proreg_f, roi_save_end - 12
    .set    gate_clr_g, roi_save_end - 8
    .set    gate_clr_f, roi_save_end - 4
#endif
    .endm

    .macro full_leave
    .globl roi_restore_start, roi_restore_end, gate_leave
roi_restore_start:
    j       .Lfull_leave
    .word   0
#if !SOFTWARE_REGS
    .space  4 * (24 - 1)            /* Align the end of both return policies. */
#endif
.Lfull_leave:
#if SOFTWARE_REGS
    full_transfer ld, fld, ra, CTX_GPR_SAVE, CTX_FPR_SAVE
#else
gate_leave:
    .word   0x0000500b              /* LEAVE */
#endif
roi_restore_end:
#if SOFTWARE_REGS
    .set    gate_leave, roi_restore_end - 4
#endif
    .endm

#if PRINTF_FULL_CHECK
    /* These probes use only a2/a3 as scratch, preserving printf's ABI and all
     * 38 selected registers until the callee has observed their entry values.
     */
    .macro full_seed
    .globl full_seed_start, full_seed_end
full_seed_start:
    .irp i,FULL_SAVED
    li      s\i, (0x141 + \i)
    li      a2, (0x241 + \i)
    fmv.d.x fs\i, a2
    .endr
    .irp i,FULL_TEMP
    li      t\i, (0x161 + \i)
    li      a2, (0x261 + \i)
    fmv.d.x ft\i, a2
    .endr
full_seed_end:
    .endm

    .macro full_check_entry
    .globl full_entry_start, full_entry_end
full_entry_start:
    .irp i,FULL_SAVED
    bnez    s\i, .Lbad_entry
    fmv.x.d a2, fs\i
    bnez    a2, .Lbad_entry
    .endr
    .irp i,FULL_TEMP
    bnez    t\i, .Lbad_entry
    fmv.x.d a2, ft\i
    bnez    a2, .Lbad_entry
    .endr
full_entry_end:
    .endm

    .macro full_clobber
    .globl full_clobber_start, full_clobber_end
full_clobber_start:
    .irp i,FULL_SAVED
    li      s\i, (0x341 + \i)
    li      a2, (0x441 + \i)
    fmv.d.x fs\i, a2
    .endr
full_clobber_end:
    .endm

    .macro full_check_restore
    .globl full_restore_check_start, full_restore_check_end
full_restore_check_start:
    .irp i,FULL_SAVED
    li      a2, (0x141 + \i)
    bne     s\i, a2, .Lbad_restore
    fmv.x.d a3, fs\i
    li      a2, (0x241 + \i)
    bne     a3, a2, .Lbad_restore
    .endr
full_restore_check_end:
    .endm
#endif
