/* SPDX-License-Identifier: BSD-3-Clause */
#define _POSIX_C_SOURCE 200112L
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "reg_restore.h"

enum
{
    CANARY = 0xa5,
    OBSERVATION_POISON = 0xcc
};

struct buffer
{
    unsigned char *allocation, *data;
    size_t bytes;
};

struct group
{
    const char *name;
    restore_function function;
    size_t offset, bytes, lines;
};

static uint64_t checks, failures;

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
allocate_buffer(struct buffer *buffer, size_t bytes)
{
    void *allocation = NULL;
    if (posix_memalign(&allocation, RESTORE_ALIGNMENT,
                       bytes + 2 * RESTORE_ALIGNMENT)) {
        return -1;
    }
    buffer->allocation = allocation;
    buffer->data = buffer->allocation + RESTORE_ALIGNMENT;
    buffer->bytes = bytes;
    memset(buffer->allocation, CANARY, bytes + 2 * RESTORE_ALIGNMENT);
    return 0;
}

static uint64_t
scalar_pattern(char group, size_t index)
{
    if (group == 'G') {
        return UINT64_C(0x1020304050607000) + index;
    }
    static const uint64_t floating_special[] = {
        UINT64_C(0x8000000000000000),
        UINT64_C(0x7ff8000000000101),
        UINT64_C(0x7ff0000000000102),
        UINT64_C(0x7ff0000000000000),
    };
    if (index < sizeof(floating_special) / sizeof(floating_special[0])) {
        return floating_special[index];
    }
    return UINT64_C(0x3ff0010203040500) + index;
}

static unsigned char
vector_pattern(size_t index)
{
    return (unsigned char)(0x5b + 17 * index + (index >> 3) +
                           29 * (index >> 8));
}

static void
expect(uint64_t sample, const char *field, size_t index, uint64_t actual,
       uint64_t expected)
{
    ++checks;
    if (actual == expected) {
        return;
    }
    if (++failures <= 16) {
        fprintf(stderr,
                "sample=%" PRIu64 " %s[%zu]: got 0x%016" PRIx64
                ", expected 0x%016" PRIx64 "\n",
                sample, field, index, actual, expected);
    }
}

static void
check_canary(uint64_t sample, const struct buffer *buffer)
{
    expect(sample, "alignment", 0, (uintptr_t)buffer->data % RESTORE_ALIGNMENT,
           0);
    for (size_t i = 0; i < RESTORE_ALIGNMENT; ++i) {
        expect(sample, "canary_before", i, buffer->allocation[i], CANARY);
        expect(sample, "canary_after", i, buffer->data[buffer->bytes + i],
               CANARY);
    }
}

static void
check_sample(uint64_t sample, const struct group *group,
             const struct buffer *source, const struct buffer *observation)
{
    char name = *group->name;
    if (name == 'G' || name == 'F') {
        const uint64_t *actual = (const uint64_t *)observation->data;
        const uint64_t *unchanged =
            (const uint64_t *)(source->data + group->offset);
        for (size_t i = 0; i < group->bytes / 8; ++i) {
            uint64_t pattern = scalar_pattern(name, i);
            expect(sample, "register", i, actual[i], pattern);
            expect(sample, "source", i, unchanged[i], pattern);
        }
    } else if (name == 'V') {
        for (size_t i = 0; i < group->bytes; ++i) {
            unsigned char pattern = vector_pattern(i);
            expect(sample, "vector_byte", i, observation->data[i], pattern);
            expect(sample, "source_byte", i, source->data[i], pattern);
        }
    } else {
        for (size_t i = 0; i < observation->bytes; ++i) {
            expect(sample, "baseline_observation", i, observation->data[i],
                   OBSERVATION_POISON);
        }
    }
    check_canary(sample, source);
    check_canary(sample, observation);
}

int
main(int argc, char **argv)
{
    uint64_t samples, expected_vlen;
    if (argc != 4 || strlen(argv[1]) != 1 || !strchr("BGFV", *argv[1]) ||
        parse_unsigned(argv[2], &samples) || !samples ||
        parse_unsigned(argv[3], &expected_vlen) ||
        (expected_vlen != 128 && expected_vlen != 256 &&
         expected_vlen != 512 && expected_vlen != 1024)) {
        fputs("Usage: binary GROUP SAMPLES EXPECTED_VLEN\n", stderr);
        puts("{\"status\":\"FAIL\",\"mode\":\"restore\","
             "\"reason\":\"invalid_arguments\"}");
        return 2;
    }
    uint64_t vlenb = reg_restore_vlenb();
    uint64_t vlen = 8 * vlenb;
    if (vlen != expected_vlen) {
        printf("{\"status\":\"FAIL\",\"group\":\"%s\","
               "\"samples\":%" PRIu64 ",\"vlen\":%" PRIu64
               ",\"reason\":\"unexpected_vlen\"}\n",
               argv[1], samples, vlen);
        return 1;
    }
    struct group group = {argv[1], reg_restore_B, 0, 0, 0};
    size_t source_bytes = 32 * vlenb;
    switch (*group.name) {
        case 'G':
            group.function = reg_restore_G;
            group.offset = CTX_GPR_SAVE;
            group.bytes = 19 * 8;
            group.lines = 3;
            source_bytes = RESTORE_SOURCE_BYTES;
            break;
        case 'F':
            group.function = reg_restore_F;
            group.offset = CTX_FPR_SAVE;
            group.bytes = 24 * 8;
            group.lines = 4;
            source_bytes = RESTORE_SOURCE_BYTES;
            break;
        case 'V':
            group.function = reg_restore_V;
            group.bytes = source_bytes;
            group.lines = source_bytes / 64;
            break;
    }
    size_t observation_bytes = group.bytes ? group.bytes : 8;
    struct buffer source = {0};
    struct buffer observation = {0};
    if (allocate_buffer(&source, source_bytes) ||
        allocate_buffer(&observation, observation_bytes)) {
        fputs("Cannot allocate restore buffers\n", stderr);
        printf("{\"status\":\"FAIL\",\"group\":\"%s\","
               "\"samples\":%" PRIu64 ",\"vlen\":%" PRIu64
               ",\"reason\":\"allocation\"}\n",
               group.name, samples, vlen);
        free(source.allocation);
        free(observation.allocation);
        return 1;
    }
    if (*group.name == 'G' || *group.name == 'F') {
        uint64_t *data = (uint64_t *)(source.data + group.offset);
        for (size_t i = 0; i < group.bytes / 8; ++i) {
            data[i] = scalar_pattern(*group.name, i);
        }
    } else {
        for (size_t i = 0; i < source_bytes; ++i) {
            source.data[i] = vector_pattern(i);
        }
    }
    /* Warm the exact restore instruction addresses without protocol events.
     * Every invocation poisons the target registers after source-line reads.
     */
    memset(observation.data, OBSERVATION_POISON, observation.bytes);
    group.function(source.data, observation.data, 8 * vlenb, 0);
    check_sample(0, &group, &source, &observation);
    for (uint64_t sample = 1; sample <= samples; ++sample) {
        memset(observation.data, OBSERVATION_POISON, observation.bytes);
        group.function(source.data, observation.data, 8 * vlenb, 1);
        check_sample(sample, &group, &source, &observation);
    }
    printf("{\"status\":\"%s\",\"mode\":\"restore\",\"group\":\"%s\","
           "\"samples\":%" PRIu64 ",\"vlen\":%" PRIu64 ",\"checks\":%" PRIu64
           ",\"failures\":%" PRIu64
           ",\"data_bytes\":%zu,\"cache_lines\":%zu}\n",
           failures ? "FAIL" : "PASS", group.name, samples, vlen, checks,
           failures, group.bytes, group.lines);
    free(source.allocation);
    free(observation.allocation);
    return failures ? 1 : 0;
}
