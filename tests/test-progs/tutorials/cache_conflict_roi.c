#include <stdio.h>

#include "gem5/m5ops.h"

/* Place the third line in another set for the tested caches. */
_Alignas(4096) static volatile unsigned char cache_data[4161] = {
    [0] = 1,
    [2048] = 2,
    [4160] = 3,
};

int
main(void)
{
    unsigned int sum = 0;

    /* Load the three data lines before resetting statistics. */
    (void)cache_data[0];
    (void)cache_data[2048];
    (void)cache_data[4160];

    m5_reset_stats(0, 0);

    for (unsigned int i = 0; i < 10000; ++i) {
        sum += cache_data[0];
        sum += cache_data[2048];
        sum += cache_data[4160];
    }

    m5_dump_stats(0, 0);

    printf("sum=%u\n", sum);
    return sum == 60000 ? 0 : 1;
}
