#include <stdio.h>

/*
 * Probe vsetvli with VLEN=256, ELEN>=64, and LMUL=1.
 *
 * vsetvli rd, rs1, eSEW, mLMUL, tail_policy, mask_policy uses ordinary
 * integer registers for rd and rs1 in this probe. rs1 supplies the
 * application vector length (AVL); rd receives the selected vector
 * length (VL), measured in elements. The x0 operand special cases are
 * not used here.
 *
 * e32/e64 select the element width (SEW), and m1 selects a one-register
 * group (LMUL=1). Thus VLMAX=VLEN/SEW. The instruction updates vtype
 * and vl, clears vstart, and leaves the hardware VLEN unchanged.
 * Subsequent vector instructions use the configured vector state.
 *
 * ta/ma allow later vector operations to discard old destination values
 * in tail elements (indices >= VL) and masked-off elements. These
 * policies do not guarantee zero values. tu/mu request preservation
 * of the corresponding old destination elements instead. vsetvli
 * itself configures state without performing vector data arithmetic.
 *
 * For supported formats and the normal register form used here:
 *   AVL <= VLMAX: VL=AVL.
 *   AVL >= 2*VLMAX: VL=VLMAX.
 *   VLMAX < AVL < 2*VLMAX: ceil(AVL/2) <= VL <= VLMAX.
 * The last range permits implementation-specific choices. These inputs
 * avoid it, giving portable expected values for the stated hardware.
 *
 * GNU extended asm maps %0 to the "=r" output and %1 to the "r" input.
 * The compiler chooses the integer registers; the output is assigned
 * to the named C variable. volatile retains each configuration operation.
 */
int
main(void)
{
    unsigned long vlenb;
    /* Exceed twice both capacities so the selected VL must equal VLMAX. */
    unsigned long avl = 100;
    unsigned long vl32;
    unsigned long vl64;
    unsigned long vl_tail;

    /* vlenb reports bytes; the vector register width is vlenb * 8 bits. */
    __asm__ volatile("csrr %0, vlenb" : "=r"(vlenb));

    /* e32/m1 gives VLMAX=256/32=8, so AVL=100 selects VL=8. */
    __asm__ volatile("vsetvli %0, %1, e32, m1, ta, ma"
                     : "=r"(vl32)
                     : "r"(avl));

    /* e64/m1 gives VLMAX=256/64=4, so AVL=100 selects VL=4. */
    __asm__ volatile("vsetvli %0, %1, e64, m1, ta, ma"
                     : "=r"(vl64)
                     : "r"(avl));

    /* Keep the format and request a short tail: AVL=3 selects VL=3. */
    avl = 3;
    __asm__ volatile("vsetvli %0, %1, e64, m1, ta, ma"
                     : "=r"(vl_tail)
                     : "r"(avl));

    printf("VLEN=%lu bits\n", vlenb * 8);
    printf("SEW=32, AVL=100, VL=%lu\n", vl32);
    printf("SEW=64, AVL=100, VL=%lu\n", vl64);
    printf("SEW=64, AVL=3, VL=%lu\n", vl_tail);

    return (vlenb == 32 && vl32 == 8 && vl64 == 4 && vl_tail == 3) ? 0 : 1;
}
