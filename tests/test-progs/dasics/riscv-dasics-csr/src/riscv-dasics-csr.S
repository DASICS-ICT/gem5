/*
 * Copyright (c) 2026 Jaeuk Lee
 * Copyright (c) 2026 zengsy99
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
    .equ CSR_DASICS_U_MAIN_CFG, 0x9E1
    .equ CSR_DASICS_U_MAIN_BOUND_LO, 0x9E2
    .equ CSR_DASICS_U_MAIN_BOUND_HI, 0x9E3
    .equ CSR_DASICS_S_MAIN_CFG, 0xBC0
    .equ CSR_DASICS_S_MAIN_BOUND_LO, 0xBC2
    .equ CSR_DASICS_S_MAIN_BOUND_HI, 0xBC3

    .equ CSR_DASICS_LIB_CFG       , 0x880
    .equ CSR_DASICS_LIB_BOUND_LO0 , 0x890
    .equ CSR_DASICS_LIB_BOUND_HI0 , 0x891
    .equ CSR_DASICS_LIB_BOUND_LO1 , 0x892
    .equ CSR_DASICS_LIB_BOUND_HI1 , 0x893
    .equ CSR_DASICS_LIB_BOUND_LO2 , 0x894
    .equ CSR_DASICS_LIB_BOUND_HI2 , 0x895
    .equ CSR_DASICS_LIB_BOUND_LO3 , 0x896
    .equ CSR_DASICS_LIB_BOUND_HI3 , 0x897
    .equ CSR_DASICS_LIB_BOUND_LO4 , 0x898
    .equ CSR_DASICS_LIB_BOUND_HI4 , 0x899
    .equ CSR_DASICS_LIB_BOUND_LO5 , 0x89A
    .equ CSR_DASICS_LIB_BOUND_HI5 , 0x89B
    .equ CSR_DASICS_LIB_BOUND_LO6 , 0x89C
    .equ CSR_DASICS_LIB_BOUND_HI6 , 0x89D
    .equ CSR_DASICS_LIB_BOUND_LO7 , 0x89E
    .equ CSR_DASICS_LIB_BOUND_HI7 , 0x89F
    .equ CSR_DASICS_LIB_BOUND_LO8 , 0x8A0
    .equ CSR_DASICS_LIB_BOUND_HI8 , 0x8A1
    .equ CSR_DASICS_LIB_BOUND_LO9 , 0x8A2
    .equ CSR_DASICS_LIB_BOUND_HI9 , 0x8A3
    .equ CSR_DASICS_LIB_BOUND_LO10, 0x8A4
    .equ CSR_DASICS_LIB_BOUND_HI10, 0x8A5
    .equ CSR_DASICS_LIB_BOUND_LO11, 0x8A6
    .equ CSR_DASICS_LIB_BOUND_HI11, 0x8A7
    .equ CSR_DASICS_LIB_BOUND_LO12, 0x8A8
    .equ CSR_DASICS_LIB_BOUND_HI12, 0x8A9
    .equ CSR_DASICS_LIB_BOUND_LO13, 0x8AA
    .equ CSR_DASICS_LIB_BOUND_HI13, 0x8AB
    .equ CSR_DASICS_LIB_BOUND_LO14, 0x8AC
    .equ CSR_DASICS_LIB_BOUND_HI14, 0x8AD
    .equ CSR_DASICS_LIB_BOUND_LO15, 0x8AE
    .equ CSR_DASICS_LIB_BOUND_HI15, 0x8AF

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
    call    test_u_main_bound_lo
    bnez    a0, .Lfinish_tests
    call    test_u_main_bound_hi
    bnez    a0, .Lfinish_tests
    call    test_s_main_bound_lo
    bnez    a0, .Lfinish_tests
    call    test_s_main_bound_hi
    bnez    a0, .Lfinish_tests
    call    test_u_main_cfg
    bnez    a0, .Lfinish_tests
    call    test_s_main_cfg
    bnez    a0, .Lfinish_tests
    call    test_lib_cfg
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo0
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi0
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo1
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi1
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo2
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi2
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo3
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi3
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo4
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi4
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo5
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi5
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo6
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi6
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo7
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi7
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo8
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi8
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo9
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi9
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo10
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi10
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo11
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi11
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo12
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi12
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo13
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi13
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo14
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi14
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_lo15
    bnez    a0, .Lfinish_tests
    call    test_lib_bound_hi15
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
    li      a0, 28
    csrr    t0, CSR_DASICS_U_MAIN_BOUND_LO
    bnez    t0, .Linitial_values_done
    li      a0, 29
    csrr    t0, CSR_DASICS_U_MAIN_BOUND_HI
    bnez    t0, .Linitial_values_done
    li      a0, 30
    csrr    t0, CSR_DASICS_S_MAIN_BOUND_LO
    bnez    t0, .Linitial_values_done
    li      a0, 31
    csrr    t0, CSR_DASICS_S_MAIN_BOUND_HI
    bnez    t0, .Linitial_values_done
    li      a0, 60
    csrr    t0, CSR_DASICS_U_MAIN_CFG
    bnez    t0, .Linitial_values_done
    li      a0, 61
    csrr    t0, CSR_DASICS_S_MAIN_CFG
    bnez    t0, .Linitial_values_done
    li      a0, 91
    csrr    t0, CSR_DASICS_LIB_CFG
    bnez    t0, .Linitial_values_done
    li      a0, 92
    csrr    t0, CSR_DASICS_LIB_BOUND_LO0
    bnez    t0, .Linitial_values_done
    li      a0, 93
    csrr    t0, CSR_DASICS_LIB_BOUND_HI0
    bnez    t0, .Linitial_values_done
    li      a0, 94
    csrr    t0, CSR_DASICS_LIB_BOUND_LO1
    bnez    t0, .Linitial_values_done
    li      a0, 95
    csrr    t0, CSR_DASICS_LIB_BOUND_HI1
    bnez    t0, .Linitial_values_done
    li      a0, 96
    csrr    t0, CSR_DASICS_LIB_BOUND_LO2
    bnez    t0, .Linitial_values_done
    li      a0, 97
    csrr    t0, CSR_DASICS_LIB_BOUND_HI2
    bnez    t0, .Linitial_values_done
    li      a0, 98
    csrr    t0, CSR_DASICS_LIB_BOUND_LO3
    bnez    t0, .Linitial_values_done
    li      a0, 99
    csrr    t0, CSR_DASICS_LIB_BOUND_HI3
    bnez    t0, .Linitial_values_done
    li      a0, 100
    csrr    t0, CSR_DASICS_LIB_BOUND_LO4
    bnez    t0, .Linitial_values_done
    li      a0, 101
    csrr    t0, CSR_DASICS_LIB_BOUND_HI4
    bnez    t0, .Linitial_values_done
    li      a0, 102
    csrr    t0, CSR_DASICS_LIB_BOUND_LO5
    bnez    t0, .Linitial_values_done
    li      a0, 103
    csrr    t0, CSR_DASICS_LIB_BOUND_HI5
    bnez    t0, .Linitial_values_done
    li      a0, 104
    csrr    t0, CSR_DASICS_LIB_BOUND_LO6
    bnez    t0, .Linitial_values_done
    li      a0, 105
    csrr    t0, CSR_DASICS_LIB_BOUND_HI6
    bnez    t0, .Linitial_values_done
    li      a0, 106
    csrr    t0, CSR_DASICS_LIB_BOUND_LO7
    bnez    t0, .Linitial_values_done
    li      a0, 107
    csrr    t0, CSR_DASICS_LIB_BOUND_HI7
    bnez    t0, .Linitial_values_done
    li      a0, 108
    csrr    t0, CSR_DASICS_LIB_BOUND_LO8
    bnez    t0, .Linitial_values_done
    li      a0, 109
    csrr    t0, CSR_DASICS_LIB_BOUND_HI8
    bnez    t0, .Linitial_values_done
    li      a0, 110
    csrr    t0, CSR_DASICS_LIB_BOUND_LO9
    bnez    t0, .Linitial_values_done
    li      a0, 111
    csrr    t0, CSR_DASICS_LIB_BOUND_HI9
    bnez    t0, .Linitial_values_done
    li      a0, 112
    csrr    t0, CSR_DASICS_LIB_BOUND_LO10
    bnez    t0, .Linitial_values_done
    li      a0, 113
    csrr    t0, CSR_DASICS_LIB_BOUND_HI10
    bnez    t0, .Linitial_values_done
    li      a0, 114
    csrr    t0, CSR_DASICS_LIB_BOUND_LO11
    bnez    t0, .Linitial_values_done
    li      a0, 115
    csrr    t0, CSR_DASICS_LIB_BOUND_HI11
    bnez    t0, .Linitial_values_done
    li      a0, 116
    csrr    t0, CSR_DASICS_LIB_BOUND_LO12
    bnez    t0, .Linitial_values_done
    li      a0, 117
    csrr    t0, CSR_DASICS_LIB_BOUND_HI12
    bnez    t0, .Linitial_values_done
    li      a0, 118
    csrr    t0, CSR_DASICS_LIB_BOUND_LO13
    bnez    t0, .Linitial_values_done
    li      a0, 119
    csrr    t0, CSR_DASICS_LIB_BOUND_HI13
    bnez    t0, .Linitial_values_done
    li      a0, 120
    csrr    t0, CSR_DASICS_LIB_BOUND_LO14
    bnez    t0, .Linitial_values_done
    li      a0, 121
    csrr    t0, CSR_DASICS_LIB_BOUND_HI14
    bnez    t0, .Linitial_values_done
    li      a0, 122
    csrr    t0, CSR_DASICS_LIB_BOUND_LO15
    bnez    t0, .Linitial_values_done
    li      a0, 123
    csrr    t0, CSR_DASICS_LIB_BOUND_HI15
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

    /* MainBound tests preserve high bits and discard low alignment bits. */
test_u_main_bound_lo:
    li      a0, 32
    li      t0, 0x1000
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_LO
    bne     t1, t0, .Lu_main_bound_lo_done

    li      a0, 33
    li      t0, 0x123F
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    li      t2, 0x1238
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_LO
    bne     t1, t2, .Lu_main_bound_lo_done

    li      a0, 34
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    li      t2, 0xFEDCBA9876543210
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_LO
    bne     t1, t2, .Lu_main_bound_lo_done

    li      a0, 35
    li      t0, 0x0123456789ABCDE3
    csrrw   t1, CSR_DASICS_U_MAIN_BOUND_LO, t0
    bne     t1, t2, .Lu_main_bound_lo_done

    li      a0, 36
    li      t2, 0x0123456789ABCDE0
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_LO
    bne     t1, t2, .Lu_main_bound_lo_done

    li      a0, 37
    li      t0, 7
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t0
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_LO
    bnez    t1, .Lu_main_bound_lo_done
    li      a0, 0
.Lu_main_bound_lo_done:
    ret

test_u_main_bound_hi:
    li      a0, 38
    li      t0, 0x1000
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t0
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_HI
    bne     t1, t0, .Lu_main_bound_hi_done

    li      a0, 39
    li      t0, 0x123F
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t0
    li      t2, 0x1238
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_HI
    bne     t1, t2, .Lu_main_bound_hi_done

    li      a0, 40
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t0
    li      t2, 0xFEDCBA9876543210
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_HI
    bne     t1, t2, .Lu_main_bound_hi_done

    li      a0, 41
    li      t0, 0x0123456789ABCDE3
    csrrw   t1, CSR_DASICS_U_MAIN_BOUND_HI, t0
    bne     t1, t2, .Lu_main_bound_hi_done

    li      a0, 42
    li      t2, 0x0123456789ABCDE0
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_HI
    bne     t1, t2, .Lu_main_bound_hi_done

    li      a0, 43
    li      t0, 7
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t0
    csrr    t1, CSR_DASICS_U_MAIN_BOUND_HI
    bnez    t1, .Lu_main_bound_hi_done
    li      a0, 0
.Lu_main_bound_hi_done:
    ret

test_s_main_bound_lo:
    li      a0, 44
    li      t0, 0x1000
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_LO
    bne     t1, t0, .Ls_main_bound_lo_done

    li      a0, 45
    li      t0, 0x123F
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    li      t2, 0x1238
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_LO
    bne     t1, t2, .Ls_main_bound_lo_done

    li      a0, 46
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    li      t2, 0xFEDCBA9876543210
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_LO
    bne     t1, t2, .Ls_main_bound_lo_done

    li      a0, 47
    li      t0, 0x0123456789ABCDE3
    csrrw   t1, CSR_DASICS_S_MAIN_BOUND_LO, t0
    bne     t1, t2, .Ls_main_bound_lo_done

    li      a0, 48
    li      t2, 0x0123456789ABCDE0
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_LO
    bne     t1, t2, .Ls_main_bound_lo_done

    li      a0, 49
    li      t0, 7
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t0
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_LO
    bnez    t1, .Ls_main_bound_lo_done
    li      a0, 0
.Ls_main_bound_lo_done:
    ret

test_s_main_bound_hi:
    li      a0, 50
    li      t0, 0x1000
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_HI
    bne     t1, t0, .Ls_main_bound_hi_done

    li      a0, 51
    li      t0, 0x123F
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    li      t2, 0x1238
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_HI
    bne     t1, t2, .Ls_main_bound_hi_done

    li      a0, 52
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    li      t2, 0xFEDCBA9876543210
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_HI
    bne     t1, t2, .Ls_main_bound_hi_done

    li      a0, 53
    li      t0, 0x0123456789ABCDE3
    csrrw   t1, CSR_DASICS_S_MAIN_BOUND_HI, t0
    bne     t1, t2, .Ls_main_bound_hi_done

    li      a0, 54
    li      t2, 0x0123456789ABCDE0
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_HI
    bne     t1, t2, .Ls_main_bound_hi_done

    li      a0, 55
    li      t0, 7
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t0
    csrr    t1, CSR_DASICS_S_MAIN_BOUND_HI
    bnez    t1, .Ls_main_bound_hi_done
    li      a0, 0
.Ls_main_bound_hi_done:
    ret

test_u_main_cfg:
    /* U writes must preserve S fields in the shared configuration state. */
    li      t0, 0x3FF
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      a0, 62
    li      t2, 0x3E
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done

    li      a0, 63
    csrw    CSR_DASICS_U_MAIN_CFG, zero
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bnez    t1, .Lu_main_cfg_done
    li      a0, 64
    li      t2, 0x3C1
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done

    li      a0, 65
    li      t0, -1
    csrw    CSR_DASICS_U_MAIN_CFG, t0
    li      t2, 0x3E
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done
    li      a0, 66
    li      t2, 0x3FF
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done

    /* A mixed S pattern tests preservation of both zero and one bits. */
    li      t0, 0x155
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      a0, 67
    li      t0, 0xAAAAAAAAAAAAAAAB
    li      t2, 0x14
    csrrw   t1, CSR_DASICS_U_MAIN_CFG, t0
    bne     t1, t2, .Lu_main_cfg_done
    li      a0, 68
    li      t2, 0x2A
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done
    li      a0, 69
    li      t2, 0x16B
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done

    li      a0, 70
    li      t0, -1
    li      t2, 0x2A
    csrrs   t1, CSR_DASICS_U_MAIN_CFG, t0
    bne     t1, t2, .Lu_main_cfg_done
    li      a0, 71
    li      t2, 0x3E
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done
    li      a0, 72
    li      t2, 0x17F
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done

    li      a0, 73
    li      t2, 0x3E
    csrrc   t1, CSR_DASICS_U_MAIN_CFG, t0
    bne     t1, t2, .Lu_main_cfg_done
    li      a0, 74
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bnez    t1, .Lu_main_cfg_done
    li      a0, 75
    li      t2, 0x141
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Lu_main_cfg_done
    li      a0, 0
.Lu_main_cfg_done:
    ret

test_s_main_cfg:
    li      t0, -1
    csrw    CSR_DASICS_S_MAIN_CFG, t0
    li      a0, 76
    li      t2, 0x3FF
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Ls_main_cfg_done
    li      a0, 77
    li      t2, 0x3E
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bne     t1, t2, .Ls_main_cfg_done

    li      a0, 78
    li      t0, 0xFEDCBA9876543217
    li      t2, 0x3FF
    csrrw   t1, CSR_DASICS_S_MAIN_CFG, t0
    bne     t1, t2, .Ls_main_cfg_done
    li      a0, 79
    li      t2, 0x217
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Ls_main_cfg_done
    li      a0, 80
    li      t2, 0x16
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bne     t1, t2, .Ls_main_cfg_done

    li      a0, 81
    li      t0, -1
    li      t2, 0x217
    csrrs   t1, CSR_DASICS_S_MAIN_CFG, t0
    bne     t1, t2, .Ls_main_cfg_done
    li      a0, 82
    li      t2, 0x3FF
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Ls_main_cfg_done
    li      a0, 83
    li      t2, 0x3E
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bne     t1, t2, .Ls_main_cfg_done

    li      a0, 84
    li      t0, -63
    li      t2, 0x3FF
    csrrc   t1, CSR_DASICS_S_MAIN_CFG, t0
    bne     t1, t2, .Ls_main_cfg_done
    li      a0, 85
    li      t2, 0x3E
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bne     t1, t2, .Ls_main_cfg_done
    li      a0, 86
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bne     t1, t2, .Ls_main_cfg_done

    li      a0, 87
    csrw    CSR_DASICS_S_MAIN_CFG, zero
    csrr    t1, CSR_DASICS_S_MAIN_CFG
    bnez    t1, .Ls_main_cfg_done
    li      a0, 88
    csrr    t1, CSR_DASICS_U_MAIN_CFG
    bnez    t1, .Ls_main_cfg_done
    li      a0, 0
.Ls_main_cfg_done:
    ret

test_lib_cfg:
    /* Complementary patterns exercise every bit, including stored U bits. */
    li      a0, 125
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_LIB_CFG, t0
    csrr    t1, CSR_DASICS_LIB_CFG
    bne     t1, t0, .Llib_cfg_done

    li      a0, 126
    not     t2, t0
    csrrw   t1, CSR_DASICS_LIB_CFG, t2
    bne     t1, t0, .Llib_cfg_done

    li      a0, 127
    csrr    t1, CSR_DASICS_LIB_CFG
    bne     t1, t2, .Llib_cfg_done

    li      a0, 128
    csrrs   t1, CSR_DASICS_LIB_CFG, t0
    bne     t1, t2, .Llib_cfg_done

    li      a0, 129
    li      t2, -1
    csrr    t1, CSR_DASICS_LIB_CFG
    bne     t1, t2, .Llib_cfg_done

    li      a0, 130
    csrrc   t1, CSR_DASICS_LIB_CFG, t0
    bne     t1, t2, .Llib_cfg_done

    li      a0, 131
    not     t2, t0
    csrr    t1, CSR_DASICS_LIB_CFG
    bne     t1, t2, .Llib_cfg_done

    li      a0, 132
    csrw    CSR_DASICS_LIB_CFG, zero
    csrr    t1, CSR_DASICS_LIB_CFG
    bnez    t1, .Llib_cfg_done

    li      a0, 133
    li      t0, -1
    csrw    CSR_DASICS_LIB_CFG, t0
    csrr    t1, CSR_DASICS_LIB_CFG
    bne     t1, t0, .Llib_cfg_done
    li      a0, 0
.Llib_cfg_done:
    ret

    /* Expand one leaf per CSR; CSR numbers must be assembly constants. */
    /* Each leaf shares one failure code across its read/write checks. */
    .macro DEFINE_LIB_BOUND_TEST name, csr, failure
\name:
    li      a0, \failure
    li      t0, 0xFEDCBA9876543217
    csrw    \csr, t0
    li      t2, 0xFEDCBA9876543210
    csrr    t1, \csr
    bne     t1, t2, .Llib_bound_done\@

    li      t0, 0x0123456789ABCDE3
    csrrw   t1, \csr, t0
    bne     t1, t2, .Llib_bound_done\@

    li      t2, 0x0123456789ABCDE0
    csrr    t1, \csr
    bne     t1, t2, .Llib_bound_done\@

    li      t0, 7
    csrw    \csr, t0
    csrr    t1, \csr
    bnez    t1, .Llib_bound_done\@
    li      a0, 0
.Llib_bound_done\@:
    ret
    .endm

    DEFINE_LIB_BOUND_TEST test_lib_bound_lo0 , CSR_DASICS_LIB_BOUND_LO0 , 134
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi0 , CSR_DASICS_LIB_BOUND_HI0 , 135
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo1 , CSR_DASICS_LIB_BOUND_LO1 , 136
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi1 , CSR_DASICS_LIB_BOUND_HI1 , 137
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo2 , CSR_DASICS_LIB_BOUND_LO2 , 138
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi2 , CSR_DASICS_LIB_BOUND_HI2 , 139
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo3 , CSR_DASICS_LIB_BOUND_LO3 , 140
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi3 , CSR_DASICS_LIB_BOUND_HI3 , 141
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo4 , CSR_DASICS_LIB_BOUND_LO4 , 142
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi4 , CSR_DASICS_LIB_BOUND_HI4 , 143
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo5 , CSR_DASICS_LIB_BOUND_LO5 , 144
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi5 , CSR_DASICS_LIB_BOUND_HI5 , 145
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo6 , CSR_DASICS_LIB_BOUND_LO6 , 146
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi6 , CSR_DASICS_LIB_BOUND_HI6 , 147
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo7 , CSR_DASICS_LIB_BOUND_LO7 , 148
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi7 , CSR_DASICS_LIB_BOUND_HI7 , 149
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo8 , CSR_DASICS_LIB_BOUND_LO8 , 150
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi8 , CSR_DASICS_LIB_BOUND_HI8 , 151
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo9 , CSR_DASICS_LIB_BOUND_LO9 , 152
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi9 , CSR_DASICS_LIB_BOUND_HI9 , 153
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo10, CSR_DASICS_LIB_BOUND_LO10, 154
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi10, CSR_DASICS_LIB_BOUND_HI10, 155
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo11, CSR_DASICS_LIB_BOUND_LO11, 156
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi11, CSR_DASICS_LIB_BOUND_HI11, 157
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo12, CSR_DASICS_LIB_BOUND_LO12, 158
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi12, CSR_DASICS_LIB_BOUND_HI12, 159
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo13, CSR_DASICS_LIB_BOUND_LO13, 160
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi13, CSR_DASICS_LIB_BOUND_HI13, 161
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo14, CSR_DASICS_LIB_BOUND_LO14, 162
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi14, CSR_DASICS_LIB_BOUND_HI14, 163
    DEFINE_LIB_BOUND_TEST test_lib_bound_lo15, CSR_DASICS_LIB_BOUND_LO15, 164
    DEFINE_LIB_BOUND_TEST test_lib_bound_hi15, CSR_DASICS_LIB_BOUND_HI15, 165

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
    li      t5, 0x1000
    csrw    CSR_DASICS_U_MAIN_BOUND_LO, t5
    li      t5, 0x2000
    csrw    CSR_DASICS_U_MAIN_BOUND_HI, t5
    li      t5, 0x3000
    csrw    CSR_DASICS_S_MAIN_BOUND_LO, t5
    li      t5, 0x4000
    csrw    CSR_DASICS_S_MAIN_BOUND_HI, t5
    /* MainCfg is one state with two views, separate from the other CSRs. */
    li      t5, 0x155
    csrw    CSR_DASICS_S_MAIN_CFG, t5
    li      t5, 0x2A
    csrw    CSR_DASICS_U_MAIN_CFG, t5

    /* Seed the full data bank before checking any stored value. */
    li      t5, 0x13579BDF2468ACE1
    csrw    CSR_DASICS_LIB_CFG, t5
    li      t5, 0x10000
    csrw    CSR_DASICS_LIB_BOUND_LO0, t5
    li      t5, 0x10080
    csrw    CSR_DASICS_LIB_BOUND_HI0, t5
    li      t5, 0x10100
    csrw    CSR_DASICS_LIB_BOUND_LO1, t5
    li      t5, 0x10180
    csrw    CSR_DASICS_LIB_BOUND_HI1, t5
    li      t5, 0x10200
    csrw    CSR_DASICS_LIB_BOUND_LO2, t5
    li      t5, 0x10280
    csrw    CSR_DASICS_LIB_BOUND_HI2, t5
    li      t5, 0x10300
    csrw    CSR_DASICS_LIB_BOUND_LO3, t5
    li      t5, 0x10380
    csrw    CSR_DASICS_LIB_BOUND_HI3, t5
    li      t5, 0x10400
    csrw    CSR_DASICS_LIB_BOUND_LO4, t5
    li      t5, 0x10480
    csrw    CSR_DASICS_LIB_BOUND_HI4, t5
    li      t5, 0x10500
    csrw    CSR_DASICS_LIB_BOUND_LO5, t5
    li      t5, 0x10580
    csrw    CSR_DASICS_LIB_BOUND_HI5, t5
    li      t5, 0x10600
    csrw    CSR_DASICS_LIB_BOUND_LO6, t5
    li      t5, 0x10680
    csrw    CSR_DASICS_LIB_BOUND_HI6, t5
    li      t5, 0x10700
    csrw    CSR_DASICS_LIB_BOUND_LO7, t5
    li      t5, 0x10780
    csrw    CSR_DASICS_LIB_BOUND_HI7, t5
    li      t5, 0x10800
    csrw    CSR_DASICS_LIB_BOUND_LO8, t5
    li      t5, 0x10880
    csrw    CSR_DASICS_LIB_BOUND_HI8, t5
    li      t5, 0x10900
    csrw    CSR_DASICS_LIB_BOUND_LO9, t5
    li      t5, 0x10980
    csrw    CSR_DASICS_LIB_BOUND_HI9, t5
    li      t5, 0x10A00
    csrw    CSR_DASICS_LIB_BOUND_LO10, t5
    li      t5, 0x10A80
    csrw    CSR_DASICS_LIB_BOUND_HI10, t5
    li      t5, 0x10B00
    csrw    CSR_DASICS_LIB_BOUND_LO11, t5
    li      t5, 0x10B80
    csrw    CSR_DASICS_LIB_BOUND_HI11, t5
    li      t5, 0x10C00
    csrw    CSR_DASICS_LIB_BOUND_LO12, t5
    li      t5, 0x10C80
    csrw    CSR_DASICS_LIB_BOUND_HI12, t5
    li      t5, 0x10D00
    csrw    CSR_DASICS_LIB_BOUND_LO13, t5
    li      t5, 0x10D80
    csrw    CSR_DASICS_LIB_BOUND_HI13, t5
    li      t5, 0x10E00
    csrw    CSR_DASICS_LIB_BOUND_LO14, t5
    li      t5, 0x10E80
    csrw    CSR_DASICS_LIB_BOUND_HI14, t5
    li      t5, 0x10F00
    csrw    CSR_DASICS_LIB_BOUND_LO15, t5
    li      t5, 0x10F80
    csrw    CSR_DASICS_LIB_BOUND_HI15, t5

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

    /* Reload bound expectations to keep the test free of stack storage. */
    li      a0, 56
    li      t5, 0x1000
    csrr    t4, CSR_DASICS_U_MAIN_BOUND_LO
    bne     t4, t5, .Lindependence_done
    li      a0, 57
    li      t5, 0x2000
    csrr    t4, CSR_DASICS_U_MAIN_BOUND_HI
    bne     t4, t5, .Lindependence_done
    li      a0, 58
    li      t5, 0x3000
    csrr    t4, CSR_DASICS_S_MAIN_BOUND_LO
    bne     t4, t5, .Lindependence_done
    li      a0, 59
    li      t5, 0x4000
    csrr    t4, CSR_DASICS_S_MAIN_BOUND_HI
    bne     t4, t5, .Lindependence_done
    li      a0, 89
    li      t5, 0x16B
    csrr    t4, CSR_DASICS_S_MAIN_CFG
    bne     t4, t5, .Lindependence_done
    li      a0, 90
    li      t5, 0x2A
    csrr    t4, CSR_DASICS_U_MAIN_CFG
    bne     t4, t5, .Lindependence_done
    li      a0, 166
    li      t5, 0x13579BDF2468ACE1
    csrr    t4, CSR_DASICS_LIB_CFG
    bne     t4, t5, .Lindependence_done
    li      a0, 167
    li      t5, 0x10000
    csrr    t4, CSR_DASICS_LIB_BOUND_LO0
    bne     t4, t5, .Lindependence_done
    li      a0, 168
    li      t5, 0x10080
    csrr    t4, CSR_DASICS_LIB_BOUND_HI0
    bne     t4, t5, .Lindependence_done
    li      a0, 169
    li      t5, 0x10100
    csrr    t4, CSR_DASICS_LIB_BOUND_LO1
    bne     t4, t5, .Lindependence_done
    li      a0, 170
    li      t5, 0x10180
    csrr    t4, CSR_DASICS_LIB_BOUND_HI1
    bne     t4, t5, .Lindependence_done
    li      a0, 171
    li      t5, 0x10200
    csrr    t4, CSR_DASICS_LIB_BOUND_LO2
    bne     t4, t5, .Lindependence_done
    li      a0, 172
    li      t5, 0x10280
    csrr    t4, CSR_DASICS_LIB_BOUND_HI2
    bne     t4, t5, .Lindependence_done
    li      a0, 173
    li      t5, 0x10300
    csrr    t4, CSR_DASICS_LIB_BOUND_LO3
    bne     t4, t5, .Lindependence_done
    li      a0, 174
    li      t5, 0x10380
    csrr    t4, CSR_DASICS_LIB_BOUND_HI3
    bne     t4, t5, .Lindependence_done
    li      a0, 175
    li      t5, 0x10400
    csrr    t4, CSR_DASICS_LIB_BOUND_LO4
    bne     t4, t5, .Lindependence_done
    li      a0, 176
    li      t5, 0x10480
    csrr    t4, CSR_DASICS_LIB_BOUND_HI4
    bne     t4, t5, .Lindependence_done
    li      a0, 177
    li      t5, 0x10500
    csrr    t4, CSR_DASICS_LIB_BOUND_LO5
    bne     t4, t5, .Lindependence_done
    li      a0, 178
    li      t5, 0x10580
    csrr    t4, CSR_DASICS_LIB_BOUND_HI5
    bne     t4, t5, .Lindependence_done
    li      a0, 179
    li      t5, 0x10600
    csrr    t4, CSR_DASICS_LIB_BOUND_LO6
    bne     t4, t5, .Lindependence_done
    li      a0, 180
    li      t5, 0x10680
    csrr    t4, CSR_DASICS_LIB_BOUND_HI6
    bne     t4, t5, .Lindependence_done
    li      a0, 181
    li      t5, 0x10700
    csrr    t4, CSR_DASICS_LIB_BOUND_LO7
    bne     t4, t5, .Lindependence_done
    li      a0, 182
    li      t5, 0x10780
    csrr    t4, CSR_DASICS_LIB_BOUND_HI7
    bne     t4, t5, .Lindependence_done
    li      a0, 183
    li      t5, 0x10800
    csrr    t4, CSR_DASICS_LIB_BOUND_LO8
    bne     t4, t5, .Lindependence_done
    li      a0, 184
    li      t5, 0x10880
    csrr    t4, CSR_DASICS_LIB_BOUND_HI8
    bne     t4, t5, .Lindependence_done
    li      a0, 185
    li      t5, 0x10900
    csrr    t4, CSR_DASICS_LIB_BOUND_LO9
    bne     t4, t5, .Lindependence_done
    li      a0, 186
    li      t5, 0x10980
    csrr    t4, CSR_DASICS_LIB_BOUND_HI9
    bne     t4, t5, .Lindependence_done
    li      a0, 187
    li      t5, 0x10A00
    csrr    t4, CSR_DASICS_LIB_BOUND_LO10
    bne     t4, t5, .Lindependence_done
    li      a0, 188
    li      t5, 0x10A80
    csrr    t4, CSR_DASICS_LIB_BOUND_HI10
    bne     t4, t5, .Lindependence_done
    li      a0, 189
    li      t5, 0x10B00
    csrr    t4, CSR_DASICS_LIB_BOUND_LO11
    bne     t4, t5, .Lindependence_done
    li      a0, 190
    li      t5, 0x10B80
    csrr    t4, CSR_DASICS_LIB_BOUND_HI11
    bne     t4, t5, .Lindependence_done
    li      a0, 191
    li      t5, 0x10C00
    csrr    t4, CSR_DASICS_LIB_BOUND_LO12
    bne     t4, t5, .Lindependence_done
    li      a0, 192
    li      t5, 0x10C80
    csrr    t4, CSR_DASICS_LIB_BOUND_HI12
    bne     t4, t5, .Lindependence_done
    li      a0, 193
    li      t5, 0x10D00
    csrr    t4, CSR_DASICS_LIB_BOUND_LO13
    bne     t4, t5, .Lindependence_done
    li      a0, 194
    li      t5, 0x10D80
    csrr    t4, CSR_DASICS_LIB_BOUND_HI13
    bne     t4, t5, .Lindependence_done
    li      a0, 195
    li      t5, 0x10E00
    csrr    t4, CSR_DASICS_LIB_BOUND_LO14
    bne     t4, t5, .Lindependence_done
    li      a0, 196
    li      t5, 0x10E80
    csrr    t4, CSR_DASICS_LIB_BOUND_HI14
    bne     t4, t5, .Lindependence_done
    li      a0, 197
    li      t5, 0x10F00
    csrr    t4, CSR_DASICS_LIB_BOUND_LO15
    bne     t4, t5, .Lindependence_done
    li      a0, 198
    li      t5, 0x10F80
    csrr    t4, CSR_DASICS_LIB_BOUND_HI15
    bne     t4, t5, .Lindependence_done
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
