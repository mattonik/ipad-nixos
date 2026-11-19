# J81 core access after page 5 comes up

The new 19H394 iPadOS boot returned core ID 0x00070500. Its P0 field V1 is the MiscACG read at PMGR +0x32000 and equals 1. P0 precedes GFX power-on and the bridge plan. P1 V1 resumes its usual meaning (GFX VID 0x164). Page-5 +4 went from zero to 0x40000000 in all three post-poll samples. The GPC timing record is 0x3909 ticks; the raw final GPC state is absent from that record.

On Linux, the control returned zero twice for page 5. On two fresh boots with the isolated MiscACG change, the writer read back 1, page 5 was still zero before the GPC batch, and both post-poll samples were 0x40000000. The separate late-core boot reproduced that pair and later read GFX PS 0x3ff, GPC state 1, GPC control 0x40000000 and page-5 bit 30 high immediately before attempting the ID. No ID returned. The timed boot also reached state 1 and saw page 5 high before going silent. Both core attempts ended in reported watchdog resets. This moves the failure boundary beyond the observed GPC and page-5 transitions.

## Three offline checks

**Access and timing.** The working iPadOS capture maps physical 0x201000000 with length 0x1000, takes the non-null mapping path, adds 0x20, and calls a helper whose instructions are a 32-bit load followed by DSB SY. The Linux timed reader also maps that base and reads a volatile 32-bit word at +0x20, followed by DSB LD. Address and width agree. The iPadOS mapper runs after the page-5 test; Linux establishes its mapping before the GPC batch. Mapping attributes, translation and fabric state at access remain unverified. In the Linux source the counter sample t1 **precedes** formatting and emitting the final checkpoint, which precedes the load. The observed 46 ticks are about 1.92 microseconds at 24 MHz to t1. They do not timestamp the load. The successful iPadOS log timestamps also bracket software logging. Two Linux stalls at different sequence positions weaken the simple late-read hypothesis without excluding a narrower timing window.

**Post-enable startup dispatch.** In the exact stock kernel, constructor 0xfffffff006bb9104..9118 copies 0x460 bytes from 0xfffffff006fce4b8 to object +0x318. This table has 70 records of 16 bytes, each with a name pointer and initially zero state in the second eight bytes. Startup 0xfffffff006bb94e8..9538 looks up each name, marks successful lookup at record +8 and stores a 32-bit value at +12, with a possible later override. After the voltage-manager call at 0xfffffff006bcd100, the loop checks that valid byte, requires object +0xe4 clear and dispatches on whether the saved value is nonzero. I decoded all 70 name pointers and intersected them with the properties on the 19H394 J81 PMGR node:

| Index | Present property | Restore-tree value | Jump-table destination (low address) |
| --- | --- | ---: | --- |
| 2 | cpu-tvm | 1 | 6bccd34 |
| 3 | soc-tvm | 1 | 6bccd7c |
| 17 | dpe-thrtl | 0x2ee0 | 6bccc70 |
| 33 | noise-hack | 1 | 6bccef0 (return) |

The populated September J81 ADT text contains the same four named values. The stock table's gfx-tvm and gfx1-tvm entries (7 and 8) have no matching restore-tree property. Its gpu-trig through gpu3-trig entries (26–29) jump directly to the return in this dispatch. Of the 48 low indices in the byte jump table, 16 go directly to return; indices 48–69 also return in this function. This bounds **one** startup path. Runtime provider properties, earlier initialization and other methods can affect the resulting state. A GPU-looking name alone is insufficient reason to reproduce a write. Next trace the three non-returning matching cases to their actual register descriptors, beginning with soc-tvm.

**Register candidates.** Two existing J81 Linux captures already contain PMGR +0x1c300 = 0x40000001 (November 11 after-GPC1 and boot288e after-bridge10, both volman.log). This makes the quoted J96 value a poor discriminator by itself. The November 11 DWI campaign saw page-5 +0/+8/+0x18 at 0x1010/0x81480348/1 both before and after GPC, on a boot with +4 clear. Keep those separate from the new MiscACG-write boots. The page-1 and page-4 +8 words stayed at 0x80480348 and 0x88480348 on the successful Linux page-5 transition. Their Apple-requested high bits therefore are unnecessary for that transition in this recipe. Whether they matter for core access remains open. [Clock-word calculation](2026-11-19-j81-page1-page4-clock-control.md)

## Research order

1. Obtain the actual page-1/page-4 readbacks from the working J81 iPadOS boot or document the archive coverage gap. Ordinary store requests from another boot are insufficient. In parallel trace the three dispatch targets above and look for a J81 GPU or interconnect dependency. Compare only registers with established addresses and phases.
2. Compare the actual iPadOS mapper contract with the observer kernel's arm64 /dev/mem mapping path, including the type of device mapping and power/reset ownership of the core aperture. Separate CPU accesses from GPU DMA/DART accesses. Escalate a mapping difference only with evidence it changes the core transaction.
3. Revisit timing or extended Fender status if the first two comparisons identify a specific transition. A second identical ID attempt cannot distinguish the candidates. The next deliverable is an attributed difference and a predicted observation before another hardware trial.

All nine prepared/result packet manifests checked successfully. The table intersection and dispatch decode used the archived kernel with SHA-256 c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008 and raw J81 ADT be3158284d25e5d1217b970327ce2414d3046a2feb6a7b4410697b66df438003. No new device access was performed.

The [SoC TVM follow-up](2026-11-19-j81-soc-tvm-core-stall.md) resolves the index-3 dispatch to PMGR +0x2d000 and identifies which archived runs actually sampled it.
