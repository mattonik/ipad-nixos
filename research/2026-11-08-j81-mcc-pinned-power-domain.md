# J81 MCC power-domain policy in the pinned Linux tree

The J81 kernel's pinned T7001 device tree declares the MCC PMGR power domain
always-on. This narrows the interpretation of the saved zero read at
`0x200000830`, but does not establish that the domain was powered or the MCC
register interface initialized during that capture.

## Pinned source

`flake.lock` pins `HoolockLinux/linux` to
`6831bc701a6ce059e71e5aaa9488c9195bea6927`. Its `t7001.dtsi` includes
`t7001-pmgr.dtsi`; the J81 board DT uses the T7001 SoC description. In that
PMGR include, `ps_mcc` is `power-controller@20230`, with PMGR offset `0x20230`,
label `mcc`, and `apple,always-on`. The pinned Orchard Linux revision
`df7c930f80abd32a054617cd30ea450b7acfb3e0` has the same MCC stanza. The local
`kernel/hoolock.nix` starts from the pinned Hoolock tree and its patches do not
change this node.

The PMGR binding defines `apple,always-on` as forcing the power domain to
remain powered. The pinned PMGR driver sets `GENPD_FLAG_ALWAYS_ON`; if its
initial state is inactive, it warns and attempts to power it up. This is Linux
device-tree policy and expected driver behavior, not an Apple hardware
register specification.

## What the saved test boot shows

The Nov. 7 read-only Linux snapshot reports `Linux 7.3.0-rc1` and its captured
runtime device-tree inventory includes
`/soc/power-management@20e000000/power-controller@20230`, compatible with
`apple,t7000-pmgr-pwrstate`. Its FDT collection script records only
`compatible`, `reg`, `status`, `clock-names`, and `power-domains`, so that
snapshot does not itself preserve the boolean `apple,always-on` property or
the MCC PMGR state. The filtered dmesg shows PMGR activity for SPI, not an
MCC-specific state/readback. The later one-shot MCC read returned
`0x00000000` and completed cleanly; it did not inspect PMGR state.

Therefore the pinned kernel describes MCC as always-on, making ordinary
PMGR power-gating a less supported explanation for the zero than it would be
without this declaration. But the saved evidence does not prove the property
was present in that exact runtime FDT, that the MCC PMGR child successfully
probed or reached active state, or that `+0x830` has meaningful readback
semantics. Clock/reset state, MCC initialization/ownership, and register
semantics remain unresolved. No hardware access was performed for this note.

## Primary sources and local evidence

- [Pinned Hoolock T7001 SoC DTS](https://raw.githubusercontent.com/HoolockLinux/linux/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/boot/dts/apple/t7001.dtsi) — includes the PMGR DTS.
- [Pinned Hoolock T7001 PMGR DTS](https://raw.githubusercontent.com/HoolockLinux/linux/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/boot/dts/apple/t7001-pmgr.dtsi) — MCC domain declaration.
- [Pinned Hoolock PMGR power-state driver](https://raw.githubusercontent.com/HoolockLinux/linux/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/pmdomain/apple/pmgr-pwrstate.c) — `apple,always-on` behavior.
- [Apple PMGR power-state binding](https://kernel.googlesource.com/pub/scm/linux/kernel/git/next/linux-next/%2B/5358248961ae23f7253d010ddfde1cfd2556ce22/Documentation/devicetree/bindings/power/apple%2Cpmgr-pwrstate.yaml) — property description.
- [Pinned Orchard MCC stanza](https://raw.githubusercontent.com/OrchardLinux/linux/df7c930f80abd32a054617cd30ea450b7acfb3e0/arch/arm64/boot/dts/apple/t7001-pmgr.dtsi).
- Local pin/build path: [`flake.lock`](../flake.lock), [`kernel/hoolock.nix`](../kernel/hoolock.nix).
- Runtime snapshot: `artifacts/live/j81-readonly-20261107T114456Z/{kernel.txt,fdt_display_controller.txt,relevant_dmesg.txt}`.
- Read result: [`2026-11-08-j81-mcc-read-result.md`](2026-11-08-j81-mcc-read-result.md).
