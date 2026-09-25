# J81 Bluetooth bring-up: offline evidence and next gate

Date: 2026-09-25
Target: iPad Air 2 Wi-Fi, J81/J81AP, A8X/T7001
Scope: static repository, captured ADT, preserved iPad5,3 kernelcache and
upstream-source analysis only. No build and no contact with the live device.

## Result

J81 Bluetooth is a Broadcom HCI UART device on T7001 UART3. It is not a USB or
PCIe Bluetooth endpoint. The SoC-side UART, pinmux, PMGR power domain, H4/BCM
line discipline and 3 Mbaud transmit path have already worked on hardware.
The remaining first-order blocker is the radio's active-high `BT_REG_ON`
equivalent: D2207 PMIC GPIO2. Linux sends HCI bytes but receives none while
that line reads low.

The smallest credible Linux path is the existing Samsung/Apple S5L UART
driver plus serial-core serdev plus upstream `hci_bcm`/`btbcm`. A J81 serdev
child can use `brcm,bcm43540-bt`, `max-speed = <3000000>`, a future D2207
GPIO provider as `shutdown-gpios`, and AP GPIO164 as
`device-wakeup-gpios`. One baud-rate detail remains unresolved: upstream
`hci_bcm` sends its first command at 115,200 baud and treats `max-speed` as
the later operational rate, while Apple's ADT records 3 Mbaud. Do not add a
reset GPIO, host-wake IRQ, radio clock or named supply without new evidence:
none exists in the J81 ADT.

Firmware is a later gate. The controller currently fails before the first HCI
Reset completes, so Linux has not read its HCI revision or selected a patchram
filename. Do not guess the chip suffix or load a Wi-Fi firmware blob.

## Evidence ledger

### Captured J81 ADT: direct hardware description

The private capture is
`artifacts/adt/20260908T082112Z-j81.adt`, 357,402 bytes, SHA-256
`cf743765e66a1a5b45cbf4e18c0e5ae21454bb1cb678b66e7007e2db04f5b6c2`.
It contains device identifiers and radio calibration, remains Git-ignored,
and is not reproduced here.

Sanitized properties observed directly:

| Item | J81 value | Consequence |
| --- | --- | --- |
| Parent | `uart3`, `uart-1,samsung` | Bluetooth transport is UART. |
| UART MMIO | `0x20a0cc000`, size `0x4000` | Matches the implemented `serial3` node. |
| UART interrupt | AIC hardware IRQ 161 | Matches the implemented node. |
| UART clock gate | `0x53` | T7001 UART3 gate, separate from radio power. |
| UART pins | TX AP GPIO14 function 2; RTS AP GPIO32 function 2 | Linux needs these two mux entries and RTS/CTS flow control. |
| Child | `bluetooth`, compatible `bluetooth,n88` | Apple platform identity; not a Linux binding string. |
| Speed | 3,000,000 baud | Exact operational speed used by the proven `btattach` probe. |
| Encoding | `3` | Apple transport metadata; the repository's BCM H4 attach is the working Linux interpretation. |
| Radio wake | `function-bt_wake` -> AP GPIO164 | A host-driven wake output; see the Apple-driver evidence below. |
| Radio enable | `function-power_enable` -> D2207 PMIC GPIO2 | Separate active-high radio enable. |

The child has no `function-bt_reset`, interrupt, clock, regulator/supply or
second power resource. This absence is evidence against inventing those
resources, not proof that the package has no internally or board-supplied
clock and rails.

The Bluetooth and Wi-Fi functions of the combo radio use different host
transports. J81's Wi-Fi function is BCM4350 on T7000 PCIe port 1; that does
not make Bluetooth a PCIe device.

### Repository and hardware record: transport is already proven

Commits `858498a` and `7ad1718` record the existing UART3 implementation and
hardware observations:

- `apple,s5l-uart` registered `/dev/ttySAC1` at `0x20a0cc000` with flow
  control active.
- BlueZ `btattach -B /dev/ttySAC1 -P bcm -S 3000000` created `hci0` through
  `hci_bcm`.
- UART counters advanced to 14 transmitted bytes and zero received bytes.
- Vendor command `0xfc18` and HCI Reset timed out with `-ETIMEDOUT`.
- D2207 GPIO2 remained configured low throughout.

Creating `hci0` proves the host tty/line-discipline plumbing, not a live
controller. Zero RX and failure of the first reset response place the fault
before patchram lookup, Bluetooth address setup or BlueZ policy.

The built kernel's `System.map` contains `samsung_serial_init`,
`serdev_device_open`, `bcm_serdev_probe`, `bcm_setup` and
`btbcm_initialize`; no new transport driver is needed. The repository's
`btattach` remains useful as a diagnostic, but manual line-discipline attach
does not supply DT GPIO resources. The final implementation should use
serdev.

### UART power and clock dependencies

The current T7001 description places `ps_uart3` at PMGR power-state register
`0x201b8`, under the shared `ps_sio_p` parent. The UART node consumes that
domain and two temporary 24 MHz `clkref` handles (`uart` and
`clk_uart_baud0`) while relying on bootloader-enabled clocks. The successful
live probe establishes that this provisional SoC-side arrangement is enough
to access UART3.

This does not power the Broadcom radio. UART3 clock gate `0x53`, the
`ps_uart3` PMGR domain and D2207 PMIC GPIO2 are three distinct controls.

### Exact Apple power/reset/wake behavior from Ghidra

The preserved iPad5,3 iOS 8.1 (12B410) kernelcache was analyzed in the
existing Ghidra `prelinktext` project. Artifact SHA-256:
`19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`.
The exact prelinked AppleBluetooth image occupies
`0xffffff8002c4b000..0xffffff8002c4dfff`.

Its `BTReset::start()` behavior is:

1. Look up `function-bt_reset`, `function-bt_wake` and
   `function-power_enable` independently; every resource is optional.
2. If `function-power_enable` exists, invoke it with value `1` during driver
   start.
3. Expose `btwake`; opening it invokes wake with `1`, closing it invokes wake
   with `0`.
4. Expose `btpoweroff`; opening it invokes power-enable with `0`, closing it
   invokes power-enable with `1`.
5. Only when `function-bt_reset` exists, expose `btreset`; open invokes reset
   with `1`, while close waits 10 ms, invokes reset with `0`, then waits
   100 ms.

The public symbol-rich iOS 10.3 s8000 AppleBluetooth kext produces the same
control flow and cross-checks the stripped iPad5,3 decompile. Its public
artifact is at commit
[`96ca2b7`](https://github.com/userlandkernel/ios-unstripped-kexts/tree/96ca2b7f012ab20cf0274ea593d0e9a03f576764/kexts/10.3/s8000/AppleBluetooth.kext).

Two conclusions follow directly:

- AP GPIO164 is a host-to-controller wake output, so the Linux property is
  `device-wakeup-gpios`. It is not evidence for `host-wakeup-gpios` or an
  interrupt.
- J81 has no reset function in ADT, and Apple's generic driver tolerates that
  absence. Adding a guessed reset GPIO or copying the generic 10 ms/100 ms
  reset pulse into J81 would be wrong.

The decompile also changes the best passive-capture point. Apple asserts
power-enable when the AppleBluetooth driver starts, likely during boot. A
Bluetooth Settings toggle may not repeat that transition. Any future capture
must include cold iPadOS boot; a toggle-only capture can produce a false
negative.

### D2207 PMIC state: decoded but not controllable from current Linux

Existing AppleD2207PMU/AppleDialogPMU disassembly and the exact iPad5,3
kernelcache establish:

- PMIC GPIO2 configuration is register `0x03e6`.
- Function value `1` writes `0x02`, making the resource active high.
- Apple's I2C transaction is the three bytes `03 e6 02` with no CRC, bank
  switch, commit or unlock.

The repository has twice tried that byte-correct write under Linux. It was
ACKed but immediately read back as `0x00`, GPIO2 stayed low, and the radio
stayed silent. Setting D2207 `0x0010` bit 2 first did not change the result.
Those negative tests rule out malformed framing and that candidate master
enable. The remaining owner/state/lock condition is unresolved.

Do not repeat the write, try alternate PMIC bytes, or implement a GPIO
provider around a write that demonstrably does not persist.

### D2207 dependency result, 2026-09-25

The additional static review closes a tempting but unsupported explanation:
there is no evidence for a second J81 Bluetooth mux or supply callback hidden
behind PMIC GPIO2. The captured ADT contains one radio-enable resource, and
the exact AppleBluetooth start path invokes that resource with `1`; the D2207
driver converts it to the already-tested `03 e6 02` transaction. The same
Apple code has no GPIO-specific unlock, checksum, bank-select, or commit step.

The current blocker is consequently not a Linux driver design gap that can be
fixed safely in software. It is an unobserved PMIC state or bus interaction
that prevents an otherwise Apple-correct write from persisting under the
checkm8/Linux boot chain. The one evidence-producing next step is a passive
SDA/SCL capture covering a *cold iPadOS boot* through AppleBluetooth startup.
Record the transactions immediately preceding and following `03 e6 02`; a
Settings-toggle-only capture is insufficient because Apple asserts the radio
enable during driver start. Until that capture exists, no further PMIC write
or mux implementation is justified.

## Linux driver and DT path

The authoritative upstream pieces are already present in the pinned Hoolock
kernel:

1. `drivers/tty/serial/samsung_tty.c` for the T7001 `apple,s5l-uart` block.
2. Serial-core tty-backed serdev registration.
3. [`hci_bcm`](https://github.com/torvalds/linux/blob/aa98230e410f0ed212b6788c46b1e4d49e0ff7ca/drivers/bluetooth/hci_bcm.c)
   for H4 transport, baud changes, GPIO/clock/regulator sequencing and sleep.
4. [`btbcm`](https://github.com/torvalds/linux/blob/aa98230e410f0ed212b6788c46b1e4d49e0ff7ca/drivers/bluetooth/btbcm.c)
   for reset, revision discovery, patchram loading and controller finalization.
5. The upstream
   [`brcm,bluetooth` binding](https://github.com/torvalds/linux/blob/aa98230e410f0ed212b6788c46b1e4d49e0ff7ca/Documentation/devicetree/bindings/net/bluetooth/brcm%2Cbluetooth.yaml),
   which includes `brcm,bcm43540-bt` and makes shutdown, wake, reset, clocks
   and supplies optional.

Once PMIC GPIO2 can be controlled reliably, the minimum board child is:

```dts
bluetooth {
	compatible = "brcm,bcm43540-bt";
	max-speed = <3000000>;
	shutdown-gpios = <&d2207_gpio 2 GPIO_ACTIVE_HIGH>;
	device-wakeup-gpios = <&pinctrl_ap 164 GPIO_ACTIVE_HIGH>;
};
```

The provider syntax and phandles above are illustrative until a real D2207
GPIO provider exists. The evidence supports the consumer roles and
polarities, not those invented labels. A `bluetooth0` alias and the existing
m1n1 `local-bd-address` handoff should be added with the real child while
keeping the private address out of Git.

There is a small upstream integration gap to resolve before calling this
node complete. `hci_bcm` defaults `init_speed` to 115,200, reads `max-speed`
only into `oper_speed`, and for `brcm,bcm43540-bt` deliberately postpones the
baud-change command until after `btbcm_initialize()`. Thus its first HCI Reset
is sent at 115,200. The common serial binding defines `current-speed`, but
`hci_bcm` does not consume it. The ADT's `transport-speed = 3000000` proves
Apple's configured transport rate, but does not by itself prove whether a
cold power-on ROM first listens at 115,200. Resolve that from the Apple
transport client or a powered controller response; if the initial rate is
3 Mbaud, a narrowly scoped `hci_bcm` initial-speed property change is needed.

Do not use:

- `hci_bcm4377`, which is a PCIe transport for later Apple/Broadcom devices;
- `btusb`, because no USB Bluetooth endpoint is described or observed;
- `brcmfmac`, which owns the separate Wi-Fi PCIe function;
- a new J81-specific HCI driver, because upstream `hci_bcm` already covers
  the required UART protocol and resource model.

## Firmware path

Upstream `btbcm_initialize()` first completes HCI Reset and reads local
version/subversion. It then tries firmware names in this order for UART:

1. `brcm/<detected-hardware>.apple,j81.hcd`
2. `brcm/<detected-hardware>.hcd`
3. `brcm/BCM.apple,j81.hcd`
4. `brcm/BCM.hcd`

For example, upstream currently maps UART subversion `0x610c` to `BCM4354`,
but J81 has not returned a subversion. `brcm,bcm43540-bt`, Apple's
`bluetooth,n88` name and the combo module's Wi-Fi identity do not prove the
Bluetooth ROM revision. Wait for the kernel's exact requested filenames.

As of linux-firmware commit
[`a06a853`](https://gitlab.com/kernel-firmware/linux-firmware/-/tree/a06a853ae6c43f66bc0e3d3ba6d12efc5fd95c9c/brcm),
the `brcm/` directory does not contain a generic BCM4354/BCM4356 UART `.hcd`
patch. The likely source is the matching iPad5,3 iOS filesystem or an
equivalent locally extracted Apple artifact. Keep it outside Git, hash it,
and verify that it is an HCD command stream accepted by `btbcm_patchram`;
do not rename the BCM4350 Wi-Fi PCIe firmware or an arbitrary third-party
patch to satisfy the lookup.

Firmware cannot explain the current zero-RX failure: lookup occurs only after
the controller answers HCI Reset and version commands.

## Safest next experiment

The next experiment should remain fully offline and read-only:

1. Extract only filenames matching Bluetooth/Broadcom/patchram from the
   matching iPad5,3 iOS 8.1 (12B410) root filesystem.
2. Identify the userspace client of `/dev/btpoweroff`, `/dev/btwake` and, on
   boards that expose it, `/dev/btreset`, plus its UART baud setup. This
   determines whether J81 ever deasserts PMIC GPIO2 after the Apple driver
   starts and whether 3 Mbaud is the initial or switched rate.
3. Hash any candidate radio patch, inspect its header/command framing, and
   record a local conversion path to Linux HCD if needed. Do not bundle it.

This can resolve firmware provenance and power sequencing without touching
the iPad. It cannot explain why the byte-correct D2207 write is rejected in
the current Linux state.

If device work is later permitted and passive measurement hardware is
available, the only justified electrical experiment is an SDA/SCL capture
covering a full cold iPadOS boot through AppleBluetooth startup, optionally
followed by a Settings toggle. Look for `03 e6 02` and immediately preceding
transactions. This is observational and avoids another blind PMIC write. A
toggle-only capture is insufficient.

## Live read-only baseline, 2026-09-25

A fixed-command USB-network snapshot was collected from the running
postmarketOS payload. It made no configuration, PMIC, GPIO, or UART writes;
the D2207 reads use an I2C combined read transaction only. The private,
address-redacted capture is deliberately ignored by Git.

- The device identifies as J81 on Linux `7.3.0-rc1`.
- `ttySAC1` remains the registered UART3 device at `0x20a0cc000`, IRQ 48,
  with RTS/CTS flow control, and its counters are still `tx:0 rx:0`.
- No `hci*` device, `btattach` process, or previous attach log exists. The
  kernel has the generic H4 and Broadcom HCI UART protocols registered, so
  this is still pre-transport, rather than a failed firmware upload.
- D2207 configuration address `0x03e6` reads `00 00`, and GPIO data register
  `0x0063` reads `0x20`; its GPIO2 bit is low. This repeats the established
  no-power state without attempting to alter it.
- This minimal image does not mount debugfs, so it cannot provide fresh
  pinctrl or generic-power-domain detail. That absence is diagnostic-only and
  does not weaken the ADT and earlier live evidence.

This is a comparison baseline only. It supplies no rationale for another
PMIC write; the cold-iPadOS bus capture remains the next evidence gate.

## Evidence versus inference

| Statement | Status |
| --- | --- |
| Bluetooth transport is UART3 at 3 Mbaud with RTS/CTS. | Direct J81 ADT plus hardware proof. |
| UART3 MMIO, IRQ, clock gate, pins and PMGR domain are correct. | Direct ADT/repository evidence plus hardware probe. |
| H4/BCM Linux plumbing transmits but the controller returns no bytes. | Direct recorded hardware result. |
| D2207 PMIC GPIO2 is active-high radio enable and Apple writes `03 e6 02`. | Cross-checked Apple-driver disassembly. |
| AP GPIO164 is device wake, not host wake. | Direct AppleBluetooth call direction. |
| J81 needs no separate reset GPIO. | Strong: property absent and Apple's driver treats it as optional. Physical integration details remain undocumented. |
| J81 needs no explicit radio clock or named regulators. | Unknown; only their absence from ADT is proven. Do not model them yet. |
| The cold controller initially listens at 3 Mbaud. | Unknown; ADT proves Apple's configured transport rate, while upstream `hci_bcm` first uses 115,200. |
| The chip is specifically BCM4354 revision X and needs filename Y. | Unknown until the controller answers HCI version commands. |
| Firmware is the present blocker. | False; the failure precedes firmware lookup. |
| The rejected D2207 write is caused by runtime ownership/lock state. | Inference after framing and one candidate master-enable were ruled out. |
| Cold boot is the right passive-capture window. | Strong inference from AppleBluetooth asserting power-enable in `start()`. |

## Source anchors

- Pinned Hoolock kernel used by this project:
  [`6831bc7`](https://github.com/HoolockLinux/linux/tree/6831bc701a6ce059e71e5aaa9488c9195bea6927)
- Project implementation and captured results:
  [`docs/plans/2026-09-08-j81-bluetooth-battery-adt.md`](../docs/plans/2026-09-08-j81-bluetooth-battery-adt.md)
- UART3 DTS patches:
  [`0001-t7001-add-uart3-node.patch`](../kernel/patches/0001-t7001-add-uart3-node.patch) and
  [`0002-t7001-air2-enable-uart3.patch`](../kernel/patches/0002-t7001-air2-enable-uart3.patch)
- Upstream Linux sources are pinned above to `aa98230e410f0ed212b6788c46b1e4d49e0ff7ca`.
- Public AppleBluetooth cross-check is pinned above to
  `96ca2b7f012ab20cf0274ea593d0e9a03f576764`.
