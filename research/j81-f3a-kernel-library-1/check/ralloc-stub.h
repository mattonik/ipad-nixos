#include <stdlib.h>
#define reralloc(ctx, ptr, type, count) ((type *)realloc((ptr), sizeof(type) * (count)))
