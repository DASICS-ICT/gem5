/* SPDX-License-Identifier: BSD-3-Clause */
/* clang-format off */
#include "context.h"

#ifndef TEST_SCENARIO
#define TEST_SCENARIO 0
#endif
#if TEST_SCENARIO < 0 || TEST_SCENARIO > 4
#error Unsupported register-protection scenario
#endif

    .equ CSR_DASICS_S_MAIN_CFG, 0xBC0
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_LIB_CFG, 0x880
    .equ CSR_DASICS_LIB_BOUND_LO0, 0x890
    .equ CSR_DASICS_LIB_BOUND_HI0, 0x891
    .equ CSR_DASICS_LIB_BOUND_LO1, 0x892
    .equ CSR_DASICS_LIB_BOUND_HI1, 0x893
    .equ CSR_DASICS_LIB_BOUND_LO2, 0x894
    .equ CSR_DASICS_LIB_BOUND_HI2, 0x895
    .equ CSR_DASICS_JUMP_CFG, 0x8C8
    .equ CSR_DASICS_JUMP_BOUND_LO0, 0x8C0
    .equ CSR_DASICS_JUMP_BOUND_HI0, 0x8C1
    .equ CSR_DASICS_MAIN_CALL_ENTRY, 0x8B0
    .equ CSR_DASICS_RETURN_PC, 0x8B1
    .equ CSR_DASICS_ACTIVE_ZONE_RETURN_PC, 0x8B2
    .equ CSR_DASICS_FREASON, 0x8B3
    .equ CSR_DASICS_CONTEXT_BASE, 0x8B4
    .equ MAIN_CFG_U, 2
    .equ SATP_SV39, (8 << 60)
    .equ PTE_V, 1
    /* U/R/X or U/R/W, with A/D preset and no global mappings. */
    .equ PTE_USER_RX, 0xDB
    .equ PTE_USER_RW, 0xD7
    .equ MSTATUS_FS, (3 << 13)
    .equ ENTRY_STATUS_CLEAR, (1 << 3) | (1 << 7) | (3 << 11) \
                            | (3 << 13) | (1 << 17) | (1 << 18) \
                            | (1 << 19) | (1 << 39)
    .equ COMPLETION_TOKEN, 0x434F4E54
    /* Three data slots: input R, output RW, and private stack RW. */
    .equ LIB_ENABLED, 0xBBA
    .equ LIB_VALID_MASK, 0x888
    .equ LIB_REVOKED, LIB_ENABLED & ~LIB_VALID_MASK
    .equ ELEMENT_COUNT, 4
    .equ FP_SCALE, 0x4000000000000000
    .equ FP_CHECKSUM, 0x4034000000000000
    .equ GPR_SEED, 0x1020304050607000
    .equ FPR_SEED, 0x7FF8123400000000
    .equ GP_SEED, 0x123456789ABCDEF0
    .equ TP_SEED, 0xFEDCBA9876543210
    .equ A_STACK_VALUE, 0x1122334455667788
    .equ B_STACK_VALUE, 0x13579BDF2468ACE0
    .equ LOAD_DEST_VALUE, 0x12345678
    /* Probe observations belong to B's output, never to A's save frame. */
    .equ OBS_FPR, 256
    .equ OBS_FCSR, 512
    .equ OBS_STACK, 520
    .equ OUTPUT_DATA, 528

    .option norelax
    .option nopic
    .option norvc
    .section .text.init,"ax",@progbits
    .globl _start
_start:
    la      t0, machine_trap_handler
    csrw    mtvec, t0
    csrw    mie, zero
    csrw    mideleg, zero
    csrw    medeleg, zero
    csrw    satp, zero
    li      t0, ENTRY_STATUS_CLEAR
    csrc    mstatus, t0
    csrw    CSR_DASICS_S_MAIN_CFG, zero

    /* No C runtime initializes NOBITS storage, including the page tables. */
    la      t0, __bss_start
    la      t1, __bss_end
.Lclear_bss:
    sd      zero, 0(t0)
    addi    t0, t0, 8
    bltu    t0, t1, .Lclear_bss

    /* TOR covers the image and its page-table walks below 0x90000000. */
    li      t0, (0x90000000 >> 2)
    csrw    pmpaddr0, t0
    li      t0, 0x0F
    csrw    pmpcfg0, t0

    /* Identity VAs near 0x80000000 select VPN[2]=2 and VPN[1]=0. */
    la      t0, root_table
    la      t1, level1_table
    srli    t1, t1, 12
    slli    t1, t1, 10
    ori     t1, t1, PTE_V
    sd      t1, 16(t0)
    la      t0, level1_table
    la      t1, level0_table
    srli    t1, t1, 12
    slli    t1, t1, 10
    ori     t1, t1, PTE_V
    sd      t1, 0(t0)

    /* Only listed U pages get leaves. Machine and guard pages stay absent. */
    la      a0, user_pages
    la      a1, user_pages_end
    la      a2, level0_table
.Lmap_page:
    ld      t0, 0(a0)
    ld      t1, 8(a0)
    srli    t2, t0, 12
    andi    t3, t2, 0x1FF
    slli    t3, t3, 3
    add     t3, a2, t3
    slli    t2, t2, 10
    or      t2, t2, t1
    sd      t2, 0(t3)
    addi    a0, a0, 16
    bltu    a0, a1, .Lmap_page

    /* Trusted U still obeys CSR privilege bits; configure bounds in M. */
    la      t0, trusted_start
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    la      t1, trusted_end
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t1
    csrw    CSR_DASICS_LIB_CFG, zero
    /* B's internal branches stay in its code page; ReturnPC is separate. */
    la      t4, untrusted_start
    csrw    CSR_DASICS_JUMP_BOUND_LO0, t4
    la      t4, untrusted_end
    csrw    CSR_DASICS_JUMP_BOUND_HI0, t4
    li      t4, 1
    csrw    CSR_DASICS_JUMP_CFG, t4
    csrw    CSR_DASICS_MAIN_CALL_ENTRY, zero
    csrw    CSR_DASICS_RETURN_PC, zero
    csrw    CSR_DASICS_ACTIVE_ZONE_RETURN_PC, zero
    csrw    CSR_DASICS_FREASON, zero
    la      t2, context_frame
    csrw    CSR_DASICS_CONTEXT_BASE, t2
    li      t3, MAIN_CFG_U
    csrw    CSR_DASICS_S_MAIN_CFG, t3

    li      t6, 1
    csrr    t4, CSR_DASICS_S_MAIN_CFG
    bne     t4, t3, machine_fail
    csrr    t4, CSR_DASICS_U_MAIN_BOUND_LO
    bne     t4, t0, machine_fail
    csrr    t4, CSR_DASICS_U_MAIN_BOUND_HI
    bne     t4, t1, machine_fail
    csrr    t4, CSR_DASICS_CONTEXT_BASE
    bne     t4, t2, machine_fail

    /* ASID=0; initialization publishes all leaves before entering U mode. */
    la      t0, root_table
    srli    t0, t0, 12
    li      t1, SATP_SV39
    or      t0, t0, t1
    fence   rw, rw
    csrw    satp, t0
    sfence.vma zero, zero
    li      t6, 2
    csrr    t1, satp
    bne     t0, t1, machine_fail

    li      t0, MSTATUS_FS
    csrs    mstatus, t0
    csrw    fcsr, zero
#if VECTOR_ABI
    li      t0, (3 << 9)
    csrs    mstatus, t0
    csrwi   vcsr, 0
    csrwi   vstart, 0
#endif
    la      sp, a_stack_top
    li      gp, 0
    li      tp, 0
    li      a3, 0
    la      t0, trusted_entry
    csrw    mepc, t0
    mret

    .section .text.machine,"ax",@progbits
    .balign 4
machine_trap_handler:
    /* Success is accepted only from the unique completed U-mode probe. */
    li      t6, 7
    csrr    t0, mcause
#if TEST_SCENARIO == 0
    li      t1, 8
#else
    li      t1, 24
#endif
    bne     t0, t1, machine_fail
    li      t6, 8
    csrr    t0, mstatus
    srli    t0, t0, 11
    andi    t0, t0, 3
    bnez    t0, machine_fail
    li      t6, 9
    csrr    t0, mepc
#if TEST_SCENARIO == 0
    la      t1, user_done
#else
    la      t1, fault_probe
#endif
    bne     t0, t1, machine_fail
    li      t6, 10
    csrr    t0, mtval
#if TEST_SCENARIO == 0
    bnez    t0, machine_fail
    li      t6, 11
    li      t0, COMPLETION_TOKEN
    bne     a3, t0, machine_fail
    mv      t6, a0
    bnez    t6, machine_fail
#else
    /* These pages are valid U mappings; the fault must come from DASICS. */
#if TEST_SCENARIO <= 2
    la      t1, context_frame
#else
    la      t1, a_stack_top
    addi    t1, t1, -8
#endif
    bne     t0, t1, machine_fail
    li      t6, 28
    csrr    t0, CSR_DASICS_FREASON
#if TEST_SCENARIO == 1 || TEST_SCENARIO == 3
    li      t1, 2
#else
    li      t1, 3
#endif
    bne     t0, t1, machine_fail
    li      t6, 29
    li      t0, LOAD_DEST_VALUE
    bne     a4, t0, machine_fail
    li      t6, 30
    la      t0, context_frame
    ld      t1, CTX_RA(t0)
    la      t2, after_gate
    bne     t1, t2, machine_fail
    la      t0, a_stack_top
    ld      t1, -8(t0)
    li      t2, A_STACK_VALUE
    bne     t1, t2, machine_fail
    li      t6, 31
    la      t0, output_buffer
    ld      t1, OBS_STACK(t0)
    li      t2, B_STACK_VALUE
    bne     t1, t2, machine_fail
    csrr    t0, CSR_DASICS_LIB_CFG
    li      t1, LIB_ENABLED
    bne     t0, t1, machine_fail
    csrr    t0, CSR_DASICS_RETURN_PC
    la      t1, return_gate
    bne     t0, t1, machine_fail
    csrr    t0, CSR_DASICS_CONTEXT_BASE
    la      t1, context_frame
    bne     t0, t1, machine_fail
    li      t6, 0
#endif

    li      a0, 0x04
    la      a1, success_message
    j       machine_report
machine_fail:
    /* The two-digit check number is also the process exit status. */
    la      t0, failure_number
    li      t1, 10
    divu    t2, t6, t1
    remu    t3, t6, t1
    addi    t2, t2, '0'
    addi    t3, t3, '0'
    sb      t2, 0(t0)
    sb      t3, 1(t0)
    li      a0, 0x04
    la      a1, failure_message
machine_report:
    fence   rw, rw
    .balign 16
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
    la      a1, exit_args
    sd      t6, 8(a1)
    fence   rw, rw
    li      a0, 0x20
    .balign 16
    slli    zero, zero, 0x1F
    ebreak
    srai    zero, zero, 7
.Lhalt:
    j       .Lhalt

    .section .rodata.machine,"a",@progbits
    .balign 8
user_pages:
    .dword trusted_start, PTE_USER_RX
    .dword untrusted_start, PTE_USER_RX
    .dword context_frame, PTE_USER_RW
    .dword a_stack_bottom, PTE_USER_RW
    .dword b_stack_bottom, PTE_USER_RW
    .dword input_buffer, PTE_USER_RW
    .dword output_buffer, PTE_USER_RW
#if VECTOR_ABI
    .dword vector_save_page, PTE_USER_RW
#endif
user_pages_end:
success_message:
#if ROI_MEASUREMENT
    .asciz "[OK] DASICS register protection: roi\n"
#elif VECTOR_CHECK
    .asciz "[OK] DASICS register protection: vector ABI check\n"
#elif TEST_SCENARIO == 0
    .asciz "[OK] DASICS register protection: normal\n"
#else
    .asciz "[OK] DASICS register protection: expected fault\n"
#endif

    .section .data.machine,"aw",@progbits
    .balign 8
exit_args:
    .dword 0x20026, 0
failure_message:
    .ascii "[FAIL] DASICS register protection: check="
failure_number:
    .asciz "00\n"

    .section .dasics_context,"aw",@nobits
    .balign 64
    .globl context_frame, context_frame_end
context_frame:
    .space CTX_SIZE
context_frame_end:

#if VECTOR_ABI
    /* Separate 4 KiB private U page, excluded from all three LibBounds. */
    .section .bss.vector_save,"aw",@nobits
    .balign 4096
vector_save_page:
    .space 4096
#endif

    .section .note.GNU-stack,"",@progbits
                                  /* clang-format on */
