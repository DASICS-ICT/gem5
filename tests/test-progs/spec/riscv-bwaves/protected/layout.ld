/* SPDX-License-Identifier: BSD-3-Clause */
SECTIONS
{
    .pow_b_text ALIGN(8) :
    {
        __dasics_untrusted_start = .;
        KEEP(*(.dasics.pow.text))
        KEEP(*(.dasics.pow.error))
        . = ALIGN(8);
        __dasics_untrusted_end = .;
    }
    __dasics_trusted_start = (SIZEOF(.init) ? ADDR(.init) :
                              SIZEOF(.plt) ? ADDR(.plt) : ADDR(.text)) & ~7;
    __dasics_trusted_end = ADDR(.pow_b_text);
}
INSERT AFTER .fini;

SECTIONS
{
    .pow_constants ALIGN(8) :
    {
        __pow_b_ro_start = .;
        KEEP(*(.dasics.pow.guard))
        b_pow_guard_slot = .;
        QUAD(b_pow_guard)
        b_pow_log_slot = .;
        QUAD(b_pow_log_table)
        b_pow_exp_slot = .;
        QUAD(b_pow_exp_table)
        KEEP(*(.dasics.pow.literals .dasics.pow.tables))
        . = ALIGN(8);
        __pow_b_ro_end = .;
    }
    .pow_context ALIGN(4096) (NOLOAD) :
    {
        __dasics_context_base = .;
        . += 256;
    }
    .pow_stack ALIGN(4096) (NOLOAD) :
    {
        __dasics_stack_bottom = .;
        . += 4096;
        __dasics_stack_top = .;
    }
}
INSERT AFTER .bss;

ASSERT(b_pow == __dasics_untrusted_start &&
       b_pow_error > b_pow && b_pow_error < __dasics_untrusted_end,
       "B must contain the real pow entry and its error handler")
ASSERT(b_pow_guard == __pow_b_ro_start &&
       b_pow_log_table >= b_pow_exp_slot + 8 &&
       b_pow_exp_table >= b_pow_exp_slot + 8 &&
       b_pow_log_table + 4168 <= __pow_b_ro_end &&
       b_pow_exp_table + 2224 <= __pow_b_ro_end,
       "Private guard and libm tables must lie inside B's read-only bound")
ASSERT(__pow_b_ro_end <= __dasics_context_base &&
       __dasics_context_base + 256 <= __dasics_stack_bottom &&
       __dasics_stack_top <= _end,
       "B's stack and A's context must fit below the process break")
