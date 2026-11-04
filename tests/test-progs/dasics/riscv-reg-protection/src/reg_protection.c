/* SPDX-License-Identifier: BSD-3-Clause */
#define _POSIX_C_SOURCE 200112L
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "reg_protection.h"

enum
{
    PROTECT_G = 1,
    PROTECT_F = 2,
    PROTECT_V = 4,
    CLEAR = 8
};

struct test_case
{
    const char *name;
    reg_function gate;
    unsigned flags;
};

static const struct test_case cases[] = {
    {"B", reg_gate_B, 0},
    {"G_SR", reg_gate_G_SR, PROTECT_G},
    {"G_SCR", reg_gate_G_SCR, PROTECT_G | CLEAR},
    {"F_SR", reg_gate_F_SR, PROTECT_F},
    {"F_SCR", reg_gate_F_SCR, PROTECT_F | CLEAR},
    {"GF_SR", reg_gate_GF_SR, PROTECT_G | PROTECT_F},
    {"GF_SCR", reg_gate_GF_SCR, PROTECT_G | PROTECT_F | CLEAR},
    {"V_SR", reg_gate_V_SR, PROTECT_V},
    {"V_SCR", reg_gate_V_SCR, PROTECT_V | CLEAR},
    {"GFV_SR", reg_gate_GFV_SR, PROTECT_G | PROTECT_F | PROTECT_V},
    {"GFV_SCR", reg_gate_GFV_SCR, PROTECT_G | PROTECT_F | PROTECT_V | CLEAR},
    {"VCTL", reg_gate_VCTL, 0},
};

enum
{
    ALIGNMENT = 128,
    CANARY = 0xa5
};

struct buffer
{
    unsigned char *allocation, *data;
    size_t bytes;
};

struct fixture
{
    struct buffer context, vector[4];
    struct reg_context *state;
    size_t vector_bytes;
};

static uint64_t checks, failures;

static void
expect(const char *test, const char *field, size_t index, uint64_t actual,
       uint64_t expected)
{
    ++checks;
    if (actual == expected) {
        return;
    }
    if (++failures <= 16) {
        fprintf(stderr,
                "%s %s[%zu]: got 0x%016" PRIx64 ", expected 0x%016" PRIx64
                "\n",
                test, field, index, actual, expected);
    }
}

static int
allocate_buffer(struct buffer *buffer, size_t bytes)
{
    void *allocation = NULL;
    if (posix_memalign(&allocation, ALIGNMENT, bytes + 2 * ALIGNMENT)) {
        return -1;
    }
    buffer->allocation = allocation;
    buffer->data = buffer->allocation + ALIGNMENT;
    buffer->bytes = bytes;
    memset(buffer->allocation, CANARY, bytes + 2 * ALIGNMENT);
    memset(buffer->data, 0, bytes);
    return 0;
}

static void
release_fixture(struct fixture *fixture)
{
    for (size_t i = 0; i < 4; ++i) {
        free(fixture->vector[i].allocation);
    }
    free(fixture->context.allocation);
}

static unsigned char
vector_pattern(size_t index)
{
    return (unsigned char)(0x5b + 17 * index + (index >> 3) +
                           29 * (index >> 8));
}

static int
initialize_fixture(struct fixture *fixture, uint64_t vlenb)
{
    memset(fixture, 0, sizeof(*fixture));
    fixture->vector_bytes = 32 * vlenb;
    if (allocate_buffer(&fixture->context, sizeof(struct reg_context))) {
        return -1;
    }
    fixture->state = (struct reg_context *)fixture->context.data;
    for (size_t i = 0; i < 4; ++i) {
        if (allocate_buffer(&fixture->vector[i], fixture->vector_bytes)) {
            release_fixture(fixture);
            memset(fixture, 0, sizeof(*fixture));
            return -1;
        }
    }
    struct reg_context *state = fixture->state;
    state->vector_save = fixture->vector[0].data;
    state->vector_seed = fixture->vector[1].data;
    state->vector_seen = fixture->vector[2].data;
    state->vector_after = fixture->vector[3].data;
    state->vlenb = vlenb;
    state->vector_stride = 8 * vlenb;
    state->reserved1 = state->reserved2 = CANARY;
    state->reserved3 = state->reserved4 = CANARY;
    for (size_t i = 0; i < 19; ++i) {
        state->gpr_seed[i] = UINT64_C(0x1020304050607000) + i;
    }
    for (size_t i = 0; i < 24; ++i) {
        state->fpr_seed[i] = UINT64_C(0x3ff0010203040500) + i;
    }
    /* No floating arithmetic may canonicalize these payloads. */
    state->fpr_seed[0] = UINT64_C(0x8000000000000000);
    state->fpr_seed[1] = UINT64_C(0x7ff8000000000101);
    state->fpr_seed[2] = UINT64_C(0x7ff0000000000102);
    state->fpr_seed[3] = UINT64_C(0x7ff0000000000000);
    for (size_t i = 0; i < fixture->vector_bytes; ++i) {
        state->vector_seed[i] = vector_pattern(i);
    }
    return 0;
}

static void
check_canary(const char *test, const struct buffer *buffer)
{
    expect(test, "alignment", 0, (uintptr_t)buffer->data % ALIGNMENT, 0);
    for (size_t i = 0; i < ALIGNMENT; ++i) {
        expect(test, "canary_before", i, buffer->allocation[i], CANARY);
        expect(test, "canary_after", i, buffer->data[buffer->bytes + i],
               CANARY);
    }
}

static void
check_fixture(const struct test_case *test, struct fixture *fixture)
{
    struct reg_context *state = fixture->state;
    unsigned flags = test->flags;
    for (size_t i = 0; i < 19; ++i) {
        uint64_t at_entry =
            ((flags & (PROTECT_G | CLEAR)) == (PROTECT_G | CLEAR))
                ? 0
                : state->gpr_seed[i];
        uint64_t after = flags & PROTECT_G ? state->gpr_seed[i]
                                           : (uint64_t)GPR_CLOBBER_VALUE;
        expect(test->name, "gpr_entry", i, state->gpr_seen[i], at_entry);
        expect(test->name, "gpr_restore", i, state->gpr_after[i], after);
    }
    for (size_t i = 0; i < 24; ++i) {
        uint64_t at_entry =
            ((flags & (PROTECT_F | CLEAR)) == (PROTECT_F | CLEAR))
                ? 0
                : state->fpr_seed[i];
        uint64_t after = flags & PROTECT_F ? state->fpr_seed[i]
                                           : (uint64_t)FPR_CLOBBER_VALUE;
        expect(test->name, "fpr_entry", i, state->fpr_seen[i], at_entry);
        expect(test->name, "fpr_restore", i, state->fpr_after[i], after);
    }
    for (size_t i = 0; i < fixture->vector_bytes; ++i) {
        unsigned char pattern = vector_pattern(i);
        unsigned char at_entry =
            ((flags & (PROTECT_V | CLEAR)) == (PROTECT_V | CLEAR)) ? 0
                                                                   : pattern;
        unsigned char after = flags & PROTECT_V ? pattern : 0xff;
        expect(test->name, "vector_entry", i, state->vector_seen[i], at_entry);
        expect(test->name, "vector_restore", i, state->vector_after[i], after);
        expect(test->name, "vector_seed", i, state->vector_seed[i], pattern);
    }
    uint64_t arguments[] = {
        ARG0_VALUE,
        ARG1_VALUE,
        ARG2_VALUE,
        ARG3_VALUE,
        1,
        (uintptr_t)test->gate,
        (uintptr_t)state,
        (uintptr_t)reg_callee_probe,
    };
    for (size_t i = 0; i < 8; ++i) {
        expect(test->name, "argument", i, state->args_seen[i], arguments[i]);
    }
    expect(test->name, "result", 0, state->result0, RESULT0_VALUE);
    expect(test->name, "result", 1, state->result1, RESULT1_VALUE);
    uint64_t initial_vl = state->vlenb / 4;
    if (initial_vl > 7) {
        initial_vl = 7;
    }
    expect(test->name, "entry_vl", 0, state->seen_vl, initial_vl);
    expect(test->name, "entry_vtype", 0, state->seen_vtype, 16);
    expect(test->name, "entry_vcsr", 0, state->seen_vcsr, 0);
    expect(test->name, "entry_vstart", 0, state->seen_vstart, 0);
    expect(test->name, "callee_vl", 0, state->after_vl, 3);
    expect(test->name, "callee_vtype", 0, state->after_vtype, 201);
    expect(test->name, "callee_vcsr", 0, state->after_vcsr, 5);
    expect(test->name, "callee_vstart", 0, state->after_vstart, 0);
    expect(test->name, "callee_sp", 0, state->seen_sp, state->batch_sp);
    expect(test->name, "stack_alignment", 0, state->seen_sp % 16, 0);
    expect(test->name, "callee_gp", 0, state->seen_gp, state->batch_gp);
    expect(test->name, "callee_tp", 0, state->seen_tp, state->batch_tp);
    expect(test->name, "restore_sp", 0, state->sp, state->batch_sp);
    expect(test->name, "restore_gp", 0, state->gp, state->batch_gp);
    expect(test->name, "restore_tp", 0, state->tp, state->batch_tp);
    expect(test->name, "gpr_save_guard", 0, state->reserved1, CANARY);
    expect(test->name, "gpr_seed_guard", 0, state->reserved2, CANARY);
    expect(test->name, "gpr_seen_guard", 0, state->reserved3, CANARY);
    expect(test->name, "gpr_after_guard", 0, state->reserved4, CANARY);
    check_canary(test->name, &fixture->context);
    for (size_t i = 0; i < 4; ++i) {
        check_canary(test->name, &fixture->vector[i]);
    }
}

static int
verify_case(const struct test_case *test, uint64_t vlenb)
{
    struct fixture fixture;
    if (initialize_fixture(&fixture, vlenb)) {
        return -1;
    }
    reg_batch(fixture.state, test->gate, reg_callee_probe, 1);
    check_fixture(test, &fixture);
    release_fixture(&fixture);
    return 0;
}

static int
parse_unsigned(const char *text, uint64_t *value)
{
    char *end;
    errno = 0;
    if (!*text || *text == '-') {
        return -1;
    }
    unsigned long long parsed = strtoull(text, &end, 10);
    if (errno || *end) {
        return -1;
    }
    *value = parsed;
    return 0;
}

static const struct test_case *
find_case(const char *name)
{
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        if (!strcmp(cases[i].name, name)) {
            return &cases[i];
        }
    }
    return NULL;
}

int
main(int argc, char **argv)
{
    const char *mode = argc > 1 ? argv[1] : "invalid";
    int verify = !strcmp(mode, "verify");
    int measure = !strcmp(mode, "measure");
    uint64_t expected_vlen, iterations = 0, warmup = 0;
    if ((!verify && !measure) || (verify && argc != 3) ||
        (measure && argc != 7) ||
        parse_unsigned(argv[verify ? 2 : 6], &expected_vlen) ||
        (expected_vlen != 128 && expected_vlen != 256 &&
         expected_vlen != 512 && expected_vlen != 1024)) {
        fputs("Usage: binary verify EXPECTED_VLEN\n"
              "       binary measure CASE CALLEE ITERATIONS WARMUP "
              "EXPECTED_VLEN\n",
              stderr);
        puts("{\"status\":\"FAIL\",\"mode\":\"invalid\",\"vlen\":0}");
        return 2;
    }
    uint64_t vlenb = reg_vlenb();
    uint64_t vlen = 8 * vlenb;
    if (vlen != expected_vlen) {
        printf("{\"status\":\"FAIL\",\"mode\":\"%s\",\"vlen\":%" PRIu64
               ",\"reason\":\"unexpected_vlen\"}\n",
               mode, vlen);
        return 1;
    }
    if (verify) {
        for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
            if (verify_case(&cases[i], vlenb)) {
                fputs("Cannot allocate verification buffers\n", stderr);
                ++failures;
                break;
            }
        }
        printf("{\"status\":\"%s\",\"mode\":\"verify\",\"vlen\":%" PRIu64
               ",\"cases\":%zu,\"checks\":%" PRIu64 ",\"failures\":%" PRIu64
               "}\n",
               failures ? "FAIL" : "PASS", vlen,
               sizeof(cases) / sizeof(cases[0]), checks, failures);
        return failures ? 1 : 0;
    }
    const struct test_case *test = find_case(argv[2]);
    reg_function callee = !strcmp(argv[3], "empty")     ? reg_callee_empty
                          : !strcmp(argv[3], "compute") ? reg_callee_compute
                                                        : NULL;
    if (!test || !callee || parse_unsigned(argv[4], &iterations) ||
        !iterations || parse_unsigned(argv[5], &warmup)) {
        puts("{\"status\":\"FAIL\",\"mode\":\"measure\","
             "\"reason\":\"invalid_measurement\"}");
        return 2;
    }
    /* Check the selected implementation without instrumentation in its ROI. */
    if (verify_case(test, vlenb) || failures) {
        printf("{\"status\":\"FAIL\",\"mode\":\"measure\",\"vlen\":%" PRIu64
               ",\"reason\":\"functional_probe\"}\n",
               vlen);
        return 1;
    }
    struct fixture fixture;
    if (initialize_fixture(&fixture, vlenb)) {
        puts("{\"status\":\"FAIL\",\"mode\":\"measure\","
             "\"reason\":\"allocation\"}");
        return 1;
    }
    if (warmup) {
        reg_batch(fixture.state, test->gate, callee, warmup);
    }
    fixture.state->measure = 1;
    reg_batch(fixture.state, test->gate, callee, iterations);
    check_canary(test->name, &fixture.context);
    for (size_t i = 0; i < 4; ++i) {
        check_canary(test->name, &fixture.vector[i]);
    }
    printf("{\"status\":\"%s\",\"mode\":\"measure\",\"vlen\":%" PRIu64
           ",\"case\":\"%s\",\"callee\":\"%s\","
           "\"iterations\":%" PRIu64 ",\"warmup\":%" PRIu64
           ",\"vector_bytes\":%zu,\"context_bytes\":%zu}\n",
           failures ? "FAIL" : "PASS", vlen, test->name, argv[3], iterations,
           warmup, fixture.vector_bytes,
           sizeof(struct reg_context) + fixture.vector_bytes);
    release_fixture(&fixture);
    return failures ? 1 : 0;
}
