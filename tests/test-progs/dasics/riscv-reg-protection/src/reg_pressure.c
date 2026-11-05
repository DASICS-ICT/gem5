/* SPDX-License-Identifier: BSD-3-Clause */
#define _POSIX_C_SOURCE 200112L
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "reg_pressure.h"

enum
{
    CANARY = 0xa5,
    MAX_NODES = PRESSURE_ALLOCATED_BYTES / 64
};

static const size_t working_sets[] = {1024, 32768, 65536, 131072, 262144};

struct pressure_case
{
    const char *name;
    reg_function gate;
    int protected;
};

static const struct pressure_case cases[] = {
    {"B", reg_gate_B, 0},
    {"GF_SCR", reg_gate_GF_SCR, 1},
};

struct buffer
{
    unsigned char *allocation, *data;
    size_t bytes;
};

struct fixture
{
    struct buffer frame, ring;
    struct reg_context *context;
    size_t working_set, nodes;
    uint64_t seed, expected_checksum;
};

static uint64_t checks, failures;

static void
expect(const char *field, size_t index, uint64_t actual, uint64_t expected)
{
    ++checks;
    if (actual == expected) {
        return;
    }
    if (++failures <= 16) {
        fprintf(stderr,
                "%s[%zu]: got 0x%016" PRIx64 ", expected 0x%016" PRIx64 "\n",
                field, index, actual, expected);
    }
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

static int
valid_working_set(uint64_t bytes)
{
    for (size_t i = 0; i < sizeof(working_sets) / sizeof(working_sets[0]);
         ++i) {
        if (working_sets[i] == bytes) {
            return 1;
        }
    }
    return 0;
}

static const struct pressure_case *
find_case(const char *name)
{
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        if (!strcmp(cases[i].name, name)) {
            return &cases[i];
        }
    }
    return NULL;
}

static int
allocate_buffer(struct buffer *buffer, size_t bytes)
{
    void *allocation = NULL;
    if (posix_memalign(&allocation, PRESSURE_ALIGNMENT,
                       bytes + 2 * PRESSURE_ALIGNMENT)) {
        return -1;
    }
    buffer->allocation = allocation;
    buffer->data = buffer->allocation + PRESSURE_ALIGNMENT;
    buffer->bytes = bytes;
    memset(buffer->allocation, CANARY, bytes + 2 * PRESSURE_ALIGNMENT);
    return 0;
}

static uint64_t
random_next(uint64_t *state)
{
    /* The fixed seed controls topology only, never timed instruction count. */
    uint64_t value = *state;
    value ^= value >> 12;
    value ^= value << 25;
    value ^= value >> 27;
    *state = value;
    return value * UINT64_C(2685821657736338717);
}

static void
initialize_context(struct fixture *fixture)
{
    struct reg_context *context = fixture->context;
    memset(context, 0, sizeof(*context));
    context->reserved1 = context->reserved2 = CANARY;
    context->reserved3 = context->reserved4 = CANARY;
    for (size_t i = 0; i < 19; ++i) {
        context->gpr_seed[i] = UINT64_C(0x1020304050607000) + i;
    }
    for (size_t i = 0; i < 24; ++i) {
        context->fpr_seed[i] = UINT64_C(0x3ff0010203040500) + i;
    }
    context->fpr_seed[0] = UINT64_C(0x8000000000000000);
    context->fpr_seed[1] = UINT64_C(0x7ff8000000000101);
    context->fpr_seed[2] = UINT64_C(0x7ff0000000000102);
    context->fpr_seed[3] = UINT64_C(0x7ff0000000000000);
}

static void
release_fixture(struct fixture *fixture)
{
    free(fixture->ring.allocation);
    free(fixture->frame.allocation);
}

static int
initialize_fixture(struct fixture *fixture, size_t working_set, uint64_t seed)
{
    memset(fixture, 0, sizeof(*fixture));
    /* Fixed allocation sizes and order keep paired B/SCR addresses identical.
     * The active prefix is selected only after both allocations complete. */
    if (allocate_buffer(&fixture->frame, sizeof(struct reg_context)) ||
        allocate_buffer(&fixture->ring, PRESSURE_ALLOCATED_BYTES)) {
        release_fixture(fixture);
        return -1;
    }
    fixture->context = (struct reg_context *)fixture->frame.data;
    fixture->working_set = working_set;
    fixture->nodes = working_set / PRESSURE_NODE_BYTES;
    fixture->seed = seed;
    initialize_context(fixture);
    uint32_t order[MAX_NODES];
    for (size_t i = 0; i < fixture->nodes; ++i) {
        order[i] = i;
    }
    uint64_t state = seed + 1;
    for (size_t i = fixture->nodes - 1; i > 0; --i) {
        size_t other = random_next(&state) % (i + 1);
        uint32_t saved = order[i];
        order[i] = order[other];
        order[other] = saved;
    }
    for (size_t i = 0; i < fixture->nodes; ++i) {
        uintptr_t *node =
            (uintptr_t *)(fixture->ring.data + PRESSURE_NODE_BYTES * order[i]);
        *node =
            (uintptr_t)(fixture->ring.data +
                        PRESSURE_NODE_BYTES * order[(i + 1) % fixture->nodes]);
    }
    uint64_t nodes = fixture->nodes;
    uint64_t base = (uintptr_t)fixture->ring.data;
    uint64_t address_sum =
        nodes * base + PRESSURE_NODE_BYTES * nodes * (nodes - 1) / 2;
    fixture->expected_checksum = (PRESSURE_LOADS / nodes) * address_sum;
    return 0;
}

static int
check_ring(const struct fixture *fixture)
{
    unsigned char visited[MAX_NODES] = {0};
    uintptr_t base = (uintptr_t)fixture->ring.data;
    uintptr_t pointer = base;
    uint64_t before = failures;
    for (size_t i = 0; i < fixture->nodes; ++i) {
        int valid = pointer >= base && pointer - base < fixture->working_set &&
                    (pointer - base) % PRESSURE_NODE_BYTES == 0;
        expect("ring_pointer", i, valid, 1);
        if (!valid) {
            return -1;
        }
        size_t node = (pointer - base) / PRESSURE_NODE_BYTES;
        expect("ring_unique", i, visited[node], 0);
        if (visited[node]) {
            return -1;
        }
        visited[node] = 1;
        pointer = *(const uintptr_t *)pointer;
    }
    expect("ring_closed", 0, pointer, base);
    for (size_t i = 0; i < fixture->nodes; ++i) {
        expect("ring_coverage", i, visited[i], 1);
    }
    return failures == before ? 0 : -1;
}

static void
check_canary(const struct buffer *buffer)
{
    expect("alignment", 0, (uintptr_t)buffer->data % PRESSURE_ALIGNMENT, 0);
    for (size_t i = 0; i < PRESSURE_ALIGNMENT; ++i) {
        expect("canary_before", i, buffer->allocation[i], CANARY);
        expect("canary_after", i, buffer->data[buffer->bytes + i], CANARY);
    }
}

static void
check_result(const struct fixture *fixture)
{
    const struct reg_context *context = fixture->context;
    expect("checksum", 0, context->result0, fixture->expected_checksum);
    expect("final_head", 0, context->result1, (uintptr_t)fixture->ring.data);
    expect("gpr_save_guard", 0, context->reserved1, CANARY);
    expect("gpr_seed_guard", 0, context->reserved2, CANARY);
    expect("gpr_seen_guard", 0, context->reserved3, CANARY);
    expect("gpr_after_guard", 0, context->reserved4, CANARY);
    check_canary(&fixture->frame);
    check_canary(&fixture->ring);
}

static void
check_registers(const struct fixture *fixture,
                const struct pressure_case *test, int probe)
{
    const struct reg_context *context = fixture->context;
    for (size_t i = 0; i < 19; ++i) {
        uint64_t after = context->gpr_seed[i];
        if (!test->protected) {
            if (i == 0) {
                after = (uintptr_t)fixture->ring.data;
            } else if (i == 1) {
                after = 0;
            } else if (i == 2) {
                after = fixture->expected_checksum;
            }
        }
        expect("gpr_after", i, context->gpr_after[i], after);
        if (probe) {
            uint64_t entry = test->protected ? 0 : context->gpr_seed[i];
            expect("gpr_entry", i, context->gpr_seen[i], entry);
        }
    }
    for (size_t i = 0; i < 24; ++i) {
        expect("fpr_after", i, context->fpr_after[i], context->fpr_seed[i]);
        if (probe) {
            uint64_t entry = test->protected ? 0 : context->fpr_seed[i];
            expect("fpr_entry", i, context->fpr_seen[i], entry);
        }
    }
    if (probe) {
        expect("head_input", 0, context->args_seen[0],
               (uintptr_t)fixture->ring.data);
        expect("loads_input", 0, context->args_seen[1], PRESSURE_LOADS);
        expect("head_argument", 0, context->args_seen[2],
               (uintptr_t)fixture->ring.data);
        expect("loads_argument", 0, context->args_seen[3], PRESSURE_LOADS);
        expect("calls_argument", 0, context->args_seen[4], 1);
        expect("gate_argument", 0, context->args_seen[5],
               (uintptr_t)test->gate);
        expect("context_argument", 0, context->args_seen[6],
               (uintptr_t)context);
        expect("callee_argument", 0, context->args_seen[7],
               (uintptr_t)reg_pressure_probe);
    }
}

static int
verify_all(void)
{
    for (size_t i = 0; i < sizeof(working_sets) / sizeof(working_sets[0]);
         ++i) {
        for (uint64_t seed = 0; seed < 3; ++seed) {
            struct fixture fixture;
            if (initialize_fixture(&fixture, working_sets[i], seed)) {
                return -1;
            }
            if (check_ring(&fixture)) {
                release_fixture(&fixture);
                return -1;
            }
            for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); ++c) {
                initialize_context(&fixture);
                reg_pressure_batch(fixture.context, cases[c].gate,
                                   fixture.ring.data, PRESSURE_LOADS, 1, 0,
                                   reg_pressure_probe);
                check_result(&fixture);
                check_registers(&fixture, &cases[c], 1);
            }
            check_ring(&fixture);
            release_fixture(&fixture);
        }
    }
    return 0;
}

int
main(int argc, char **argv)
{
    int verify = argc > 1 && !strcmp(argv[1], "verify");
    int measure = argc > 1 && !strcmp(argv[1], "measure");
    uint64_t expected_vlen, iterations = 0, warmup = 0;
    uint64_t working_set = 0, seed = 0, loads = PRESSURE_LOADS;
    const struct pressure_case *test = NULL;
    if ((verify && argc != 3) || (measure && argc != 10) ||
        (!verify && !measure) ||
        parse_unsigned(argv[verify ? 2 : 6], &expected_vlen) ||
        expected_vlen != 128 ||
        (measure &&
         (!(test = find_case(argv[2])) || strcmp(argv[3], "memory") ||
          parse_unsigned(argv[4], &iterations) || !iterations ||
          parse_unsigned(argv[5], &warmup) || warmup != 8 ||
          parse_unsigned(argv[7], &working_set) ||
          !valid_working_set(working_set) || parse_unsigned(argv[8], &seed) ||
          seed > 2 || parse_unsigned(argv[9], &loads) ||
          loads != PRESSURE_LOADS))) {
        fputs("Usage: binary verify 128\n"
              "       binary measure CASE memory N WARMUP 128 "
              "WORKING_SET_BYTES SEED LOADS_PER_CALL\n",
              stderr);
        puts("{\"status\":\"FAIL\",\"mode\":\"invalid\",\"vlen\":0}");
        return 2;
    }
    uint64_t vlen = 8 * reg_vlenb();
    if (vlen != expected_vlen) {
        printf("{\"status\":\"FAIL\",\"mode\":\"%s\",\"vlen\":%" PRIu64
               ",\"reason\":\"unexpected_vlen\"}\n",
               argv[1], vlen);
        return 1;
    }
    if (verify) {
        if (verify_all()) {
            ++failures;
        }
        printf("{\"status\":\"%s\",\"mode\":\"verify\",\"vlen\":%" PRIu64
               ",\"checks\":%" PRIu64 ",\"failures\":%" PRIu64 "}\n",
               failures ? "FAIL" : "PASS", vlen, checks, failures);
        return failures ? 1 : 0;
    }
    struct fixture fixture;
    if (initialize_fixture(&fixture, working_set, seed)) {
        puts("{\"status\":\"FAIL\",\"mode\":\"measure\","
             "\"vlen\":128,\"reason\":\"allocation\"}");
        return 1;
    }
    if (check_ring(&fixture)) {
        release_fixture(&fixture);
        return 1;
    }
    reg_pressure_batch(fixture.context, test->gate, fixture.ring.data, loads,
                       1, 0, reg_pressure_probe);
    check_result(&fixture);
    check_registers(&fixture, test, 1);
    if (!failures) {
        initialize_context(&fixture);
        fixture.context->measure = 1;
        reg_pressure_batch(fixture.context, test->gate, fixture.ring.data,
                           loads, iterations, warmup, reg_pressure_memory);
    }
    check_result(&fixture);
    check_registers(&fixture, test, 0);
    check_ring(&fixture);
    printf("{\"status\":\"%s\",\"mode\":\"measure\",\"vlen\":%" PRIu64
           ",\"case\":\"%s\",\"callee\":\"memory\","
           "\"iterations\":%" PRIu64 ",\"warmup\":%" PRIu64
           ",\"working_set\":%" PRIu64 ",\"seed\":%" PRIu64
           ",\"loads_per_call\":%" PRIu64 ",\"ring_address\":\"0x%" PRIxPTR
           "\",\"frame_address\":\"0x%" PRIxPTR
           "\",\"head_address\":\"0x%" PRIxPTR "\",\"checksum\":%" PRIu64
           ",\"expected_checksum\":%" PRIu64
           ",\"allocated_bytes\":%u,\"checks\":%" PRIu64
           ",\"failures\":%" PRIu64 "}\n",
           failures ? "FAIL" : "PASS", vlen, test->name, iterations, warmup,
           working_set, seed, loads, (uintptr_t)fixture.ring.data,
           (uintptr_t)fixture.context, (uintptr_t)fixture.ring.data,
           fixture.context->result0, fixture.expected_checksum,
           PRESSURE_ALLOCATED_BYTES, checks, failures);
    release_fixture(&fixture);
    return failures ? 1 : 0;
}
