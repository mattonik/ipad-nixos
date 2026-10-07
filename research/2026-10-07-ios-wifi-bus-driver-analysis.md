# iOS 8.1 Wi-Fi PCIe bus driver vs the Linux brcmfmac run: why the firmware ignores its rings

Date: 2026-10-07. Static analysis of the pinned iPad5,3 `12B410` kernelcache (flat `__PRELINK_TEXT` import, Ghidra helpers in
`tools/ghidra/`), prompted by wifi H1B run 3 (`2026-10-07-wifi-h1b-modelA-run.md`): no DMA error recorded anywhere, firmware alive,
MSI works, but the firmware never reads its host-to-device rings and had asked for deep sleep right after the doorbells. No hardware.

## What was found

The kernelcache contains Apple's own host driver for this chip: `AppleBCMWLANV2-354.8`, `AppleBCMWLANBusInterfacePCIe` (strings at
`0xffffff8002c16822`, source path `.../Busses/PCIe/AppleBCMWLANBusInterfacePCIe.cpp`) with `AppleBCMWLANChipManagerPCIe`. Key functions
(kernelcache addresses): shared-memory/ring setup `0xffffff8002c05974`; interrupt handler `0xffffff8002c02c84`; power-state machine
`0xffffff8002c0d0d0` (found only through a brute-force ADR scan, Ghidra had no function there).

### 1. Setup and doorbells: the same as Linux

Apple reads the shared structure from the device, maps the **H2D doorbell as core-3 (PCIe2) register `+0x140`** (Linux `h2d_mailbox_0`),
and the device/host mailbox data words from shared-structure fields `+0x28`/`+0x2c`, as brcmfmac does. At the end of setup it clears
the interrupt status (`+0x48 = 0xffffffff`) and sets the mask `+0x4c = 0x10100` (D2H doorbell 0 and FN0_0, a subset of Linux's mask).
Nothing in the ring programming explains the stalled read indices.

### 2. Deep sleep is a managed state in iOS, and it has a wake-up step Linux lacks

Apple's power-state function has four states (0 off/D3, 1 active/D0, 2 "active stay-awake", 3 "deep sleep permanent"). Entering 3
sends the **deep-sleep ACK** exactly as the host mailbox protocol defines it (mailbox word `= 2`) but signals it by writing **`1` to
core-3 `+0x144` (H2D mailbox 1, MMIO)**; Linux writes the same data word and then writes `1` to **PCI config space `0x98`**
(`BRCMF_PCIE_REG_SBMBX`). Leaving state 3 (back to active) does not just ring a doorbell: it calls a helper object (`param_1[0x1b9]`
vtable `+0x130`), then **waits up to about one second on a command gate for the device's "Deep Sleep Exit Notification"**
(mailbox bit 2) and logs `Timeout on waiting for Deep Sleep exit notification` (and can panic, boot-arg
`wlan.pcie.deviceWakeWaitBeforePanic`). The same driver counts DS requests, exits and doorbells per interrupt.

### 3. The wake source is a GPIO

The PCIe port driver reads `function-perst`, **`function-device_wake`**, `function-clkreq` from the port node
(`apcie` init, `0xffffff8002bed864`) and exposes **`setDeviceWake(bool)`** (`0xffffff8002bf0adc`, log text
`apcie[%u:%s]::%s DEVICE_WAKE = %d`) to the Wi-Fi driver through a port control function (tail-called from `0xffffff8002bf1040`).
The saved J81 ADT has `function-device_wake` on `pci-bridge1`: **OIPG pin `0xa5` (GPIO 165)**, flags `0x00000101` (compare
`function-perst` = pin `0xb3`, flags 0; `function-clkreq` = pin `0xae`, flags 2). Linux's DT and driver have never touched it
(`research/` notes from earlier called it "not required for basic link-up").

### 4. The NVRAM selects exactly that wake mode

The proven private NVRAM contains `device_wake_opt=1` and `host_wake_opt=0` (plus `uart_wake_gpio=2`, `btc_mode=1`). In Broadcom's
PCIe firmware `device_wake_opt` selects the dedicated DEVICE_WAKE pin as the way the host wakes the dongle from deep sleep. The
numeric values are not calibration; they are recorded here, the file stays private.

## How this explains run 3 (hypothesis, not yet tested)

1. the firmware boots, prints its banner, finds nothing to do, and **requests deep sleep** (`DEEP SLEEP REQ`, seen);
2. brcmfmac **acknowledges it** (config-space write, seen in the log: "sent DEEP SLEEP ACK") and the firmware goes to sleep;
3. brcmfmac then posts buffers and rings the in-band doorbell (`h2d_mailbox_0`), which, with `device_wake_opt=1`, **does not wake
   a deep-sleeping device**; the ring read indices stay at 0, the d2h scratch word stays 0, no DMA, no DART or PCIe error (nothing
   ever issued a transaction), and the control query times out at 2 s.

Everything observed fits: the interrupt path and host mappings are fine, the device is asleep. iOS never gets here because its power
state machine asserts DEVICE_WAKE and waits for the exit notification before using the rings.

## Experiments this suggests (test-only, switchable by boot arguments so one kernel serves all)

- E1: **do not acknowledge the first deep-sleep request** (log it only): the firmware should then stay awake; no new hardware access.
- E2: **drive DEVICE_WAKE (GPIO 165) high** from the controller driver (new `device-wake-gpios` on the root-port node) before brcmfmac
  loads the firmware, and keep it asserted: the same thing iOS does while the device is active. A GPIO write to the Wi-Fi module's
  wake input; polarity inferred from the ADT flags (`0x101`, perst's polarity is the opposite with flags 0) and from `setDeviceWake(1)`
  meaning "wake": it needs the user's explicit go-ahead like every hardware step.
- E3: send the deep-sleep ACK Apple's way (MMIO `h2d_mailbox_1`) instead of the config-space register, in case the config-space
  write is not what the firmware sees.

## Limits

The object at `param_1[0x1b9]` was identified as the wake helper from its position in the power state machine and from the strings and the
NVRAM option, not by following its vtable to `setDeviceWake`; the GPIO polarity is inferred. The ACK-register difference (config `0x98`
vs MMIO `0x144`) is documented fact, its effect is not. None of this was tested on the device.

## FUN_ffffff8002c0e27c: chip GPIO 0 drive (static, no hardware)

The function selects core index 0 (ChipCommon) and writes, in order:
`0xc40=0`, `0xe00=1`, `0x6c=0`, `0x68=1`, `0x64=(param==1)`.
In the standard Broadcom ChipCommon map `0x64` is `gpioout`, `0x68` is
`gpioouten` and `0x6c` is `gpiocontrol`. So Apple makes **chip GPIO 0 an
output** (control=0, outen=1) and drives it high or low. `0xc40` and `0xe00`
are not identified; they are probably pin-mux or function-select registers.
It records the level in the driver at +0xdd0, and temporarily clears and
restores the +0x7c1 flag (a vtable +0x98 call).

Callers:
- Power-state D0 path, when +0x1ba is set: called with 0 (GPIO0 low).
- `FUN_ffffff8002c10a24` (a vtable method, 28 bytes): called with 1 (GPIO0 high).
  Its caller is not yet identified.

Linux brcmfmac never touches chip GPIO 0 on this path. The rieslinga NVRAM has
no gpio keys; it has `device_wake_opt=1`, `host_wake_opt=0`, `uart_wake_gpio=2`,
`btc_mode=1`. The chip GPIO 0 line is probably routed to a module/coex signal
(possibly BT/WLAN coexistence). Whether it gates doorbell servicing is unknown.

Status: hypothesis only. A test would be a read-only ChipCommon
gpioout/gpioouten/gpiocontrol snapshot via the BAR0 window first. A write would
be an extra hardware action, so it needs the user's explicit go-ahead, and the
level to drive is not yet established.

## Follow-up leads after the GPIO snapshot (static, no hardware)

Runs 8/9 (ChipCommon GPIO snapshot, see `2026-10-07-wifi-h1b-modelA-run.md`) closed the GPIO side: chip GPIO 0
is already an output driving low (Apple's D0 level), and chip GPIO 1 is the DEVICE_WAKE input.

1. **Caller of `FUN_c10a24` (drives chip GPIO 0 high).** It is vtable slot 0x668 of the class whose vtable
   starts at `0xffffff8002c1d180` (slot address `0xffffff8002c1d7e8`; `c0e27c` itself is not in any vtable).
   A scan of PRELINK_TEXT for `ldr xN, [xM, #0x668]` finds 141 sites, none in the Wi-Fi kext range
   (`0x2bf...-0x2c11...`). The ones decompiled belong to unrelated classes (USB HID, PCIe link training).
   No caller can be attributed from the slot offset alone. Unresolved; low priority because GPIO 0 is low in both
   hardware runs and nothing in the GPIO block depends on the host.
2. **DMA-engine interrupt / coalescing registers (0x188-0x19c).** The register-name table lists them, but the
   decompiled Wi-Fi bus driver never writes them directly (only the literal writes below). Apple's literal
   register writes are: mailbox status/mask `0x48`/`0x4c` (setup: mask `0x10100`, then status `0xffffffff`;
   teardown: mask 0), ARM wrapper IOCtrl/ResetCtrl `0x408`/`0x800` (start sequence), mailbox `0x144` (DMB trap and
   deep-sleep ACK, value 1), and the core-0 GPIO block above. Nothing else is programmed by the host.
3. **`0xc40` / `0xe00`.** Only written inside the GPIO routine. The chip already holds `0xc40=1`, `0xe00=0x22000`
   (not 0 and 1) with GPIO0 driving low, so those writes look like part of the same pin setup rather than a
   requirement for the doorbell. Meaning still unidentified.

Net: Apple's host-side register protocol is no larger than Linux's. The mask (`0x10100` vs Linux `0x30300`) only
affects host interrupts, while the stall is the device-side latch (`h2d_mailbox_0` = 1 never cleared). The remaining
difference must therefore be in shared-memory content (ring/host-capability fields) or in the exact ordering
of the setup, not in extra registers.
