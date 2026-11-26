/* SPDX-License-Identifier: BSD-3-Clause */
#define _POSIX_C_SOURCE 200809L

#include <stdint.h>
#include <stdio.h>
#include <stdio_ext.h>
#include <stdlib.h>
#include <string.h>
#include <sys/random.h>
#include <unistd.h>

/* A initializes these slots and grants B read access during printf. */
FILE *b_stdout __attribute__((aligned(8), section(".dasics.printf.ptr")));
uintptr_t b_stack_guard
    __attribute__((aligned(8), section(".dasics.printf.ptr")));
#if PRINTF_ROI
enum
{
    BufferSize = 32768,
    WarmupCalls = 128,
    MaxMeasuredCalls = 4096
};
extern int run_printf_batch(unsigned warmup, unsigned measured);
#else
enum
{
    BufferSize = 256
};
#endif
char b_buffer[BufferSize]
    __attribute__((aligned(8), section(".dasics.printf.data")));
const char b_format[8]
    __attribute__((aligned(8), section(".dasics.printf.ro"))) = "n=%d\n";
uintptr_t b_file_hi;

extern int run_printf(const char *format, int argument);

/* A writes only from the known buffer after checking the produced length. */
__attribute__((noinline)) int
emit_buffer(size_t produced)
{
    return write(STDOUT_FILENO, b_buffer, produced) == (ssize_t)produced;
}

int
#if PRINTF_ROI
main(int argc, char **argv)
#else
main(void)
#endif
{
    size_t output_calls = 1;
    int measured = 0;
#if PRINTF_ROI
    if (argc == 2) {
        char *end;
        long count = strtol(argv[1], &end, 10);
        if (end == argv[1] || *end || count < 1 || count > MaxMeasuredCalls) {
            _exit(15);
        }
        measured = (int)count;
        output_calls = WarmupCalls + measured;
    } else if (argc != 1) {
        _exit(15);
    }
#endif
    if (getrandom(&b_stack_guard, sizeof(b_stack_guard), 0) !=
        (ssize_t)sizeof(b_stack_guard)) {
        _exit(10);
    }
    FILE *stream = fdopen(STDOUT_FILENO, "w");
    if (!stream || ((uintptr_t)stream & 7) ||
        setvbuf(stream, b_buffer, _IOFBF, sizeof(b_buffer)) != 0) {
        _exit(10);
    }
    __fsetlocking(stream, FSETLOCKING_BYCALLER);

    /* Enter byte-oriented buffered write mode without flushing fd 1. */
    if (fputc('?', stream) == EOF || __fpending(stream) != 1) {
        _exit(11);
    }
    __fpurge(stream);
    if (stream->_IO_write_base != b_buffer ||
        stream->_IO_write_ptr != b_buffer ||
        stream->_IO_write_end != b_buffer + sizeof(b_buffer)) {
        _exit(11);
    }
    memset(b_buffer, 0xa5, sizeof(b_buffer));
    b_stdout = stream;
    /* glibc's _IO_FILE_plus places its vtable pointer just after FILE. */
    b_file_hi = ((uintptr_t)stream + sizeof(FILE) + sizeof(void *) + 7) &
                ~(uintptr_t)7;

    int result;
#if PRINTF_ROI
    if (measured) {
        result = run_printf_batch(WarmupCalls, measured);
    } else
#endif
    {
        result = run_printf(b_format, 7);
    }
    if (result < 0) {
        _exit(result >= -31 ? 32 - result : 64);
    }
    if (result != 4 * (measured ? measured : 1)) {
        _exit(12);
    }

    uintptr_t begin = (uintptr_t)b_buffer;
    uintptr_t cursor = (uintptr_t)stream->_IO_write_ptr;
    if (stream->_IO_write_base != b_buffer ||
        stream->_IO_write_end != b_buffer + sizeof(b_buffer) ||
        cursor < begin || cursor > begin + sizeof(b_buffer)) {
        _exit(13);
    }
    size_t produced = cursor - begin;
    if (produced != 4 * output_calls) {
        _exit(13);
    }
#if PRINTF_ROI
    for (size_t i = 0; i < produced; i += 4) {
        if (memcmp(b_buffer + i, "n=7\n", 4) != 0) {
            _exit(16);
        }
    }
#endif
    /* Skip exit-time flushing of the private stream. */
    _exit(emit_buffer(produced) ? 0 : 14);
}
