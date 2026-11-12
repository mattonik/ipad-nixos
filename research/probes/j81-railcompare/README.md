# J81 iPadOS PMGR request-word comparison

This experimental 19H394 probe reads PMGR ordinary region 0 offset
`0x2300c` twice: after the GFX provider returns and after GPU identity.
The corresponding physical address `0x20e02300c` is a cross-reference
from the captured ADT, not an independently verified iOS mapping. The PMGR
object's lifetime and identity at the later hook are inferred. The existing
PMGR read method is used; no PMGR or GPU write is added by the probe.

Why this word: on a fresh Linux RAM boot with DWI on before GPC, it changed
from `0` before the GPC campaign to `0x164` afterward. A candidate PMU row
also changed from `00/40` to `64/64`. The observations were separate, and
the physical rail, actual voltage and bit semantics are unverified. iOS has
not yet been measured at this word. See the
[Linux result](../../2026-11-11-j81-dwi-gpu-comparison-result.md).

The first `Q=` follows `PAGE5-early-before` and the second follows
`PAGE5-before`; the names are retained from the parent probe. These are
different checkpoints from the Linux snapshots, not atomic measurements.
The iOS probe also logs the GFX provider, GPC and identity markers. Both
read results, those markers, a successful boot and firmware-startup message
are needed for a useful comparison. A missing marker or reboot is
inconclusive. Reads of this undocumented word may have side effects or hang
or reboot iPadOS, and early logs may be lost.

Interpretation and next actions:

* If iOS changes to a value other than Linux's post-GPC `0x164`, trace the
  field and iOS/bootloader producer and compare PMU state before proposing
  any Linux write. This is a candidate difference, not proof of causation or
  voltage.
* If both systems sample `0x164`, deprioritize this word as a direct
  discriminator. Matching requests do not prove matching rails or actual
  voltages. A later transition or checkpoint difference remains possible.
* If the iOS value changes between the two reads, that establishes a change
  during the broad interval, not that the GPC request caused it. If either
  read is missing, no conclusion follows.

The source is mechanically adapted from the hardware-run
[paired page-5 probe](../j81-page5pair/README.md): only the symbol prefix
and the two fixed offsets change. Native ARM64 host tests check the exact
read arguments, early/late order, one-shot behavior and absent-PMGR skip.
The KPF host harness accepted the target and rejected each of nine missing
and nine duplicate signatures and a wrong UUID. The final binary's two
fixed offset instruction pairs were checked. The pinned Pongo checkout is
documented in [the thread probe](../j81-thread/README.md); register
`j81_railcompare_capture` and use `KPF_CFLAGS=-DJ81_RAILCOMPARE_DEVICE_BUILD`.

The local module is
`artifacts/live/private/j81-ios-railcompare-probe/railcompare`, SHA-256
`5823515aa28d7345d50c998c13d9dcc0d684f2146729106166db40de740cfaaf`.
It has **not** been run on hardware. Verify the hash immediately before a
temporary rootless boot. Host tests do not establish live object lifetime,
MMIO safety, exact timing or log persistence. Keep complete archives private.
