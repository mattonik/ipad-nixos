# J81 GFX power requests before the first GPU identity read

The working iPadOS boot reported GFX PMGR poll value `0x000003ff` and first RGX identity `0x00070500`. Linux reached the same PMGR sample in a separate capture and produced no identity result. The exact stock driver and pinned Linux driver predict different **requested words** immediately after that poll under one specific starting condition. The next measurement is the old word, target, poll and auto-enable request in order for PMGR region 0, offset `0x20320`, instance 0. [Working and stalled captures](2026-11-10-j81-ios-linux-poll-result.md)

## What the drivers predict

Assume an initial word of `0x00000300`, requested state 15, auto-enable requested and a successful poll returning `0x000003ff`. The initial word is the Linux cycle module's entry requirement. Its value at entry to the stock setter and the exact Linux poll return in that setter are unmeasured. These are conditional source predictions, separate from the published endpoint samples.

| Operation | J81AP 19H394 iPadOS | Pinned Linux with cycle patch |
| --- | --- | --- |
| Request active | Clear gate-history bits 9:8 and insert target 15. Write `0x0000000f`. | Clear auto-enable, gate-history and target fields. Insert target 15. Write `0x0000000f`. |
| Poll for active | Mask `0xf0`, expected `0xf0`. | Compare ACTUAL bits 7:4 to 15. |
| Request automatic management | Use the saved request from before the poll. Set bit 28. Write `0x1000000f`. | Use the successful poll result. Clear bits 9:8 and set bit 28. Write `0x100000ff`. |

The XOR of the final requests is `0x000000f0`, entirely in the ACTUAL field. Both set the same target and auto-enable bit. Whether the hardware acts on writes to ACTUAL is unestablished. Treat a difference confined to those bits as a fingerprint of the software paths. It gives no basis by itself for changing Linux. Preserve the raw poll, order, and any additional edge when comparing traces. [Pinned Linux setter and bit definitions](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/pmdomain/apple/pmgr-pwrstate.c#L19-L106) · [Cycle build](../kernel/gpu-pmgr-cycle/build.nix) · [Local patch 0123](../kernel/patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch)

Other starting conditions matter. The stock setter can return early for an already matching target and mode. If it takes the transition path with bit 28 already set and the old target equal to 15, it can first clear auto-enable and poll ACTUAL for 15. For a new target below 15 the ordinary target write at the site below sets both gate-history bits. Linux clears those bits in its target request. Identify an actual off/on transition before comparing that case. A successful get → put → get on the Linux consumer records runtime-PM API success and a final held reference. The domain callback and its actual write count must be observed separately. [Linux consumer](../kernel/gpu-pmgr-cycle/gpu-pmgr-cycle.c)

### Recheck on the matching stock image

Select J81AP from the 19H394 BuildManifest. SHA-256 of the **decompressed kernelcache** is `c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008`. In that image the increasing-state caller at `0xfffffff006bd8770` derives the auto-enable argument from record flags. PMGR's setter takes its original word at `0xfffffff006bc714c`. For the case in the table, follow the requested word in W24 through the ordinary write at `0xfffffff006bc7268`, the actual-state poll at `0xfffffff006bc7294` and the next write at `0xfffffff006bc735c`. W24 survives the poll. Its post-poll value comes from clearing history and setting bit 28. With LLVM tools and a matching local file, inspect the paths with these read-only commands. [Apple restore image](https://updates.cdn-apple.com/2025FallFCS/fullrestores/082-67137/2FF7F5F3-3900-4F6D-BBDF-A68EEBE7B83F/iPad_64bit_TouchID_15.8.5_19H394_Restore.ipsw)

```sh
llvm-objdump -D --start-address=0xfffffff006bd8760 --stop-address=0xfffffff006bd879c "$KERNELCACHE"
llvm-objdump -D --start-address=0xfffffff006bc714c --stop-address=0xfffffff006bc7364 "$KERNELCACHE"
```

## Which domains appear in the ordinary-store export?

The J81AP member `Firmware/all_flash/DeviceTree.j81ap.im4p` has SHA-256 `864839f20f6b18185914dd6acdf930c226d16645658b2bca8a890ee1cb25ed6d`. Its decompressed tree hashes to `be3158284d25e5d1217b970327ce2414d3046a2feb6a7b4410697b66df438003`. In the SGX node, clock-gates and power-gates each contain LE32 `0x7c`. The exact board also has two LE32 ones in `gfx-qos`. A literal search of the matching kernel found no occurrence of that property name. Its consumer and relevance to pre-identity startup remain unknown.

To reproduce the lookup, use the PMGR node's 4704-byte `devices` property. It holds 98 records of 48 bytes. In each record, the name begins at byte 32, the lane is byte 10 and the bank index is byte 11 (all offsets decimal). Index `ps-regs` as triples of little-endian 32-bit words. For an enabled lane, the region is word 0, and the offset is word 1 plus eight times the lane. GFX is record 80, ID `0x7c`, bank 3, lane 4. Bank 3 contains `(0, 0x20300, 0x1f)`, giving GFX offset `0x20320`. This is the device-tree power-state table. The separate 44-byte `device-clocks` records describe clock metadata. [Clock record decoder](../tools/gpu_apple_clock_model.py)

| Reported region-0 offset | J81 device name |
| --- | --- |
| `0x20100`, `0x20108`, `0x20110` | LIO, IOMUX, AIC |
| `0x20120`, `0x20128` | DWI, GPIO |
| `0x201a0` through `0x201e0`, stride 8 | UART0 through UART8 in order |
| `0x201f0` | SIO |
| `0x20320` | GFX |

These names account for the visible `0x201xx` offsets. The prior prefix also includes MCC/control-bank work. The legacy formatter supplied fixed ordinary-row thread and instance tags, and 15 staged slots are unaccounted for in the reported tail if its header matches the sampled producer. The table identifies offsets; neither device ownership of a particular write nor absence of a GFX request follows from it. [Published rows](2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md) · [Coverage and normalization rules](2026-11-18-j81-gfx-transition-builder.md)

## An earlier write to look for in the working driver

On the increasing-state path, the stock caller can issue a **minimum-state request before entering the setter** in the table above. In 19H394 the caller takes the flags from record byte 0 and the minimum nibble from byte 15. In the J81 GFX `devices` row both bytes are zero. With flag bit 2 clear, `0xfffffff006bd876c` calls `0xfffffff006bc6da0`. After its bank, lane and instance checks, that helper reads the old word and tail-calls the ordinary writer at `0xfffffff006bc6e84`. For minimum zero the requested word is `old & 0xfff0fcff`. On input `0x300` that gives **`0x00000000`**. The helper has no equality check to skip the write when the minimum already equals zero. The main active-state setter subsequently reads its own old word. Its entry value must be observed separately. This independently checks the [earlier 19H422 reconstruction](2026-11-09-j81-pmgr-clock-reset-path-correction.md#additional-power-state-operation) on the target build and board record.

The pinned Linux `ps_gfx` node declares its label, address and power/reset providers. It has no `apple,min-state` property. Linux programs MIN at provider probe only when that property exists and has a valid value. Its normal active setter has no equivalent explicit MIN request. Check the *effective* DTB when comparing a private build. If an early zero-valued request appears, retain its old value, caller and successor. Calling it “power-off” from the word alone would discard the discriminator. If MIN and TARGET were already zero, the extra write proves a difference in the software transaction sequence. Its electrical effect remains open. [J81 power node](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/boot/dts/apple/t7001-pmgr.dtsi#L607-L613) · [Linux provider initialization](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/pmdomain/apple/pmgr-pwrstate.c#L217-L250)

Two independent implementations use bits 7:4 as observed state. Asahi's m1n1 requests the target and polls ACTUAL. Its legacy device-tree decoder also selects the power-state bank and adds eight times the lane, matching the exact-board lookup above. OpenBSD's enable routine changes the target nibble, preserves the other read bits and polls the actual nibble. Both projects implement explicit reset in separate routines. These sources corroborate the field interpretation but neither measures whether J81 ignores writes to ACTUAL or whether the stock GPU required a reset. [m1n1 power-state setter](https://github.com/AsahiLinux/m1n1/blob/ce2b8a43cea4220b602af1005dc9dbfc59c9624e/src/pmgr.c#L86-L100) · [m1n1 address lookup](https://github.com/AsahiLinux/m1n1/blob/ce2b8a43cea4220b602af1005dc9dbfc59c9624e/src/pmgr.c#L123-L141) · [OpenBSD power and reset](https://github.com/openbsd/src/blob/04c139adb022989174988750a28751dce8a02cad/sys/arch/arm64/dev/aplpmgr.c#L157-L226)

## Test necessity against the earlier successful boot

On November 14 at 20:57 local time the project recorded an early manual recipe at successful `ApplePMGR::start()` return on iPadOS. The same boot logged pre-request `S=00000300`, three page-5 samples with bit 30 set, and `CORE=00070500`. That successful identity predates the normal AGX provider trace. The published capture does not enumerate the PMGR write arguments. Its private sampled binary is identified publicly only by prefix `0a20ead8`. This makes it a better control for *necessity* than comparing terminal state words from separate OS boots. [Run 3 primary report](2026-11-14-j81-ios-boot-bisect-probe1-results.md#run-3-module-0a20ead8-time-based-gpc-poll-boot-2057-the-core-answers) · [Later evidence qualifications](2026-11-15-j81-entry-gpc-offline-review.md#what-the-controls-establish)

Match the successful archived binary and build record, then recover the manual recipe's requests from the existing material. If it reached identity without issuing the MIN or auto-enable request in that sequence, downgrade that operation as an indispensable **per-acquisition** step in that startup context. Earlier platform initialization can still supply the prerequisite. In that case, prioritize the state already established by the end of PMGR startup. A design note or absence from the legacy callback log is insufficient to establish the operation's omission. The Linux observer can still determine which setter calls and edges actually occurred.

One further address distinction is worth preserving. After the two startup `0x1008` and `0x4008` operations, the exact stock method calls a parent method and then uses separate 64-bit helpers with selector 8 and offsets `0x78`, `0x68` and `0x20`. The helpers use an internal descriptor (`0xfffffff006bc75e4`, pointer at descriptor +0x18). The raw J81 PMGR ADT resource at ordinal 8 overlaps the ISP node. The helper selector alone establishes neither that ADT mapping nor a GFX register. This is an offline mapping question. The observed GFX requests remain the comparison target.

The [November 19 startup trace](2026-11-19-j81-pmgr-start-resources.md) resolves logical selector 8 to resource 1 and places the CPU table update after the voltage-manager seed.
