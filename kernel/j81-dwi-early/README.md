# J81 early DWI comparison (experimental)

Paired RAM payloads use the same patched kernel, DTB, Pongo, m1n1 and
initramfs. Their only intended difference is `j81_dwi_hold=0` versus `1`.
The kernel logs the DWI state before and after probe changes and on the
power-off callback. The hold mode rejects only that callback for a J81
`dwi` provider with the expected compatible and offset. It does not prevent
auto-gating or another writer, power the domain on, change the GPU, or
establish uninterrupted pre-kernel state.

Host checks:

```
python3 kernel/j81-dwi-early/test.py /path/to/pinned/drivers/pmdomain/apple/pmgr-pwrstate.c
python3 kernel/j81-dwi-early/verify.py /path/to/control /path/to/hold
```

For each fresh boot, record payload digest, boot ID, `/proc/cmdline`, full
early kernel log and `j81-dwi` lines. Treat a missing line, nonzero register
read error, mismatched identity/bootargs, or DWI off at entry as inconclusive.
Capture genpd state and vetted PMGR words at matched times using the existing
acknowledged read-only sampler. Do not issue GPC, GPU-core or PMU accesses in
the first comparison. The test changes power policy and can hang or reboot;
prior recovery does not guarantee that all failures are recoverable. See
`research/2026-11-13-j81-early-power-audit.md` for interpretation and limits.

The recipe consumes the pinned once payload only for Pongo, m1n1, bootargs and
initramfs. It builds a separate kernel and DTB; it does not restore or replace
the missing cycle payload. Do not use modules built for an earlier kernel
without checking their compatibility against this specific build.

The previously used statically linked sampler is available locally at
`artifacts/live/private/j81-pmgr-words-bundle-v1/pmgr-words-peek`, SHA-256
`b58d2ada974d3f0c280ee24f494ad17c7b2b252cf06fa00575b04a1c54618502`.
Recheck the digest before staging. For this comparison select only PMGR
`20120`, `2300c` and `5004`; the tool requires a `READ` acknowledgment and
never writes the mapped registers. A successful sample does not prove that
state remained unchanged between observations.

## Built 2026-11-13

- Control: `artifacts/live/j81-dwi-early-control`, combined-image SHA-256
  `c4ff7308eb9e7f5932e317fd78590e79713f353cb182a19e871de896562684f7`.
- Hold: `artifacts/live/j81-dwi-early-hold`, combined-image SHA-256
  `24c43c226656fea6d5eef3ab2ca4ae46f550672a5763dd85bede8bbbe49e09ce`.
- Both use Pongo SHA-256
  `1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575`,
  kernel `Image.gz` SHA-256
  `b21ce434b2ddbf8f4bfc5bb9897daf66ea8ce9b0b8ddf7f3cfa32d2917ea4bc1`,
  and instrumentation patch SHA-256
  `3504512b2531b1ac5e93cef491d5f0ff229b055bc5c14474a52ebf2247b67bac`.

The paired payload verifier, source patch application, callback behavior and
sampler host tests passed. The kernel configuration has
`CONFIG_APPLE_PMGR_PWRSTATE=y`, and the built image contains the probe log and
boot-argument strings. The generated DTB matches the test kernel DTB except
for the existing payload builder's `/chosen/framebuffer@0` → `framebuffer`
rename. DTC emitted PCI/GPIO warnings during the existing decompile/recompile
step; the semantic comparison did not find other changed nodes or properties.
These are host checks only: neither image has been booted on the iPad.
