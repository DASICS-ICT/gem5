#include <stdio.h>

int
main(void)
{
    unsigned long vlenb;

    /* Read the guest's architectural vector register size. */
    __asm__ volatile("csrr %0, vlenb" : "=r"(vlenb));

    printf("vlenb=%lu bytes\n", vlenb);
    printf("VLEN=%lu bits\n", vlenb * 8);

    return 0;
}
