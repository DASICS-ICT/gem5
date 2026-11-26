/* SPDX-License-Identifier: BSD-3-Clause */
SECTIONS
{
    .memcpy_b ALIGN(8) :
    {
        __dasics_untrusted_start = .;
        KEEP(*(.dasics.memcpy.entry))
        *(.dasics.memcpy.text)
        . = ALIGN(8);
        __dasics_untrusted_end = .;
    }
    .memcpy_b_ro ALIGN(8) :
    {
        __dasics_b_ro_start = .;
        *(.dasics.memcpy.ro)
        . = ALIGN(8);
        __dasics_b_ro_end = .;
    }
    __dasics_trusted_start = (SIZEOF(.init) ? ADDR(.init) : ADDR(.text)) & ~7;
    __dasics_trusted_end = ADDR(.memcpy_b);
}
INSERT AFTER .fini;

SECTIONS
{
    .memcpy_context ALIGN(4096) (NOLOAD) :
    {
        __dasics_context_base = .;
        . += 256;
    }
    .memcpy_stack ALIGN(4096) (NOLOAD) :
    {
        __dasics_stack_bottom = .;
        . += 32768;
        __dasics_stack_top = .;
    }
}
INSERT AFTER .bss;

ASSERT(b_memcpy >= __dasics_untrusted_start && b_memcpy < __dasics_untrusted_end,
       "glibc memcpy outside B")
ASSERT(b_wordcopy_fwd_aligned >= __dasics_untrusted_start &&
       b_wordcopy_fwd_aligned < __dasics_untrusted_end &&
       b_wordcopy_fwd_dest_aligned >= __dasics_untrusted_start &&
       b_wordcopy_fwd_dest_aligned < __dasics_untrusted_end, "word-copy helpers outside B")
