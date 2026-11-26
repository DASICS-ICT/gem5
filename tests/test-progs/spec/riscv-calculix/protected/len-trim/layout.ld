/* SPDX-License-Identifier: BSD-3-Clause */
SECTIONS
{
    .dasics_trim ALIGN(8) :
    {
        __dasics_untrusted_start = .;
        KEEP(*(.dasics.trim.body))
        . = ALIGN(8);
        __dasics_untrusted_end = .;
    }
    .dasics_trim_ro ALIGN(8) (READONLY) : { *(.dasics.trim.ro) }
    __dasics_trusted_start = (SIZEOF(.init) ? ADDR(.init) :
                              SIZEOF(.plt) ? ADDR(.plt) : ADDR(.text)) & ~7;
    __dasics_trusted_end = ADDR(.dasics_trim);
}
INSERT AFTER .fini;

SECTIONS
{
    .dasics_trim_frame ALIGN(4096) (NOLOAD) :
    {
        __dasics_context_base = .;
        . += 256;
    }
    .dasics_trim_input ALIGN(8) (NOLOAD) :
    {
        __trim_input = .;
        . += 8;
        __trim_input_end = .;
    }
    .dasics_trim_stack ALIGN(4096) (NOLOAD) :
    {
        __dasics_stack_bottom = .;
        . += 4096;
        __dasics_stack_top = .;
    }
}
INSERT AFTER .bss;

ASSERT(trim_gate >= __dasics_trusted_start && trim_gate < __dasics_trusted_end,
       "LEN_TRIM gate is outside trusted text")
ASSERT(b_len_trim == __dasics_untrusted_start, "LEN_TRIM body is outside B")
ASSERT(__trim_input_end - __trim_input == 8 &&
       (__trim_input & 7) == 0 && __dasics_context_base + 256 <= __trim_input &&
       __trim_input_end <= __dasics_stack_bottom && __dasics_stack_top <= _end,
       "LEN_TRIM data regions overlap or exceed the process break")
