# Wi-Fi H1B campaign summary (2026-10-06 .. 2026-10-08)

> Superseded for current state by [`2026-10-09-wifi-h1b-handoff.md`](2026-10-09-wifi-h1b-handoff.md) (runs 15-30, the `macaddr` fix, and the open hard-reset problem).

Goal: get the BCM4350 (PCIe `14e4:43a3`, C2 stepping) to complete brcmfmac's first control exchange (`cur_etheraddr`
query over the msgbuf rings, completed via MSI slot 8 / AIC 232) with the private C2 `rieslinga` firmware.

## Result so far
**Root cause (strong evidence, hardware test pending): the NVRAM has no `macaddr` key, so the firmware's `wl` (D11) core fails
to attach (bmac attach returns 0x15), the firmware never runs the pciedev `open()` that unmasks the PCIe2 interrupt, and the
host's doorbell is ignored.** Evidence: `research/2026-10-08-live-ram-device-state-analysis.md` and
`research/2026-10-08-wifi-macaddr-provisioning.md` (live RAM interrupt-mask fields all 0; stale return address after the
`macaddr` lookup; PCIe2 IntMask 0 with IntStatus bit 16 pending; no `macaddr` in the 156-key NVRAM; ROM decompile confirming
0x15 for a missing MAC). Test payload M1 adds a locally administered test MAC; run it next (see "Next").

## Hypotheses tested (all negative before the root cause), with run numbers in `2026-10-07-wifi-h1b-modelA-run.md`
| Hypothesis | Test | Outcome |
|---|---|---|
| DMA translation / DART / MSI path | Model A (rebase), Model B (raw), ring/IOVA/DART logging | host side correct; same stall (runs 1-7, 11) |
| Deep-sleep ACK | stock / none / MMIO ACK (`h1b_ds_ack`) | no effect (E1, E3) |
| DEVICE_WAKE GPIO 165 | `device_wake=1` | keeps firmware awake (DS request disappears); no effect on stall (E2, E2b) |
| ASPM / L1 | `pcie_aspm=off` | no effect (E4) |
| Chip GPIO 0 / ChipCommon GPIO block | read-only snapshot (0069) | firmware sets GPIO0 output low as Apple does; GPIO1 = DEVICE_WAKE input; closed (runs 8-9) |
| Shared-memory differences vs Apple (scratch 4 KiB, no ring-update buffer, Apple ring depths) | `h1b_apple_shared=7` (0070) | no effect (run 10) |
| Ring id/type words (Apple writes, Linux leaves 0) | `h1b_ring_ids=1` (0072) | written and read back; no effect (run 13) |
| Firmware dead/trapped? | `snap`/`diff`/`arm` (0073) | alive: timer words tick, ARM CR4 up, no trap (run 14) |
| PCIe2 interrupt masked inside the device | read `0x20`/`0x24` | IntStatus 0x00010000 pending, IntMask 0: confirmed masked; explained by the missing `open()` |

## What was built (all test-only, off by default)
Kernel patches `0061`-`0073` (see `kernel/hoolock-pcie-j81-wifi-h1b.nix` for the order): metadata probe, OTP shadow capture, DART
window/rebase (Model A), brcmfmac diagnostics, DART/port debugfs, wake/ACK toggles, console poll, ChipCommon GPIO snapshot, Apple
shared-memory parity toggle, **read-only debugfs query interface** (`/sys/kernel/debug/brcmfmac-h1b/{query,result}`; `tcm`, `core`,
`shared`, `rings`, `console`, `snap`, `diff`, `arm`, gated `unlock rom`/`rom`), hold toggle (`h1b_hold=1`, device stays bound for
queries), ring-id toggle, safe-register list. Host tools: `boot/assemble_private_wifi_payload.py` (private overlay, allowlisted test
bootargs, `--nvram-macaddr`), `boot/h1b_run_record.py` (read-only capture), `boot/h1b_query.py` (allowlisted queries, `--allow-rom`),
`tools/ghidra/ThumbSweep.java` (raw Thumb firmware import). Offline suite: 53 passed, 0 failed, 7 skipped.

## Hardware safety lessons (each cost a reboot or nearly did)
- **Window-moving register reads are only safe at known registers.** A sweep of PCIe2 `0x00-0xff` through the BAR0 window killed the
  USB link and rebooted the iPad (run 12). The driver now limits `core` reads to a safe list (PCIe2 `0x20 0x24 0x48 0x4c 0x140 0x144`;
  ChipCommon GPIO block, `0xc40`, `0xe00`).
- **BAR2 reads past the mapped ROM reboot the device.** The aperture ends at 0xA0000 (ROM 0x0-0xA0000, RAM from 0x180000). The chip ROM
  was dumped in 4 KiB steps up to that point; the first read past it rebooted the iPad. Never read beyond the dumped range.
- The firmware reclaims its init code after boot (live RAM is zero there); static analysis of code uses the original image, runtime
  state uses the live dump.
- Use `/opt/homebrew/bin/python3` (3.14) for `boot/*.py` and `tools/check_offline.py`; the system `python3` is 3.9.6 and fails the console
  tests (`X | None` syntax).

## Next
1. Run M1 (`wifi-h1b-modelA-M1-macaddr-hold-devwake-...`): expect `wl` console output, shared flags `0x10005`, non-zero IntMask,
   advancing read indices, and possibly a completed control query. Confirm with `snap`/`diff`, `shared`, `core pcie2 0x20/0x24`.
2. If it works: provide the MAC permanently (device-tree route in `2026-10-08-wifi-macaddr-provisioning.md`, option 2), then
   permanent DEVICE_WAKE handling, then drop the test toggles from the build.
3. If `wl` still fails to attach: the firmware console / `diff` will show where; the ROM dump (private) and the original image are in
   the Ghidra projects in the scratch directory.
