# Providing the Wi-Fi MAC address: how the firmware gets `macaddr`

Background: the live-RAM analysis (`2026-10-08-live-ram-device-state-analysis.md`) found that the C2 firmware's `wl` core fails
to attach when the NVRAM has no `macaddr` key, so the PCIe interrupt is never enabled and the host's doorbell is ignored.
The staged NVRAM (`P-rieslinga_M-CIDR_V-u__m-2.1.txt`, 156 keys) has no `macaddr` line. The test payload M1 appends a
locally administered test MAC in the private assembler (`--nvram-macaddr`). This note covers the permanent route. No MAC
value appears here or anywhere in Git; MACs stay in private artifacts only.

## Where Linux and Apple get it
- **Linux brcmfmac** (`brcmf_fw_nvram_strip` in `firmware.c`): if `eth_platform_get_mac_address(dev, mac)` finds an address for the
  PCI device (the device-tree `local-mac-address`/`mac-address` of the endpoint's OF node, or nvmem), it removes any `macaddr`
  from the NVRAM text and appends `macaddr=<that MAC>`. With no platform MAC, the NVRAM's own line is used, and it is absent here.
  An all-zero `local-mac-address` is treated as invalid (placeholder).
- **ADT (the iPad's device tree from iBoot):** `/chosen` has `mac-address-wifi0`, `mac-address-bluetooth0` and
  `mac-address-ethernet0` properties (names confirmed in the captured J81 ADT; values are device identifiers and are not
  recorded). The `wlan` node also has a `local-mac-address`, and a `device-mac-address`/`host-mac-address` pair exists for
  another node.
- **m1n1** (Asahi lineage) copies `/chosen/mac-address-<name>` into a `local-mac-address` property on the device-tree node that
  the alias `<name>` points to. Our `t7001.dtsi` comment already notes this for `bluetooth0`: there is no alias yet, so it
  has no node to attach to. Same for `wifi0`.

## Why the device tree cannot do this yet
- The kernel enumerates the Apple root port at `00:01.0` (106b:1002) and the endpoint at `01:00.0` (14e4:43a3). Our DT root-port
  node is `pci@0,0` with `reg = <0x0 ...>`, which corresponds to device 0 and therefore does not bind to the real bridge at
  device 1. An endpoint child node needs a bridge node that matches (`pci@1,0`, `reg = <0x800 ...>`) with a child
  `network@0,0` (`reg = <0x10000 ...>`, `compatible = "pci14e4,43a3"`).
- The same `pci@0,0` node carries the hardware-proven `reset-gpios` and the test `device-wake-gpios`, and the driver's
  `pci_host_common_parse_ports()` walks it by `device_type = "pci"`. Changing its `reg` could break the proven link bring-up, so
  it needs a hardware run to validate; it is not something to do blind.

## Options
1. **Private assembler adds it (done for the test):** `--nvram-macaddr` appends a test MAC; a variant that reads the real MAC
   from the private ADT capture is easy and keeps public builds MAC-free. Good enough for all bring-up runs. Not suitable for
   a distributable image.
2. **Device tree + m1n1 (proper):** add `wifi0` alias, a `pci@1,0` bridge node (or retarget the current node after validating
   the port parser) and an endpoint `network@0,0` with a zero `local-mac-address` placeholder; m1n1 fills it from the ADT and
   brcmfmac writes it into the NVRAM. Needs: a DT patch, a hardware run to confirm the port still comes up and the node binds
   (`/sys/bus/pci/devices/0000:01:00.0/of_node`), and confirmation that the prebuilt Hoolock m1n1 performs the alias copy.
3. **Small kernel fallback:** if no platform MAC exists, have brcmfmac fall back to a MAC taken from the root port's OF node
   (or generate a random locally administered one). Simple, but it papers over a missing binding.

Recommendation: finish bring-up with option 1 (M1 first), then do option 2 as a normal DT change once the Wi-Fi path works, so
the validation run can also check the node binding.

## Cross-check of the attach path (ROM + original image, Ghidra)
Decompiling the bmac attach `FUN_001e74ac` (called from `wlc_attach` `FUN_001e482c`, probe `FUN_001e323c`) with the chip ROM
imported at 0x0 confirms the agent's finding: near its end the function looks up the MAC variable; if the lookup returns
nothing it returns **0x15**, and if the value is the all-zero or a multicast address it returns **0x16**. All other NVRAM reads
on this path use the integer-variable getter with a default (they do not fail when a key is missing); the other error returns
(0xc, 0xd, 0xe, 0xf, 0x11, 0x12, 0x13) come from allocation and core-setup steps, not from NVRAM. So `macaddr` is the only
NVRAM key this attach path requires, and the test MAC (unicast, locally administered) satisfies both checks. Note for future
analysis: the firmware reclaims its init code after boot, so the live RAM has zeros there; use the original image for code and
the live dump for state.
