#include <stdio.h>

#include "gem5/m5ops.h"

/* Preserve repeated loads; the offsets alias in both tested caches. */
_Alignas(4096) static volatile unsigned char cache_data[4097] = {
    [0] = 1,
    [2048] = 2,
    [4096] = 3,
};

int
main(void)
{
    unsigned int sum = 0;

    m5_reset_stats(0, 0);

    for (unsigned int i = 0; i < 10000; ++i) {
        sum += cache_data[0];
        sum += cache_data[2048];
        sum += cache_data[4096];
    }

    m5_dump_stats(0, 0);

    printf("sum=%u\n", sum);
    return sum == 60000 ? 0 : 1;
}
