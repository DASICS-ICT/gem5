/* SPDX-License-Identifier: BSD-3-Clause */
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

/* Padding immediately outside the requested length also stays poisoned. */
enum
{
    MaxBytes = 4096,
    GuardBytes = 64
};
struct guarded_buffer
{
    unsigned char before[GuardBytes];
    unsigned char bytes[MaxBytes];
    unsigned char after[GuardBytes];
};
struct guarded_buffer source __attribute__((aligned(64)));
struct guarded_buffer destination __attribute__((aligned(64)));

typedef void *(*copy_fn)(void *, const void *, size_t);
extern void *b_memcpy(void *, const void *, size_t);
extern void *run_memcpy(void *, const void *, size_t, copy_fn);
extern void *checked_memcpy(void *, const void *, size_t);
extern int run_memcpy_batch(void *, const void *, size_t, unsigned);

static unsigned char
pattern(size_t index, unsigned phase)
{
    return (unsigned char)(37 * index + 83 * phase + 11);
}

static void
prepare(unsigned phase)
{
    for (size_t i = 0; i < GuardBytes; ++i) {
        source.before[i] = 0x31;
        source.after[i] = 0x42;
        destination.before[i] = 0x53;
        destination.after[i] = 0x64;
    }
    for (size_t i = 0; i < MaxBytes; ++i) {
        source.bytes[i] = pattern(i, phase);
        destination.bytes[i] = (unsigned char)~source.bytes[i];
    }
}

static int
matches(size_t n, unsigned phase)
{
    for (size_t i = 0; i < GuardBytes; ++i) {
        if (source.before[i] != 0x31 || source.after[i] != 0x42 ||
            destination.before[i] != 0x53 || destination.after[i] != 0x64) {
            return 0;
        }
    }
    for (size_t i = 0; i < MaxBytes; ++i) {
        unsigned char expected = pattern(i, phase);
        unsigned char copied = i < n ? expected : (unsigned char)~expected;
        if (source.bytes[i] != expected || destination.bytes[i] != copied) {
            return 0;
        }
    }
    return 1;
}

/* The warmup check and re-poisoning run before the workbegin marker. */
int
prepare_measured(size_t n)
{
    if (!matches(n, 0)) {
        return 0;
    }
    prepare(1);
    return 1;
}

static long
number(const char *arg)
{
    char *end;
    long value = strtol(arg, &end, 10);
    return (*arg && !*end) ? value : -1;
}

int
main(int argc, char **argv)
{
    if (argc != 2 && argc != 3) {
        return 10;
    }
    long n = number(argv[1]);
    if (n != 1 && n != 2 && n != 15 && n != 16 && n != 64 && n != MaxBytes) {
        return 10;
    }
    prepare(0);
    if (argc == 2) {
        if (checked_memcpy(destination.bytes, source.bytes, n) !=
                destination.bytes ||
            !matches(n, 0)) {
            return 11;
        }
        prepare(1);
        if (run_memcpy(destination.bytes, source.bytes, n, b_memcpy) !=
            destination.bytes) {
            return 12;
        }
    } else {
        long count = number(argv[2]);
        if (count < 1 || count > 4096) {
            return 10;
        }
        if (!run_memcpy_batch(destination.bytes, source.bytes, n, count)) {
            return 13;
        }
    }
    return matches(n, 1) ? 0 : 14;
}
