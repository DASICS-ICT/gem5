/* SPDX-License-Identifier: BSD-3-Clause */
OUTPUT_ARCH(riscv)
ENTRY(_start)

/* One 2 MiB window needs one leaf table for 4 KiB identity mappings. */
MEMORY
{
    ram (rwx) : ORIGIN = 0x80000000, LENGTH = 2M
}

PHDRS
{
    machine PT_LOAD FLAGS(5);
    trusted PT_LOAD FLAGS(5);
    untrusted PT_LOAD FLAGS(5);
    data PT_LOAD FLAGS(6);
}

SECTIONS
{
    . = ORIGIN(ram);
    .text.boot :
    {
        KEEP(*(.text.init))
        *(.text.machine)
        *(.rodata.machine)
    } > ram :machine

    .text.trusted ALIGN(4096) :
    {
        trusted_start = .;
        *(.text.trusted)
        *(.rodata.trusted)
        trusted_code_end = .;
        . = trusted_start + 4096;
        trusted_end = .;
    } > ram :trusted

    /* Leave a non-present page on either side of untrusted instructions. */
    .text.untrusted ALIGN(4096) + 4096 :
    {
        untrusted_start = .;
        *(.text.untrusted)
        untrusted_code_end = .;
        . = untrusted_start + 4096;
        untrusted_end = .;
    } > ram :untrusted

    .data.machine ALIGN(4096) + 4096 :
    {
        *(.data.machine)
    } > ram :data

    /* The pressure probe needs a cold line untouched by the boot-time zeroing. */
    .rodata.prf_pressure ALIGN(4096) :
    {
        *(.rodata.prf_pressure)
    } > ram :data
    ASSERT(SIZEOF(.rodata.prf_pressure) == 0 || SIZEOF(.rodata.prf_pressure) == 4096,
           "PRF load targets must occupy one read-only user page")

    .bss.page_tables ALIGN(4096) (NOLOAD) :
    {
        __bss_start = .;
        root_table = .;
        . += 4096;
        level1_table = .;
        . += 4096;
        level0_table = .;
        . += 4096;
    } > ram :data

    .dasics_context ALIGN(4096) + 4096 (NOLOAD) :
    {
        KEEP(*(.dasics_context))
        . = 4096;
    } > ram :data

    .bss.a_stack ALIGN(4096) + 4096 (NOLOAD) :
    {
        a_stack_bottom = .;
        . += 4096;
        a_stack_top = .;
    } > ram :data

    .bss.b_stack ALIGN(4096) + 4096 (NOLOAD) :
    {
        b_stack_bottom = .;
        . += 4096;
        b_stack_top = .;
    } > ram :data

    .bss.input ALIGN(4096) + 4096 (NOLOAD) :
    {
        input_buffer = .;
        . += 4096;
        input_buffer_end = .;
    } > ram :data

    .bss.output ALIGN(4096) (NOLOAD) :
    {
        output_buffer = .;
        . += 4096;
        output_buffer_end = .;
    } > ram :data

    /* Present only when a second untrusted domain supplies a stack page. */
    .bss.c_stack ALIGN(4096) (NOLOAD) :
    {
        *(.bss.c_stack)
    } > ram :data
    ASSERT(SIZEOF(.bss.c_stack) == 0 || SIZEOF(.bss.c_stack) == 4096,
           "C stack must occupy a single mapped page")

    .bss.vector_save ALIGN(4096) (NOLOAD) :
    {
        *(.bss.vector_save)
        __bss_end = .;
    } > ram :data
    vector_page_offset = ABSOLUTE(ADDR(.bss.vector_save) - context_frame);
    ASSERT((vector_page_offset & 4095) == 0, "Vector page must be aligned")


    /DISCARD/ : { *(.comment) *(.note.GNU-stack) }

    /* Resolve the custom J displacement across the two code sections. */
    dasics_call_displacement = ABSOLUTE(callee_entry - gate_call);
    dasics_call_encoding = ABSOLUTE(0x0B
        | ((dasics_call_displacement & 0x7FE) << 20)
        | ((dasics_call_displacement & 0x7800) >> 3)
        | (dasics_call_displacement & 0x1F8000)
        | ((dasics_call_displacement & 0x200000) >> 14)
        | ((dasics_call_displacement & 0x400000) << 9));
    /* Bias the signed displacement before ld's unsigned range comparison. */
    ASSERT(dasics_call_displacement + 0x400000 <= 0x7FFFFE,
           "DASICSCALL target exceeds its signed displacement")
    ASSERT((dasics_call_displacement & 3) == 0,
           "DASICSCALL target must be instruction aligned")
    ASSERT(return_gate == gate_call + 4,
           "Return gate must immediately follow DASICSCALL")
    ASSERT(gate_call >= trusted_start && return_gate < trusted_code_end,
           "Call and return gate must be trusted")
    ASSERT(callee_entry >= untrusted_start
           && callee_entry < untrusted_code_end,
           "Callee must be untrusted")
    ASSERT(trusted_code_end <= trusted_end, "Trusted code exceeds one page")
    ASSERT(untrusted_code_end <= untrusted_end,
           "Untrusted code exceeds one page")
    ASSERT(context_frame == ADDR(.dasics_context),
           "Context frame must start at its private page base")
    ASSERT(context_frame_end - context_frame == 256,
           "Context frame must occupy 256 bytes")
    ASSERT(__bss_end <= ORIGIN(ram) + LENGTH(ram),
           "Image exceeds its Sv39 leaf table window")
}
