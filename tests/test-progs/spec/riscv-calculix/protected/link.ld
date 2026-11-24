/* SPDX-License-Identifier: BSD-3-Clause */

/* Keep the Linux ABI, TLS and libc startup layout from the default script. */
SECTIONS
{
    .dasics_fmod ALIGN(8) :
    {
        __dasics_untrusted_start = .;
        KEEP(*(.dasics.fmod.body))
        *(.dasics.fmod.helper)
        *(.dasics.fmod.error)
        . = ALIGN(8);
        __dasics_untrusted_end = .;
    }
    .dasics_fmod_ro ALIGN(8) :
    {
        __dasics_ro_start = .;
        *(.dasics.fmod.ro)
        . = ALIGN(8);
        __dasics_ro_end = .;
    }
    __dasics_trusted_start = (SIZEOF(.init) ? ADDR(.init) :
                              SIZEOF(.plt) ? ADDR(.plt) : ADDR(.text)) & ~7;
    __dasics_trusted_end = ADDR(.dasics_fmod);
}
INSERT AFTER .fini;

SECTIONS
{
    .dasics_frame ALIGN(4096) (NOLOAD) :
    {
        __dasics_context_base = .;
        . += 256;
    }
    .dasics_stack ALIGN(4096) (NOLOAD) :
    {
        __dasics_stack_bottom = .;
        . += 4096;
        __dasics_stack_top = .;
    }
}
INSERT AFTER .bss;

/* DASICSCALL.J encodes a signed, PC-relative byte displacement. */
dasics_fmod_delta = ABSOLUTE(dasics_fmod_body - dasics_fmod_call);
dasics_fmod_call_encoding = ABSOLUTE(0x0b
    | ((dasics_fmod_delta & 0x7fe) << 20)
    | ((dasics_fmod_delta & 0x7800) >> 3)
    | (dasics_fmod_delta & 0x1f8000)
    | ((dasics_fmod_delta & 0x200000) >> 14)
    | ((dasics_fmod_delta & 0x400000) << 9));
ASSERT(dasics_fmod_delta + 0x400000 <= 0x7ffffe &&
       (dasics_fmod_delta & 3) == 0, "Invalid DASICSCALL.J displacement")
ASSERT(dasics_fmod_return == dasics_fmod_call + 4, "Invalid return gate")
ASSERT(dasics_fmod_gate >= __dasics_trusted_start &&
       dasics_fmod_ret < __dasics_trusted_end, "Gate outside trusted code")
ASSERT(dasics_fmod_body == __dasics_untrusted_start &&
       dasics_fmod_error < __dasics_untrusted_end, "Invalid fmod code layout")
ASSERT(__dasics_ro_start == dasics_fmod_table &&
       __dasics_ro_end - __dasics_ro_start == 256, "Invalid fmod lookup table")
ASSERT(__dasics_context_base + 256 <= __dasics_stack_bottom &&
       __dasics_stack_top <= _end, "Invalid private stack or context frame")
