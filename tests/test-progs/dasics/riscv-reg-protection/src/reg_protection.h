/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef REG_PROTECTION_H
#define REG_PROTECTION_H

#define CTX_RA 0
#define CTX_SP 8
#define CTX_GP 16
#define CTX_TP 24
#define CTX_ARG0 32
#define CTX_ARG1 40
#define CTX_VECTOR_STRIDE 48
#define CTX_VLENB 56
#define CTX_VL 64
#define CTX_VTYPE 72
#define CTX_MEASURE 80
#define CTX_GPR_SAVE 128
#define CTX_FPR_SAVE 288
#define CTX_VECTOR_SAVE 480
#define CTX_VECTOR_SEED 488
#define CTX_VECTOR_SEEN 496
#define CTX_VECTOR_AFTER 504
#define CTX_GPR_SEED 512
#define CTX_FPR_SEED 672
#define CTX_GPR_SEEN 864
#define CTX_FPR_SEEN 1024
#define CTX_GPR_AFTER 1216
#define CTX_FPR_AFTER 1376
#define CTX_ARGS_SEEN 1568
#define CTX_RESULT0 1632
#define CTX_RESULT1 1640
#define CTX_SEEN_VL 1648
#define CTX_SEEN_VTYPE 1656
#define CTX_SEEN_VCSR 1664
#define CTX_SEEN_VSTART 1672
#define CTX_AFTER_VL 1680
#define CTX_AFTER_VTYPE 1688
#define CTX_AFTER_VCSR 1696
#define CTX_AFTER_VSTART 1704
#define CTX_SEEN_SP 1712
#define CTX_SEEN_GP 1720
#define CTX_SEEN_TP 1728
#define CTX_BATCH_SP 1736
#define CTX_BATCH_GP 1744
#define CTX_BATCH_TP 1752
#define CTX_SIZE 1760

#define ARG0_VALUE 0x11111111
#define ARG1_VALUE 0x22222222
#define ARG2_VALUE 0x33333333
#define ARG3_VALUE 0x44444444
#define RESULT0_VALUE 0x51515151
#define RESULT1_VALUE 0x61616161
#define GPR_CLOBBER_VALUE 0x7e7e7e7e7e7e7e7e
#define FPR_CLOBBER_VALUE 0x6d6d6d6d6d6d6d6d

#ifndef __ASSEMBLER__
#include <stddef.h>
#include <stdint.h>

/* This is a single-threaded microbenchmark ABI, not a general library gate.
 * a0/a1 carry observed arguments and results. a2/a3 hold fixed signatures,
 * a4 the loop count, a5 the gate, a6 this context, and a7 the target. The
 * benchmark callees preserve a2-a7. No vector arguments or results are used.
 * Control, seed, and observation storage is outside the timed payload set.
 */
struct reg_context
{
    uint64_t ra, sp, gp, tp, arg0, arg1;
    uint64_t vector_stride, vlenb, vl, vtype, measure;
    uint64_t reserved0[5];
    uint64_t gpr_save[19], reserved1;
    uint64_t fpr_save[24];
    unsigned char *vector_save, *vector_seed, *vector_seen, *vector_after;
    uint64_t gpr_seed[19], reserved2;
    uint64_t fpr_seed[24];
    uint64_t gpr_seen[19], reserved3;
    uint64_t fpr_seen[24];
    uint64_t gpr_after[19], reserved4;
    uint64_t fpr_after[24];
    uint64_t args_seen[8], result0, result1;
    uint64_t seen_vl, seen_vtype, seen_vcsr, seen_vstart;
    uint64_t after_vl, after_vtype, after_vcsr, after_vstart;
    uint64_t seen_sp, seen_gp, seen_tp, batch_sp, batch_gp, batch_tp;
};

#define CHECK_OFFSET(field, offset)                                           \
    _Static_assert(offsetof(struct reg_context, field) == offset, #field)
CHECK_OFFSET(measure, CTX_MEASURE);
CHECK_OFFSET(gpr_save, CTX_GPR_SAVE);
CHECK_OFFSET(fpr_save, CTX_FPR_SAVE);
CHECK_OFFSET(vector_save, CTX_VECTOR_SAVE);
CHECK_OFFSET(gpr_seed, CTX_GPR_SEED);
CHECK_OFFSET(fpr_seed, CTX_FPR_SEED);
CHECK_OFFSET(gpr_seen, CTX_GPR_SEEN);
CHECK_OFFSET(fpr_seen, CTX_FPR_SEEN);
CHECK_OFFSET(gpr_after, CTX_GPR_AFTER);
CHECK_OFFSET(fpr_after, CTX_FPR_AFTER);
CHECK_OFFSET(args_seen, CTX_ARGS_SEEN);
CHECK_OFFSET(result0, CTX_RESULT0);
CHECK_OFFSET(seen_vl, CTX_SEEN_VL);
CHECK_OFFSET(after_vl, CTX_AFTER_VL);
CHECK_OFFSET(batch_tp, CTX_BATCH_TP);
_Static_assert(sizeof(struct reg_context) == CTX_SIZE, "context size");
#undef CHECK_OFFSET

typedef void (*reg_function)(void);
void reg_batch(struct reg_context *, reg_function gate, reg_function callee,
               uint64_t iterations);
uint64_t reg_vlenb(void);
void reg_callee_empty(void);
void reg_callee_compute(void);
void reg_callee_probe(void);

#define DECLARE_GATE(name) void reg_gate_##name(void)
DECLARE_GATE(B);
DECLARE_GATE(G_SR);
DECLARE_GATE(G_SCR);
DECLARE_GATE(F_SR);
DECLARE_GATE(F_SCR);
DECLARE_GATE(GF_SR);
DECLARE_GATE(GF_SCR);
DECLARE_GATE(V_SR);
DECLARE_GATE(V_SCR);
DECLARE_GATE(GFV_SR);
DECLARE_GATE(GFV_SCR);
DECLARE_GATE(VCTL);
#undef DECLARE_GATE
#endif
#endif
