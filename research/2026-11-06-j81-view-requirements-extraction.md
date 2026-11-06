# J81 view-requirements extraction

`tools/gpu_g4g_extract_view_requirements.py` now parses the recovered iOS 8.1
AGX initializer without needing runtime addresses. It finds eight repeated
physical-I/O allocations:

```text
size source       multiplier   allocator flags   map selector
param[3]          0x6c         0x22              0x80007
param[4]          0x6c         0x22              0x80007
param[5]          0x6c         0x22              0x80007
param[6]          0x3594       0x22              0x80007
param[7]          0x6c         0x22              0x80007
param[8]          0x6c         0x22              0x80007
param[9]          0x6c         0x22              0x80007
param[10]         0x6c         0x22              0x80007
```

This tightens the host contract: the four-view model is a proven prefix, not
necessarily the complete allocation set. The extractor deliberately leaves
all mapped/backing addresses unresolved and remains execution-disabled. The
next adapter must identify which of these eight allocations are firmware
segments versus auxiliary/shared structures before constructing Linux DART
entries.
