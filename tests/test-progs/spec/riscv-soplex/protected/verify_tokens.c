/* SPDX-License-Identifier: BSD-3-Clause */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern char *strtok_gate(char *input, const char *delim, char *line);

/* The three distinct retirement sites count completed, verified calls. */
#define RETIRE_MARKER(name)                                                   \
    __attribute__((noipa)) void name(void)                                    \
    {                                                                         \
        __asm__ volatile("" ::: "memory");                                    \
    }
RETIRE_MARKER(strtok_verified_first)
RETIRE_MARKER(strtok_verified_next)
RETIRE_MARKER(strtok_verified_null)

enum
{
    LineSize = 256
};
static FILE *trace;
static unsigned calls;

static void
fail(const char *reason)
{
    fprintf(stderr, "strtok validation failed at call %u: %s\n", calls,
            reason);
    exit(EXIT_FAILURE);
}

static void
close_trace(void)
{
    if (fclose(trace) != 0) {
        _Exit(EXIT_FAILURE);
    }
}

/* MPSInput::readLine finishes one data row before starting another.
 * The trusted reference owns a row copy and a cursor distinct from both libc
 * strtok cursors. No reference storage is included in a B data bound. */
char *
checked_strtok(char *input, const char *delim, char *line)
{
    static char reference[LineSize];
    static char *cursor;
    static char *active_line;
    static size_t bytes;

    ++calls;
    if ((uintptr_t)line % 8 || strcmp(delim, " ") != 0) {
        fail("unaligned line or unexpected delimiter");
    }
    if (input) {
        if (input != line + 1) {
            fail("unexpected start of data row");
        }
        size_t length = strnlen(line, sizeof(reference));
        if (length == sizeof(reference)) {
            fail("unterminated input row");
        }
        bytes = length + 1;
        memcpy(reference, line, bytes);
        cursor = NULL;
        active_line = line;
    } else if (!cursor || active_line != line) {
        fail("continuation without its input row");
    }

    char *expected = strtok_r(input ? reference + 1 : NULL, delim, &cursor);
    char *actual = strtok_gate(input, delim, line);
    int offset = expected ? (int)(expected - reference) : -1;
    if (actual != (expected ? line + offset : NULL)) {
        fail("token offset or NULL result differs");
    }
    /* Compare through the row's original terminator, including delimiters
     * that either tokenizer replaced on earlier calls. */
    if (memcmp(reference, line, bytes) != 0) {
        fail("in-place token bytes differ");
    }

    if (!trace) {
        trace = fopen("strtok-tokens.csv", "w");
        if (!trace || atexit(close_trace) != 0 ||
            fputs("call,kind,offset,length\n", trace) == EOF) {
            fail("cannot initialize token trace");
        }
    }
    if (fprintf(trace, "%u,%s,%d,%zu\n", calls, input ? "first" : "next",
                offset, expected ? strlen(expected) : 0) < 0) {
        fail("cannot record token result");
    }
    if (input) {
        strtok_verified_first();
    } else {
        strtok_verified_next();
    }
    if (!actual) {
        strtok_verified_null();
    }
    return actual;
}
