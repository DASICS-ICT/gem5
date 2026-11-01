#include <riscv_vector.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

int
main(void)
{
    enum
    {
        ELEMENTS = 8
    };
    const uint32_t a[ELEMENTS] = {1, 2, 3, 4, 5, 6, 7, 8};
    const uint32_t b[ELEMENTS] = {10, 20, 30, 40, 50, 60, 70, 80};
    uint32_t c[ELEMENTS];

    /* This single-chunk example requires all eight elements to fit. */
    size_t vl = __riscv_vsetvl_e32m1(ELEMENTS);
    if (vl != ELEMENTS) {
        printf("Expected VL=8, got %zu\n", vl);
        return 1;
    }

    /* Load VL unsigned 32-bit elements from each input array. */
    vuint32m1_t va = __riscv_vle32_v_u32m1(a, vl);
    vuint32m1_t vb = __riscv_vle32_v_u32m1(b, vl);

    /* Add corresponding active elements, producing a vector result. */
    vuint32m1_t vc = __riscv_vadd_vv_u32m1(va, vb, vl);

    /* Store the active elements before inspecting them with scalar C. */
    __riscv_vse32_v_u32m1(c, vc, vl);

    printf("VL=%zu\n", vl);
    for (size_t i = 0; i < ELEMENTS; ++i) {
        if (c[i] != a[i] + b[i]) {
            printf("Mismatch at index %zu\n", i);
            return 1;
        }
        printf("%u%s", (unsigned)c[i], i + 1 == ELEMENTS ? "\n" : " ");
    }

    return 0;
}
