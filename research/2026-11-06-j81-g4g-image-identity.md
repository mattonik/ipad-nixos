# J81 G4G image identity

The private J81 image artifact is not an anonymous blob.  Its SHA-256 is
`314454e8d3179c255d704b6e481f971502bf7ec32f2a21b1345c6c8ba63534b8`, and
the embedded strings identify:

```text
Secondary loader stub 1.0.0.5
.../METAFW.build/g4g_a0/g4g_a0_t1.elf
.../METAFW.build/g4g_a0/g4g_a0_t0.elf
```

This establishes the J81 target family and the two META firmware images:
`g4g_a0_t0` and `g4g_a0_t1`, built by AppleEmbeddedGPUDrivers `50.6.10~3`.
It agrees with the J81 AGX symbols (`AGXMetaFirmware`, META boot/alive
handling) and is stronger than inferring the image family from the GPU name.

What it does **not** establish is which image is selected for which META
thread, where Apple places the secondary loader relative to the
`META_BOOTLOADER` slot, or how the packed image addresses are translated into
Linux/DART addresses.  The contract therefore narrows the remaining item to
“A8X META boot-descriptor ownership and image-to-slot binding”; no firmware
execution is enabled.
