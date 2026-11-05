/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef REG_PRESSURE_H
#define REG_PRESSURE_H

#include "reg_protection.h"

#define PRESSURE_ALLOCATED_BYTES 262144
#define PRESSURE_NODE_BYTES 64
#define PRESSURE_LOADS 4096
#define PRESSURE_ALIGNMENT 128

#ifndef __ASSEMBLER__
/* The integer kernel preserves a2-a7 and fa0/fa1. The batch uses a2 as the
 * carried head, a3 as K, a4 as remaining calls, a5 as gate, a6 as context,
 * and a7 as callee. fa0 holds the marked flag and fa1 the warm/ROI phase.
 * The callee receives head/K in a0/a1 and returns checksum/head in a0/a1.
 * fa0/fa1 are private control outside G19/F24. Timed calls are uninstrumented.
 */
void reg_pressure_batch(struct reg_context *context, reg_function gate,
                        const void *head, uint64_t loads_per_call,
                        uint64_t iterations, uint64_t warmup,
                        reg_function callee);
void reg_pressure_memory(void);
void reg_pressure_probe(void);
#endif
#endif
