#ifndef J81_FENDER_ID_H
#define J81_FENDER_ID_H

#include <stdint.h>

enum j81_sample_stage {
    J81_MISSING_MAP = 0,
    J81_PAGE5_READ,
    J81_FENDER_READ,
    J81_ID_READ
};

struct j81_sample {
    uint32_t stage;
    uint32_t page5;
    uint32_t fender;
    uint32_t gpu_id;
};

/* Caller owns three aligned Device mappings and a distinct writable RAM record. */
void j81_sample_fender_id(const volatile uint32_t *page5_base,
                          const volatile uint32_t *fender_base,
                          const volatile uint32_t *core_base,
                          volatile struct j81_sample *result);

#endif
