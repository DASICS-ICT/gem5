/* SPDX-License-Identifier: BSD-3-Clause */
SECTIONS
{
    .printf_b ALIGN(8) :
    {
        __dasics_untrusted_start = .;
        KEEP(*(.dasics.printf.entry))
        *(.dasics.printf.lib.text*)
        . = ALIGN(8);
        __dasics_untrusted_end = .;
    }
    .printf_b_ro ALIGN(8) (READONLY) :
    {
        __dasics_b_ro_start = .;
        *(.dasics.printf.ro .dasics.printf.lib.ro*)
        . = ALIGN(8);
        __dasics_b_ro_end = .;
    }
    .printf_b_got ALIGN(8) (READONLY) :
    {
        __dasics_b_got_start = .;
        *(.dasics.printf.got)
        . = ALIGN(8);
        __dasics_b_got_end = .;
    }
    __dasics_trusted_start = (SIZEOF(.init) ? ADDR(.init) : ADDR(.text)) & ~7;
    __dasics_trusted_end = ADDR(.printf_b);
}
INSERT AFTER .fini;
SECTIONS
{
    .printf_b_ptr ALIGN(8) :
    {
        __dasics_b_ptr_start = .;
        *(.dasics.printf.ptr)
        . = ALIGN(8);
        __dasics_b_ptr_end = .;
    }
    .printf_b_data ALIGN(8) :
    {
        __dasics_b_data_start = .;
        /* Private errno and current locale in B's single-thread TLS block. */
        __dasics_b_tp = .;
        QUAD(0)
        QUAD(b__nl_C_locobj)
        *(.dasics.printf.data .dasics.printf.lib.data*)
        . = ALIGN(8);
        __dasics_b_data_end = .;
    }
    .printf_context ALIGN(4096) (NOLOAD) :
    {
        __dasics_context_base = .;
        . += 256;
    }
    .printf_stack ALIGN(4096) (NOLOAD) :
    {
        __dasics_stack_bottom = .;
        . += 32768;
        __dasics_stack_top = .;
    }
}
INSERT AFTER .bss;
ASSERT(probe_b_entry >= __dasics_untrusted_start && probe_b_entry < __dasics_untrusted_end,
       "B probe outside the untrusted window")
ASSERT(b_printf >= __dasics_untrusted_start && b_printf < __dasics_untrusted_end &&
       b___vfprintf_internal >= __dasics_untrusted_start && b___vfprintf_internal < __dasics_untrusted_end,
       "glibc printf implementations outside the untrusted window")
