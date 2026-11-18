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
