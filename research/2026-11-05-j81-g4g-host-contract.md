# J81 G4G host contract: what can be reused (2026-11-05)

The offline 8.1/15.8.8 analysis and Orchard's current Rogue META loader now
separate the problem into a reusable part and a target-specific part.

## Reusable

J81's `AGXFirmwareKextG4G` image is a META LDR stream. The private 8.1 image
has the normal linked records (load, zero, config, comments, and a
`StartThreads` record), and the 15.8.8 image has the same container shape.
The 27 configuration writes are byte-identical between releases. Their
addresses include Linux-known META control/segment/cache registers, so the
inner command encoding and several register definitions can be shared with
`pvr_fw_meta.c`.

This is enough to justify an offline parser/translator, not firmware
execution. The existing `tools/gpu_ldr_inspect.py` is the correct boundary:
it validates links and ranges without exporting or running the proprietary
image.

## Target-specific host work still required

Apple's 8.1 setup does more than feed the LDR stream:

1. It allocates several aligned regions, creates two address views, and saves
   per-region bases/lengths in the accelerator object.
2. It interprets Apple's `ZeroMem` guard differently from Linux's core-memory
   mapping; records crossing the guard cannot be classified by a naïve whole
   range rule.
3. It copies load records into those mapped regions and verifies the copy.
4. It extracts a secondary-thread record into another structure. Linux's
   generic META path deliberately ignores `StartThreads` and constructs its
   own boot arguments, so that path cannot be assumed equivalent.
5. It builds a host boot/config area, then performs GPC/META readiness and
   firmware-alive waits through the G4G accelerator object.

The exact GPU physical-to-device address mapping for the allocated regions,
the shared-memory ABI after META start, and the 8.1 firmware-alive handshake
are still unresolved. Those are the real prerequisites for a driver; the
stock Linux firmware-header/BVNC checks and job rings cannot be bypassed by
recognising the LDR records.

## Implementation order

The smallest safe engineering sequence is:

* keep `gpu_ldr_inspect.py` as a no-execution validator;
* add an offline-only metadata report for Apple region classes, thread
  records, config targets, and Linux segment requirements;
* implement a private, compile-time-disabled host-layout adapter that accepts
  only synthetic LDR data until every address domain and allocation lifetime
  is proven;
* compare the generated boot/config words against the recovered Apple
  decompilation, without uploading them;
* only then design an operator-present firmware-alive test with a watchdog.

No current hardware test should read RGX, write GPC, upload firmware, or
start META. A successful PMGR reference and an LDR parser do not establish
that the A8X core is ready for those operations.

