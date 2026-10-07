# C2 firmware (rieslinga) static analysis: first pass

Scope: the private `rieslinga.trx` image (hash pinned in `research/j81-private-firmware-assets.md`), analysed
locally in a Ghidra project outside the repository. No firmware bytes, decompiler output or project files are
committed; this note keeps only structure and conclusions. `tools/ghidra/ThumbSweep.java` is the new helper.

## Image format
- Raw Thumb-2 Cortex-R4 code, no TRX header, base address `0x180000` (confirmed: exactly one literal-pool word
  matches the image base plus the offset of each of two probe strings).
- Build string says `4350c2-roml/pcie-ag-msgbuf-splitrx-splitbuf-pktctx-proptxstatus-...` ("roml": a ROM-based build).
  The core PCIe msgbuf (pciedev) logic and the hnd/si helper layer are largely in the chip ROM, which is not part of
  the image, so the code that reads the host doorbell and consumes the rings cannot be read from this file. Only the
  RAM patch layer is visible.
- The feature string includes `splitrx-splitbuf`, a split-RX msgbuf variant. Linux brcmfmac was written for the
  non-split variant; Apple's driver comments mention separate RX completion handling.

## What is visible
- `pciedev_probe` equivalent at `0x1dfd6c` (allocates a 0x50-byte device struct, vendor id 0x14e4, registers the
  "pciemsgbuf%d" device).
- A mailbox/doorbell event dispatcher at `0x185a78` (RAM patch): it takes a pending-event bitmask and handles bit 0
  (deep-sleep related path), bit 1, bit 2, bit 31, and bit 29 ("Forced TRAP via mailbox"). After the first run it
  programs the PCIe interrupt mask from device state: `0x20000` when a capability bit (bit 17 of a device flag word)
  is set, `0x300` otherwise.
- Ring name table (`h2dctl`, `h2drx`, `d2hctl`, `d2htx`, `d2hrx`) at `0x1df4d0`, and debug strings `h2d_drbl: %u`,
  `d2h_drbl: %u`, `ds_enter_req`, `ds_exit_notify`, `DS_*` deep-sleep states, `device_wake_opt`, `host_wake_opt`.

## Conclusions
- The code that decides whether to service the host doorbell is in ROM and cannot be examined here. Static analysis
  of this image can confirm names and structure but cannot, by itself, explain the stall.
- The remaining plausible explanations are host protocol details the ROM expects (for example the `splitrx`
  variant's extra host-capability or ring-info fields, or host-ready signalling) that neither Linux nor my
  Apple-parity toggles provided, or a hardware precondition outside the registers compared so far.
- Next options that do not need a ROM: (a) compare the shared-structure fields that exist only in newer protocol
  versions (host capabilities, host-ready doorbell) against what this build advertises in its flags word; (b) dump
  and inspect the firmware-owned shared structure in TCM after boot, read-only, to see which fields the firmware
  populated and which it left zero; (c) check whether Apple writes anything to the shared structure beyond
  offsets 0x34-0x3c in `FUN_c05974`, which the earlier pass covered.
