# J81 bridge window consumer and upstream-map trace

Date: 2026-11-07

## Ownership from Apple call paths

The recovered physical address is `0x201f40000` (selector 9 base
`0x201f00000` + Apple table offset `0x40000`); selector 10 maps the analogous
word at `0x201fc0000`. This mapping follows the PMGR `bridge-reg-index` and
selector properties in the J81 ADT. It is not an offset into the GPU core
window (`0x201000000`) or GPC/Fender window (`0x201e00000`).

There are two Apple implementation paths in the local disassembly, at
different OS versions:

* The iOS 8.1 PMGR clock-table/provider path parses the selector tables and
  stores each offset/value pair through a mapped bridge region. The J81
  `device-clocks` record selects the GFX clock action; it is the only found
  driver-owned consumer of these `bridge-settings` tables in that kernel.
* In iOS 15.8.8, `AppleT7000`'s `FUN_fffffff006c961f8` selects the two table
  indices from the clock record and calls `FUN_fffffff006c97278`. That writer
  loads the selector's region pointer and performs plain 32-bit stores at
  `region + table_offset`; it contains no read/modify/write, mask, poll, or
  status readback. `AppleT7001PMGR` matches the J81 PMGR compatible and
  inherits the shared ApplePMGR provider plumbing. The shared PMGR bridge
  operation is exposed through provider vtable dispatch; it is not a DART
  routine or a GPU-core register accessor.

I searched the available iOS 8.1/15 decompilations and call logs for
`bridge-settings`, selector-table writer calls, and literal `0x40000` /
`0x40004` offsets. The only direct table application is the PMGR clock path;
the only other `0x40000` literals found in the T7000 clock code are unrelated
field updates to PMGR SoC registers `+0x20290` / `+0x20298` (mask
`0xfff0ffff`, set `0x40000`) in the GFX special-action path. Those are not
the selector 9/10 windows. Other iOS PMGR helper code can do read/modify/write
on dynamic register offsets, but no cross-reference connects such an
operation to table offset `0x40000`; it cannot be used as a field definition
for the J81 pair.

Thus the strongest supported classification is **PMGR-selected bridge
configuration window**, applied by a clock-provider state action. It does not
look like a DART register table or the separate SoC-tuner region. This names
the owning mechanism, not the hardware function of the word `0x007c7c01`.

## Upstream comparison and limits

The upstream Linux T7001 DTS describes PMGR at `0x20e000000` with size
`0x24000`, plus PMGR power-state child registers. It does not describe the
J81 bridge windows, a T7001 GPU/GPC node, or a GPU DART binding. The upstream
Apple DART driver operates DART's own mapped register block and IOMMU
stream/translation registers; its compatible table has no T7001 entry. The
J81 ADT has no GPU `iommu-parent`, DART phandle, SID, or DART range on `sgx`.
The `0x201f` bridge regions are therefore outside the presently documented
Linux DART contract. The T7001 PMGR DTS also has no bridge register
definitions, and the upstream Linux PMGR driver only models power-state/reset
registers; there is no field-level upstream register description to compare
against this table.

Sources:

* Private evidence: `artifacts/live/private/gpu-offline/clock-table.c`,
  `ios15t7000-special.c`, `ios15t7000-bridge-writer.c`,
  `ios15pmgr-bridge-use.c`, `ios15pmgr-bridge-access.c`, and the private
  J81 `ios81-dt.json` / captured Pongo ADT.
* Local upstream Linux checkout: `../orchardlinux/linux/arch/arm64/boot/dts/apple/t7001.dtsi`,
  `t7001-pmgr.dtsi`, `drivers/iommu/apple-dart.c`, and
  `drivers/pmdomain/apple/pmgr-pwrstate.c`.
* Public upstream mirror: [Linux T7001 DTS](https://gbmc.googlesource.com/linux/+/f79749a8e42b3a6dcb980e87f3ef752962b9f094/arch/arm64/boot/dts/apple/t7001.dtsi), [Apple DART driver](https://gbmc.googlesource.com/linux/+/976aa630da5b5508c278487db31b873ddf6bae8f/drivers/iommu/apple-dart.c), and [Apple DART binding](https://gbmc.googlesource.com/linux/+/refs/heads/linux-7.1.y/Documentation/devicetree/bindings/iommu/apple,dart.yaml).

## Consequence for the next observation

This trace narrows ownership but does not make one new write discriminating
enough to justify it. `0x201f40000` is the first configuration word in a
clock transition block and Apple uses a direct store with no local safety
check. No iOS caller reads or masks the entry to define its access behavior;
the public Linux map is silent on this block. A write/readback would at most
confirm retention, while still applying an uncharacterized clock-setup
setting. Do not run it without a register-level A8X contract and recovery
evidence for a stalled MMIO transaction.
