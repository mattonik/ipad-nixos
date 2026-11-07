# J81 G4G contract assessment

The new execution-disabled contract tool was run against the existing private
J81 image `artifacts/live/private/gpu-offline/g4g81-image.bin` (SHA-256
`314454e8d3179c255d704b6e481f971502bf7ec32f2a21b1345c6c8ba63534b8`).

Observed metadata:

```text
LDR records:       80
load bytes:        85,980
configuration writes: 27
modeled Apple host state: APPLE_HOST_ACCEPTED
execution_allowed:   false
```

The assessment reports `firmware_handshake_ready=false`: the modeled Apple
host state is not evidence that Linux delivered event 0. These gates remain
unresolved:

1. Apple callback registration/event producer/interrupt source and the Linux completion adapter.
2. J81 META-address to Linux GPU-address mapping.
3. A8X META boot-descriptor ownership and image-to-slot binding (image family
   is now identified as `g4g_a0_t0`/`g4g_a0_t1`).
4. DART mappings and command-buffer ABI.

This is useful progress: the image is structurally parseable and its modeled
alive transition is coherent, but no firmware bytes were copied or executed.
The next offline implementation should resolve the four view base/backing
pairs from the iOS 8.1 allocator trace before any loader stub is considered.
