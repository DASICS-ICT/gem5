/* SPDX-License-Identifier: BSD-3-Clause */
#include <stdint.h>
#include <sys/random.h>
#include <unistd.h>

/* A initializes the guard before the first call. B's bound is read-only. */
uintptr_t b_pow_guard
    __attribute__((aligned(8), section(".dasics.pow.guard")));

__attribute__((constructor)) static void
initialize_pow_guard(void)
{
    if (getrandom(&b_pow_guard, sizeof(b_pow_guard), 0) !=
        (ssize_t)sizeof(b_pow_guard)) {
        _exit(90);
    }
}

/* Catch an unmodeled libm error path or a failed stack check inside B. */
__attribute__((noreturn, section(".dasics.pow.error"))) void
b_pow_error(void)
{
    __builtin_trap();
}
