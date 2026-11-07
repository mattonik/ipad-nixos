# J81 MCC mode-4 read interpretation (2026-11-07)

Offline follow-up to `2026-11-07-j81-mcc-ios81-record-stride.md` and
`2026-11-07-j81-mcc-physical-address-audit.md`. No device access or MMIO was
performed.

## Selector-4 write signature

The 12B410 selector-4 code reads mapped `+0x830`, writes
`0x55 | (old & 0xffffffe0)`, reads it again, then writes
`(old & 0xfffffeff) | 0x100`. Therefore selector 4 deterministically sets bits
0, 2, 4, 6, and 8; it leaves bit 5 and bits 9..31 unchanged. In particular,
its post-write masked signature is:

```
value & 0x15f == 0x155
```

The instructions establish these bit effects, not meanings such as a cache
mode, enable, or validity flag. The software mode field is the low five bits
(`0x15` after this record), but the unmasked `0x55` also sets bit 6. Do not
interpret the signature as proof that the hardware accepted or is operating
in a semantic “mode 4.”

A lone read can at most say whether the current word is consistent with this
write signature. It cannot establish that selector 4 ran: startup, firmware,
or another writer could leave the same bits. A before/after pair bracketing a
known, independently logged display-idle 1-to-0 event would distinguish a
change to this signature from a stable value, but still would not identify the
writer or prove the callback's success. Attribution needs the callback/result
state or a trace of the actual read/modify/write path. The existing one-shot
Linux capture reads only once, so it is a baseline raw observation, not an
MCC mode-transition test.

## Clock/reset evidence and read limits

The saved Linux runtime inventory (`artifacts/live/private/gpu-observations/clock-reset-inventory-2026-11-05.txt`)
shows no MCC device node or MCC clock/reset references. It does show generic
PMGR reset-controller nodes, the GFX genpd provider, and a command line with
`clk_ignore_unused`; none maps an MCC clock/reset ID or proves the MCC block's
power state. The iOS 8.1 provider path reviewed in the stride note maps its
`reg` resource and performs PRAM/setup plus MCC register accesses; the
available disassembly does not identify a named MCC clock or reset operation.
This is absence of an identified dependency in these artifacts, not evidence
that the block has no power/clock prerequisite.

Thus the available evidence does not establish that a missing clock/reset
blocks a read, nor that a raw read is safe or guaranteed to complete. The
translated address is Apple-source-derived, while Linux does not publish the
range in `/proc/iomem`; reservation only checks Linux's resource tree. A
powered-off/nonresponsive peripheral could still hang the access. The current
acknowledged, watchdog-supervised one-read path limits the experiment but
does not remove that hardware risk. Keep the planned read gated and do not
add guessed clock/reset writes or MCC programming.

Evidence checked: the two cited offline MCC notes; the saved 2026-11-05
clock/reset inventory; `kernel/mcc-read-once/mcc-read-once.c` and
`research/2026-11-07-j81-mcc-probe-preparation.md` for the one-shot read's
scope and watchdog boundary. REA was not needed: the original 12B410
instruction evidence is already recorded with tool, addresses, and provenance
in the stride note.
