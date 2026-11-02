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

    /* No runtime initializes gp or provides a dynamic linker. */
    .option norelax
    .option nopic
    .section .text.init
    .globl _start
_start:
    la      t0, trap_handler
    csrw    mtvec, t0

    /* Exit codes identify the first failed assertion; zero means success. */
    li      a2, 1
    csrr    t0, CSR_DASICS_MAIN_CALL_ENTRY
    bnez    t0, exit_test

    /* Include bit 63 and nonzero low bits to detect truncation or masking. */
    li      a2, 2
    li      t0, 0xFEDCBA9876543217
    csrw    CSR_DASICS_MAIN_CALL_ENTRY, t0
    csrr    t1, CSR_DASICS_MAIN_CALL_ENTRY
    bne     t1, t0, exit_test

    li      a2, 3
    li      t2, 0x0123456789ABCDE3
    csrrw   t1, CSR_DASICS_MAIN_CALL_ENTRY, t2
    bne     t1, t0, exit_test

    li      a2, 4
    csrr    t1, CSR_DASICS_MAIN_CALL_ENTRY
    bne     t1, t2, exit_test

    li      a2, 0
    j       exit_test

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
