/*
 * Copyright (c) 2026 Jaeuk Lee
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met: redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer;
 * redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution;
 * neither the name of the copyright holders nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

    /* Use the numeric address without a custom assembler CSR name. */
    .equ CSR_DASICS_MAIN_CALL_ENTRY, 0x8B0
    .equ CSR_DASICS_RETURN_PC, 0x8B1
    .equ CSR_DASICS_ACTIVE_ZONE_RETURN_PC, 0x8B2
    .equ CSR_DASICS_FREASON, 0x8B3

    /* No runtime initializes gp or provides a dynamic linker. */
    .option norelax
    .option nopic
    .section .text.init
    .globl _start
_start:
    la      t0, trap_handler
    csrw    mtvec, t0

    /* Leaf tests return zero on success or a failure code in a0. */
    call    test_csr_initial_values
    bnez    a0, .Lfinish_tests
    call    test_main_call_entry
    bnez    a0, .Lfinish_tests
    call    test_return_pc
    bnez    a0, .Lfinish_tests
    call    test_active_zone_return_pc
    bnez    a0, .Lfinish_tests
    call    test_freason
    bnez    a0, .Lfinish_tests
    call    test_csr_independence

.Lfinish_tests:
    mv      a2, a0
    j       exit_test

test_csr_initial_values:
    /* Check cold state before any test writes a DASICS CSR. */
    li      a0, 1
    csrr    t0, CSR_DASICS_MAIN_CALL_ENTRY
    bnez    t0, .Linitial_values_done
    li      a0, 6
    csrr    t0, CSR_DASICS_RETURN_PC
    bnez    t0, .Linitial_values_done
    li      a0, 12
    csrr    t0, CSR_DASICS_ACTIVE_ZONE_RETURN_PC
    bnez    t0, .Linitial_values_done
    li      a0, 17
    csrr    t0, CSR_DASICS_FREASON
    bnez    t0, .Linitial_values_done
    li      a0, 0
.Linitial_values_done:
    ret

test_main_call_entry:
    /* Include bit 63 and nonzero low bits to detect truncation or masking. */
    li      a0, 2
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_MAIN_CALL_ENTRY, t0
    csrr    t1, CSR_DASICS_MAIN_CALL_ENTRY
    bne     t1, t0, .Lmain_call_entry_done

    li      a0, 3
    li      t2, 0x0123456789ABCDE3
    csrrw   t1, CSR_DASICS_MAIN_CALL_ENTRY, t2
    bne     t1, t0, .Lmain_call_entry_done

    li      a0, 4
    csrr    t1, CSR_DASICS_MAIN_CALL_ENTRY
    bne     t1, t2, .Lmain_call_entry_done
    li      a0, 0
.Lmain_call_entry_done:
    ret

test_return_pc:
    li      a0, 7
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_RETURN_PC, t0
    csrr    t1, CSR_DASICS_RETURN_PC
    bne     t1, t0, .Lreturn_pc_done

    li      a0, 9
    li      t2, 0x0123456789ABCDE3
    csrrw   t1, CSR_DASICS_RETURN_PC, t2
    bne     t1, t0, .Lreturn_pc_done

    li      a0, 10
    csrr    t1, CSR_DASICS_RETURN_PC
    bne     t1, t2, .Lreturn_pc_done
    li      a0, 0
.Lreturn_pc_done:
    ret

test_active_zone_return_pc:
    li      a0, 13
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_ACTIVE_ZONE_RETURN_PC, t0
    csrr    t1, CSR_DASICS_ACTIVE_ZONE_RETURN_PC
    bne     t1, t0, .Lactive_zone_return_pc_done

    li      a0, 14
    li      t2, 0x0123456789ABCDE3
    csrrw   t1, CSR_DASICS_ACTIVE_ZONE_RETURN_PC, t2
    bne     t1, t0, .Lactive_zone_return_pc_done

    li      a0, 15
    csrr    t1, CSR_DASICS_ACTIVE_ZONE_RETURN_PC
    bne     t1, t2, .Lactive_zone_return_pc_done
    li      a0, 0
.Lactive_zone_return_pc_done:
    ret

test_freason:
    /* All bits set must read back as the three-bit reason mask. */
    li      a0, 18
    li      t0, -1
    csrw    CSR_DASICS_FREASON, t0
    li      t2, 7
    csrr    t1, CSR_DASICS_FREASON
    bne     t1, t2, .Lfreason_done

    /* CSR operations return the old reason and mask upper operand bits. */
    li      a0, 19
    li      t0, -6
    csrrw   t1, CSR_DASICS_FREASON, t0
    bne     t1, t2, .Lfreason_done

    li      a0, 20
    li      t2, 2
    csrr    t1, CSR_DASICS_FREASON
    bne     t1, t2, .Lfreason_done

    li      a0, 21
    li      t0, -7
    csrrs   t1, CSR_DASICS_FREASON, t0
    bne     t1, t2, .Lfreason_done

    li      a0, 22
    li      t2, 3
    csrr    t1, CSR_DASICS_FREASON
    bne     t1, t2, .Lfreason_done

    li      a0, 23
    csrrc   t1, CSR_DASICS_FREASON, t0
    bne     t1, t2, .Lfreason_done

    li      a0, 24
    li      t2, 2
    csrr    t1, CSR_DASICS_FREASON
    bne     t1, t2, .Lfreason_done

    li      a0, 25
    csrw    CSR_DASICS_FREASON, zero
    csrr    t1, CSR_DASICS_FREASON
    bnez    t1, .Lfreason_done

    li      a0, 26
    li      t0, -8
    csrw    CSR_DASICS_FREASON, t0
    csrr    t1, CSR_DASICS_FREASON
    bnez    t1, .Lfreason_done
    li      a0, 0
.Lfreason_done:
    ret

test_csr_independence:
    /* Prepare distinct values without relying on earlier test results. */
    li      t0, 0x0123456789ABCDE3
    csrw    CSR_DASICS_MAIN_CALL_ENTRY, t0
    li      t1, 0xFEDCBA9876543217
    csrw    CSR_DASICS_RETURN_PC, t1
    li      t2, 0x89ABCDEF01234565
    csrw    CSR_DASICS_ACTIVE_ZONE_RETURN_PC, t2
    /* Distinct low bits detect aliasing with the masked FReason register. */
    li      t3, 2
    csrw    CSR_DASICS_FREASON, t3

    li      a0, 8
    csrr    t4, CSR_DASICS_MAIN_CALL_ENTRY
    bne     t4, t0, .Lindependence_done
    li      a0, 11
    csrr    t4, CSR_DASICS_RETURN_PC
    bne     t4, t1, .Lindependence_done
    li      a0, 16
    csrr    t4, CSR_DASICS_ACTIVE_ZONE_RETURN_PC
    bne     t4, t2, .Lindependence_done
    li      a0, 27
    csrr    t4, CSR_DASICS_FREASON
    bne     t4, t3, .Lindependence_done
    li      a0, 0
.Lindependence_done:
    ret

    /* Direct-mode mtvec requires four-byte alignment. */
    .balign 4
trap_handler:
    /* Keep the exception cause available for debugger inspection. */
    csrr    a3, mcause
    li      a2, 5

exit_test:
    la      a1, exit_args
    sd      a2, 8(a1)
    li      a0, 0x20

    /* Keep the three semihosting marker instructions within one page. */
    .balign 16
semihost_exit:
    .option push
    .option norvc
    slli    zero, zero, 0x1f
    ebreak
    srai    zero, zero, 7
    .option pop

halt:
    j       halt

    .section .data
    .balign 8
exit_args:
    .dword  0x20026
    .dword  0
