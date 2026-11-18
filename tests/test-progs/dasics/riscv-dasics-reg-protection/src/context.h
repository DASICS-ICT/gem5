/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef DASICS_REG_CONTEXT_H
#define DASICS_REG_CONTEXT_H

/* RV64 save slots contain raw register bits; fcsr occupies one 8-byte slot.
 * The frame belongs to trusted A and is never included in B's LibBounds.
 */
#define CTX_RA 0
#define CTX_SP 8
#define CTX_GP 16
#define CTX_TP 24
#define CTX_FCSR 32
#define CTX_GPR_SAVE 40
#define CTX_FPR_SAVE 136
#define CTX_PADDING 232
#define CTX_SIZE 256

/* Keep whole-register save strides and the complete e64 argument in sync
 * with the VLEN selected for this ELF and checked against vlenb at boot.
 */
#ifndef VECTOR_VLEN
#define VECTOR_VLEN 128
#endif
#if VECTOR_VLEN != 128 && VECTOR_VLEN != 256 && VECTOR_VLEN != 512 &&         \
    VECTOR_VLEN != 1024
#error Unsupported vector width
#endif
#define VEC_BYTES (VECTOR_VLEN / 8)
#define VEC_LANES (VECTOR_VLEN / 64)

/* The functional test uses the complete gate. ROI builds add one operation
 * at a time so adjacent variants differ only by the selected instructions.
 */
#define GATE_BOUNDARY 0
#define GATE_SAVE 1
#define GATE_RESTORE 2
#define GATE_SOFTWARE 3
#ifndef GATE_MODE
#define GATE_MODE GATE_SOFTWARE
#endif
#if GATE_MODE < GATE_BOUNDARY || GATE_MODE > GATE_SOFTWARE
#error Invalid gate mode
#endif

#endif
