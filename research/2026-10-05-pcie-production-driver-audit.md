# T7000 PCIe: static production-driver audit after DLLLA validation

Date: 2026-10-05. This is static research only. It reads the exact source tree
produced by the `0053` payload and the recorded hardware results; it performs
no build, boot, device action, or source change. It answers what can safely be
carried from the Stage-5 sequence into a maintainable J81 PCIe host driver and
what must stay explicitly unfinished.

## Baseline now established

The `0053` hardware result is decisive for link detection:

- board-local D2207 Wi-Fi `REG_ON` is asserted and verified at `0x0403`, then
  held for 100 ms before PCIe setup;
- the link-start write occurs at 0.3514 s and root-port DLLLA is set at 0.3574
  s (`LnkSta=0x3011`), about 6 ms later;
- generic enumeration immediately finds `14e4:43a3` behind `106b:1002`; and
- controller `+0x088=0x5` while DLLLA is set, so it is a controller state
  word, not a link-success bit.

The complete record is in
[`j81-d2207-gpio-register-correction.md`](j81-d2207-gpio-register-correction.md)
and the preserved host session is
`artifacts/live/sessions/20261005T071724Z-ead7dd92ea6547a3899274b82f174a8d/`.
That session records a host payload SHA-256 but, like earlier sessions, does
not independently prove the payload identity running on the tablet.

The reviewed final source is the output of
`kernel/hoolock-pcie-j81-dllla.nix`: patch chain `0016`, `0040`--`0045`,
`0052`, `0053`. The audit distinguishes **proven order/effect** from merely
**tolerated individual writes**; it does not imply upstream readiness.

## Write classification

| Operation | Evidence and current result | Production disposition |
| --- | --- | --- |
| D2207 Wi-Fi GPIO3 `0x0403`: `(old & 0x1d) \| 0x02`, verify, wait 100 ms | Board-specific Apple function decode and two successful enumeration runs; GPIO2 is untouched | Keep board-gated on `t7001-air2.dtsi`; retain fail-closed readback and intentional non-deassert policy. |
| Shared-window port-1 bootstrap: refclk/PERST/LTSSM writes and 10/100 us delays | Recovered from the iOS path; the order is hardware-proven with the endpoint now powered | Keep order and values verbatim. Do not generalize to ports 2--4. |
| Root-port Gen1 `LnkCtl2` RMW | Exact Apple `maximum-link-speed = 1` handling; endpoint is Gen1-only | Keep, but express it as a board/firmware constraint, not a generic performance preference. |
| DBI gate and three `dbi-overrides` RMWs | Exact J81 ADT records and Apple accessor mapping; safe in every successful sequence | Keep order and gate save/restore. Do not replace with direct per-port offsets or delete based only on individual tolerance. |
| Three direct `apcie-config-tunables` RMWs | Exact J81 ADT records and Apple order | Keep order and values. Their independent necessity is not isolated, but the working sequence depends on the complete ordering. |
| Port tail `+0x114/+0x104/+0x100` and MSI-controller `+0x124/+0x128` writes | Recovered Apple tail, then hardware-proven as part of the successful sequence | Keep the writes and ordering. Treat the `+0x100` readback of zero as its documented event/status self-clear/W1C behavior, not as a failed configuration write. |
| PERST# deassertion then link-start | Exact recovered ordering; DLLLA proves it reaches L0 with REG_ON asserted | Keep this ordering. |
| DLLLA wait via root ECAM | Hardware-proven; eliminates the old fixed half-second poll | Keep. A timeout remains non-fatal and enumeration is the final authority. |
| Controller `+0x88/+0x8c` output | Raw state is still undecoded and has been disproven as a success signal | Remove from normal `dev_info` output or retain only as `dev_dbg` while documenting it as diagnostic, never a decision input. |

The ADT records and their Apple access paths are detailed in
[`t7000-pcie-stage5-handoff.md`](t7000-pcie-stage5-handoff.md). The safe
cleanup principle is simple: **rename, structure and reduce logging without
changing the recovered writes, their order, masks, delays or port scope.**

## The two warnings: static resolution

### `retraining failed` is a generic PCI quirk, not a host-link failure

The final source sets root-port `LnkCtl2.Target Link Speed = 2.5 GT/s` because
Apple's J81 property requires it. Linux's generic
`pcie_failed_link_retrain()` then sees a downstream root port which both:

1. advertises a capability above Gen1 (the root port advertises 5.0 GT/s), and
2. is already restricted to Gen1 with DLLLA asserted.

That generic workaround assumes firmware may have left an unnecessary speed
restriction, raises the target to the root port's maximum, and retrains. The
BCM4350 only supports 2.5 GT/s, so that attempt fails and the quirk restores
the original Gen1 setting. The recorded final state is still link active,
2.5 GT/s x1, with the endpoint enumerated.

This is not a reason to remove the Apple Gen1 RMW, raise the BCM target speed,
or disable PCI quirks globally. Its observed cost is only a few milliseconds
after root-port discovery. A later **source-only** sub-study may determine
whether a narrowly scoped early Apple-root-port exemption is appropriate; do
not implement one until its execution point is proven early enough to affect
`pcie_failed_link_retrain()`.

### `iommu-map id 0x8` is an intentional non-match for the root port

The DT has `iommu-map = <0x100 &dart_apcie1 0 1>` and
`iommu-map-mask = <0xff00>`. The root port's requester ID `0x0008` masks to
zero, so it is deliberately outside the one-ID endpoint mapping starting at
`0x0100`. The BCM endpoint (`01:00.0`) does match and joined IOMMU group 0.
The root port itself does not DMA through the endpoint DART stream.

Therefore do **not** widen the map to include zero merely to silence this
message: that would attach an unrelated requester to the endpoint stream.
The warning is cosmetic for the present enumerating host. Its origin can be
documented/quieted only after a binding-level review; it is not a bring-up
blocker.

## Real production gaps

These are not fixed by replacing test log strings:

1. **MSI domain is absent.** The recovered hardware MSI registers are written,
   but the DT deliberately has no Linux `msi-controller`, `msi-parent` or
   `msi-ranges` implementation. The J81 ADT supplies the necessary starting
   facts: doorbell `0xbffff000`, 32 controller vectors, AIC vector offset 224,
   and port 1's eight-vector slice beginning at 8 (hence the proven
   `+0x124=0x31`, `+0x128=0x00080008` writes). The old tentative DT form was
   `msi-ranges = <&aic AIC_IRQ 224 IRQ_TYPE_EDGE_RISING 32>`, but restoring
   those properties without a Linux MSI domain would be invalid. Enumeration
   does not prove a future BCM driver can obtain interrupts. Before binding
   `brcmfmac`, turn these facts into a real IRQ/MSI-domain design.
2. **Power-management lifecycle is absent.** There is no proven suspend,
   resume, link-down, hot-reset, or unbind sequence. Keeping Wi-Fi `REG_ON`
   asserted is correct for this non-removable staging path, not a complete
   lifecycle design.
3. **The controller window overlaps the DART MMIO resource.** The non-exclusive
   `devm_ioremap()` is intentional and hardware-proven. Do not turn it into an
   exclusive resource claim; a future ownership/refactoring review must
   preserve the sharing arrangement.
4. **Port scope is J81 port 1 only.** The driver must not silently claim that
   T7000 ports 2--4 are supported. Keep a board-specific port model until
   evidence exists for the others.
5. **No endpoint driver has run.** Enumeration, BAR assignment and IOMMU group
   membership are transport milestones only; they do not validate DMA, MSI,
   firmware loading, NVRAM or Wi-Fi operation.

## Builder-ready cleanup boundary

The next implementation series may do the following without another hardware
experiment:

- squash/rebase the final working sequence into a clean driver source while
  preserving the exact write order above;
- replace `*-test` symbols and `dev_info` register dumps with durable names
  and `dev_dbg` diagnostics;
- keep explicit comments for the board-gated REG_ON action, overlapping DART
  window, J81 port-1 scope, and intentionally non-fatal DLLLA timeout; and
- retain the `0053` capability walker and DLLLA wait exactly as the link
  criterion.

It must **not** alter the Gen1 RMW, IOMMU-map range, DBI/tunable records,
port-tail ordering, PMU scope, or Bluetooth state. It must not claim MSI,
suspend or endpoint-driver support.

## Next static research deliverables

1. Turn the known J81 MSI facts (doorbell `0xbffff000`, 32 vectors at AIC 224,
   port-1 base 8) into a Linux MSI-domain design. Establish exactly which
   controller state the domain must own and a no-hardware acceptance matrix;
   do not restore DT MSI properties before that domain exists.
2. Trace the generic failed-link-retrain call order and identify whether a
   per-device exemption can run before it; compare the outcome against leaving
   the harmless restoration in place.
3. Produce the clean-driver patch review checklist: binding shape, port scope,
   error paths, lifecycle omissions and exact source-level assertions that
   prevent reintroduction of `+0x88` as a success test.

Only after those deliverables should the builder turn the staging sequence into
a long-lived driver. A later endpoint-driver probe remains a separate,
explicitly approved hardware step.
