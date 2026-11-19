# J81 startup enables MiscACG before the working GPC request

**ApplePMGR requests bit 0 at physical 0x20e032000 while GFX can still be off. Linux has a saved zero at that exact address after GPC state 1.** The stock driver's own diagnostic calls the method `ApplePMGR::enableACG(bool)` and the group `kRegGroupMiscACG`. This is a candidate prerequisite for the later page-5 response. There is no post-start MiscACG readback in the five markers from the successful November 14 recipe, and no experiment here establishes which clocks the group controls. [GFX startup state](2026-11-19-j81-gfx-startup-state-producer.md) · [Working recipe](2026-11-14-j81-ios-boot-bisect-probe1-results.md)

## Trace in the decompressed J81AP 19H394 kernel and ADT

Code addresses below omit the common prefix `0xfffffff00`. Offsets in the PMGR register block are relative to physical 0x20e000000.

| Stage | Evidence |
| --- | --- |
| Describe the register | Before ADT initialization, slot +0x590 resolves to `6c884cc`. The call at `6c88548` passes group 9, selector 0 and offset 0x2d000 + 0x5000. Its thunk loads the pointer at `6fe5d58` to `6bbf784`, which sets the valid byte at object +0x2310 + 0x18 × group and stores the offset eight bytes later. For group 9 these fields are +0x23e8 and +0x23f0. |
| Enable the group | On the returning startup path, GFX lane replay precedes `6bcd0ec`. That call uses instance slot +0x690 with argument 1. The target `6bcf3c8` checks group validity at `6bcf544`, loads its offset and reads the old word via `6bcf55c`. At `6bcf560..564` it calculates `(old & ~1) | enable`. With enable=1 it requests `old | 1` via `6bcf580`. The two helpers select region 0, instance 0 and use the mapped 32-bit read/write methods. Reg[0] length is 0x40000. There is no poll or verification of this store on the traced tail. |
| Identify it independently | The invalid-group diagnostic at `6bcf584 → 6be8734` references both the method and group names. Group 9 here is an index in the driver's register descriptors. The GFX bridge selector numbered 9 addresses different hardware. |
| Order it against the voltage operation | Slot +0x698 receives 1 at `6bcd100`, after the MiscACG call. It enables the voltage manager and seeds the CPU/SRAM words. GFX's software byte can be zero throughout both operations. Neither operation directly writes page-5 +4. [Startup call chain](2026-11-19-j81-pmgr-start-resources.md) |

The subclass also requests `(old & 0x3fffffff) | 0x40000000` at +0x1008 and +0x4008 before calling the parent. Applying that transform to the archived Linux words 0x80480348 and 0x88480348 yields 0x40480348 and 0x48480348, exactly the two ordinary-store requests seen in a separate iPadOS window. These are page **1** and page **4** configuration words. The comparison establishes two more startup fingerprints; their effect on page 5 is unknown. Later in the method, slot +0x9a8 can restore saved values at +0x10208 and +0x10050 when nonzero and poll bit 30 **clear at those addresses**. It supplies no direct rising-bit operation at +0x5004. [Captured prefix and coverage](2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md) · [Six-page clock calculation](2026-11-09-j81-llb-page5-clock-dataflow.md)

## Compare the observed phases

| Run and phase | MiscACG +0x32000 | GPC and perf | Page-5 +4 |
| --- | --- | --- | --- |
| November 15 iPadOS entry control | Read **0**. The archived control reads PMGR +0x32000 at its offset 0x4270 and prints the value as `r9`. | Entry snapshots precede the manual GPC request. | Entry control reads 0. |
| November 14 iPadOS successful end-of-start recipe | Static startup request sets bit 0. Runtime value unknown. | Poll exited on `(raw & 0x1f) == 1`. Perf 0x80000000 → 0x80110100 and GFX VID 0 → 0x164. | 0 before request, then 0x40000000 in three samples following the timing log. Core ID 0x00070500. |
| November 11 Linux post-GPC collection, `pmgr-words-20261111-after-gpc1` | **0** in `volman.log`, with VM control 1, GFX VID 0x164 and perf 0x80110100 in the same completed readout. | Collection labeled after GPC1. | 0 in sibling `plls.log`. These are separate commands. |
| November 11 Linux DWI comparison, `dwi-gpu-compare-20261111-01` | Omitted from this campaign's sample. | Raw GPC=1 at poll 11. Perf and GFX VID make the same transitions as in the working recipe. PMU row 0x0128 bytes 0 and 2 change from 00/40 to 64/64. | Both paired samples zero at +709 ns and +101834 ns after the poll, and zero in the saved 10-second follow-up. |
| Separate bare PongoOS control | Unknown. | GPC state 1 and perf 0x80110100; GFX VID remains zero. | Three zero samples. [Pongo result](2026-11-16-j81-pongo-gpc-page5-result.md) |

The DWI comparison shows that Linux can complete the GPC request, update the perf state and GFX VID, and change the candidate PMU bytes while page 5 stays clear at every sampled point. The PMU bytes are digital readbacks. The iPadOS and Linux sample times differ; neither trace establishes continuous state between samples. The historical recipe's `G=30303000` comes from the logging buffer and supplies no Fender readback.

The 19H422 iBoot and LLB static indexes each contain a store of zero to 0x20e032000 (at 0x87001528c and 0x180390f5c respectively). This is compatible with the zero entry observation on 19H394; it does not identify which bootloader path actually ran. The Linux T7001 power-domain description documents the per-domain PS controls. It gives no functional assignment from MiscACG bit 0 to the GFX PLL. [Linux T7001 power domains](https://gbmc.googlesource.com/linux/+/f79749a8e42b3a6dcb980e87f3ef752962b9f094/arch/arm64/boot/dts/apple/t7001-pmgr.dtsi)

## Offline verification and next decision

The digest-pinned [startup audit](../tools/audit_j81_pmgr_start.py) checks method slots, instruction anchors, diagnostic names and the register translation. The two arithmetic instructions also passed 131,072 native ARM64 cases over both Boolean arguments. The existing [reader's host test](../boot/test_pmgr_words_peek.py) checks that offset 0x32000 maps the expected physical page read-only and returns the synthetic word. All tests ran without device access.

The next discriminator is a **working-boot, post-start, pre-GPC MiscACG value**, or an attributed write during startup followed by a later readback. The prior replay-caller check can proceed independently. If the working readback has bit 0 clear, the hypothesis that a *retained* 1 is necessary loses support; a transient effect would need distinct evidence. If it is set and a matched failing Linux pre-request read is clear, the setting becomes a candidate for a separately reviewed single-variable experiment. If both have it set before the request, prioritize the page-1/page-4 configuration and fabric differences. A staged store establishes a requested value only. A capture that omitted the address leaves the question open. [Builder handoff](j81-gpu-builder-handoff.md#compare-miscacg-with-the-page-5-outcome)

The [page-1 and page-4 follow-up](2026-11-19-j81-page1-page4-clock-control.md) checks both requests against the recovered clock-rate calculation, the populated arm-io table, and the platform-active callback.

The [four-report mailbox review](2026-11-19-j81-gpu-mailbox-review.md) records the later iPadOS control and read-probe boots. Both reached the Home screen. The post-enable register value remains unknown.
