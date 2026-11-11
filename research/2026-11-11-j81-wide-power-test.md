# J81 20-domain restore comparison

This experiment restores the 20 power-state words from the earlier Linux
boot's genpd accounting, then repeats the DWI/PMU/GPC comparison. It is a
broad state change, not a claim that iPadOS held all 20 domains on or that
any particular one controls the GPU. It does not read the GPU core.

The captured Pongo ADT's 48-byte `devices` records list `SIO_P` as parent of
I2C1–3 and UART1/2/4/6/7/8, `USBCTRL` as parent of USB2HOST0–2, USB as parent
of USBCTRL, and ISP as parent of VENC. In this captured tree, `ps-regs` and
the eight-byte stride map the external SIO_P, USB and USBCTRL parent words to
PMGR offsets `0x201f8`, `0x20248`, and `0x20250`. The campaign reads these
three and requires their actual state to be 15 before any restore, and checks
them again after GFX/bridge setup. ISP is restored before VENC. This is an
ADT-based dependency check, not proof that every dependency or side effect is
known. Domain state words are sampled again immediately before GPC and twice
afterward, not monitored continuously.

The pinned `pmgr-ps-restore` binary only accepts its 20 fixed names, reads
all 20 first, then requires a separate host acknowledgment for each needed
write. The host validates each name, address and state, refuses reset,
parent-off and device-disable bits, and stops if a write does not reach 15.
It logs and flushes before each acknowledgment. It does not change PMU voltage
values or explicitly access GPU core registers. Direct `/dev/mem` power-state
writes bypass the kernel genpd lock/accounting and differ from the kernel's
full power-on sequence; they can interact with devices and power control. They
are not automatically undone. The PMU snapshots use the previously sampled
four 8-byte I2C rows, including register-address selection and `-f`; these
reads may have side effects and interfere with a bound driver.

After all domains are on, the existing GFX PMGR cycle, bridge setup and
watchdog-supervised paired GPC/page-5 test runs. Every one of the 20 restored
words and all three external parents must report active immediately before the
GPC request. PMGR and PMU snapshots and domain states are recorded after it
and again ten seconds later. The boot ID and staged file hashes are checked
throughout. A failed or incomplete stage stops the campaign; do not retry on
the same boot.

Run only on a fresh cycle-payload RAM boot:

```sh
cd /tmp/j81-dwi-gpu-compare
python3 boot/j81_wide_power_compare.py artifacts/live/gpu/wide-power-NEW
```

`NEW` must be unique. Local private bundle hashes are verified before the
first action; the restore binary SHA-256 is
`90474674554b3e3abac9f15e3d5d189b43a8a816feddf97dacdb8a32286f1d18`.
The 20-domain tool passed its original host test; the host supervisor tests
correct order and acknowledgments, invalid baseline, incorrect domain, stall,
already-on and full-state snapshot behavior. Existing DWI and GPC tests pass.
These are offline/mocked checks: the 20-domain write sequence has not run on
the device. The one-at-a-time writes, PMU reads and parent checks are not
watchdog-supervised. A hung access may not be recovered by watchdog or reset.

If the page-5 bit changes, identify the responsible domain with controlled
follow-up boots; a broad positive is not proof of causality. If it remains
clear, this sampled set was not sufficient under the test conditions; it does
not rule out clocks, voltage, resets, provider history or transitions that
occurred between snapshots. A missing result is inconclusive. Private logs
remain in `artifacts/live/gpu/` and should not be published wholesale.
