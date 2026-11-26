/* SPDX-License-Identifier: BSD-3-Clause */
SECTIONS
{
    .strtok_b_text ALIGN(8) :
    {
        __dasics_untrusted_start = .;
        KEEP(*(.dasics.strtok.text .dasics.strtok.fail))
        . = ALIGN(8);
        __dasics_untrusted_end = .;
    }
    __dasics_trusted_start = (SIZEOF(.init) ? ADDR(.init) :
                              SIZEOF(.plt) ? ADDR(.plt) : ADDR(.text)) & ~7;
    __dasics_trusted_end = ADDR(.strtok_b_text);
}
INSERT AFTER .fini;

SECTIONS
{
    .strtok_constants ALIGN(8) :
    {
        /* A seeds the guard at startup. B receives a read-only bound. */
        __strtok_b_ro_start = .;
        KEEP(*(.dasics.strtok.guard))
        b_strtok_guard_slot = .;
        QUAD(b_strtok_guard)
        b_delim = .;
        BYTE(0x20)
        BYTE(0)
        . = ALIGN(8);
        __strtok_b_ro_end = .;
    }
    .strtok_cursor ALIGN(8) (NOLOAD) :
    {
        __strtok_b_rw_start = .;
        KEEP(*(.dasics.strtok.cursor))
        __strtok_b_rw_end = .;
    }
    .strtok_context ALIGN(4096) (NOLOAD) :
    {
        __dasics_context_base = .;
        . += 256;
    }
    .strtok_stack ALIGN(4096) (NOLOAD) :
    {
        __dasics_stack_bottom = .;
        . += 4096;
        __dasics_stack_top = .;
    }
}
INSERT AFTER .bss;

ASSERT(b_strtok == __dasics_untrusted_start &&
       b_strtok_stack_fail < __dasics_untrusted_end,
       "B must contain the real strtok and its failure handler")
ASSERT(b_strtok_guard == __strtok_b_ro_start &&
       b_strtok_guard_slot == b_strtok_guard + 8 &&
       b_strtok_cursor == __strtok_b_rw_start &&
       __strtok_b_rw_end - __strtok_b_rw_start == 8,
       "Unexpected private guard or glibc cursor layout")
ASSERT(__strtok_b_rw_end <= __dasics_context_base &&
       __dasics_context_base + 256 <= __dasics_stack_bottom &&
       __dasics_stack_top <= _end,
       "B stack and A context must fit below the process break")
