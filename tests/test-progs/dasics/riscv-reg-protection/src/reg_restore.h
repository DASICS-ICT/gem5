/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef REG_RESTORE_H
#define REG_RESTORE_H

#include "reg_protection.h"

#define RESTORE_SOURCE_BYTES 512
#define RESTORE_ALIGNMENT 128

#ifndef __ASSEMBLER__
#include <stdint.h>

/* The common wrapper preserves the C ABI outside the measurement. During
 * the markers and target loads, a2 holds the source, a3 is 8*vlenb, a4 names
 * observation storage, and a5 selects marked execution. These registers are
 * outside G19/F24/V32. a0/a1 carry only m5 work/thread IDs inside the ROI.
 * G/F source offsets match the existing 128-byte-aligned save context.
 */
typedef void (*restore_function)(const void *source, void *observed,
                                 uint64_t vector_stride, uint64_t marked);
void reg_restore_B(const void *, void *, uint64_t, uint64_t);
void reg_restore_G(const void *, void *, uint64_t, uint64_t);
void reg_restore_F(const void *, void *, uint64_t, uint64_t);
void reg_restore_V(const void *, void *, uint64_t, uint64_t);
uint64_t reg_restore_vlenb(void);
#endif
#endif
