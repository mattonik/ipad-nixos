#include "probe.h"

static inline void sync_access(void)
{
    __asm__ volatile("dsb sy" ::: "memory");
}

void j81_sample_fender_id(const volatile uint32_t *page5_base,
                          const volatile uint32_t *fender_base,
                          const volatile uint32_t *core_base,
                          volatile struct j81_sample *result)
{
    result->stage = J81_MISSING_MAP;
    result->page5 = 0;
    result->fender = 0;
    result->gpu_id = 0;
    if (!page5_base || !fender_base || !core_base)
        return;

    uint32_t page5 = page5_base[1];
    sync_access();
    result->page5 = page5;
    result->stage = J81_PAGE5_READ;
    if (!(page5 & (1u << 30)))
        return;

    uint32_t control = fender_base[0];
    sync_access();
    result->fender = control;
    result->stage = J81_FENDER_READ;
    sync_access();  /* Complete the RAM checkpoint before issuing the ID load. */

    uint32_t id = core_base[0x20 / sizeof(uint32_t)];
    sync_access();
    result->gpu_id = id;
    result->stage = J81_ID_READ;
}
