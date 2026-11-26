/* SPDX-License-Identifier: BSD-3-Clause */
#include <stdint.h>
#include <sys/random.h>
#include <unistd.h>

/* A initializes the independent guard. B's data bound grants only reads. */
uintptr_t b_strtok_guard
    __attribute__((aligned(8), section(".dasics.strtok.guard")));

__attribute__((constructor)) static void
initialize_strtok_guard(void)
{
    if (getrandom(&b_strtok_guard, sizeof(b_strtok_guard), 0) !=
        (ssize_t)sizeof(b_strtok_guard)) {
        _exit(90);
    }
}

/* A canary failure must terminate inside B without calling A's libc. */
__attribute__((noreturn, section(".dasics.strtok.fail"))) void
b_strtok_stack_fail(void)
{
    __builtin_trap();
}
