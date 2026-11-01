#include <riscv_vector.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

int
main(void)
{
    enum
    {
        ELEMENTS = 23
    };
    uint32_t a[ELEMENTS], b[ELEMENTS], c[ELEMENTS];

    for (size_t i = 0; i < ELEMENTS; ++i) {
        a[i] = (uint32_t)(i + 1);
        b[i] = 10 * a[i];
        c[i] = 0;
    }

    size_t offset = 0;
    while (offset < ELEMENTS) {
        size_t remaining = ELEMENTS - offset;
        size_t vl = __riscv_vsetvl_e32m1(remaining);

        vuint32m1_t va = __riscv_vle32_v_u32m1(a + offset, vl);
        vuint32m1_t vb = __riscv_vle32_v_u32m1(b + offset, vl);
        vuint32m1_t vc = __riscv_vadd_vv_u32m1(va, vb, vl);
        __riscv_vse32_v_u32m1(c + offset, vc, vl);

        printf("offset=%zu remaining=%zu vl=%zu\n", offset, remaining, vl);

        /* Advance by the actual element count, not a fixed batch size. */
        offset += vl;
    }

    for (size_t i = 0; i < ELEMENTS; ++i) {
        if (c[i] != a[i] + b[i]) {
            printf("Mismatch at index %zu\n", i);
            return 1;
        }
    }

    printf("PASS: %u elements\n", (unsigned)ELEMENTS);
    return 0;
}
