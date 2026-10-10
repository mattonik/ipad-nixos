# J81 base package: what every build always carries

## Why
Experiment payloads were each built by copying the minimal `m1n1-hoolock-control` recipe. The Wi-Fi H1B payloads therefore had no
boot-time charging (their kernels lacked patch 0017, so `input_current_limit` was read-only), no SSH, no tablet tools, and only the
stock debug-shell hook. The tablet payload had those but was a separate, differently derived build. The base package makes the
useful set the default for every payload that is meant to be run.

## The five always-on pieces
| # | Piece | How it is guaranteed |
|---|---|---|
| 1 | **Charging** | kernel carries `0017` (writable `input_current_limit`) after the base patches; `/usr/bin/charging-policy` (2400 mA, backs off to 500 mA at 42 C / 80 %) is started by the boot hook; sysfs only, no I2C tools |
| 2 | **Telnet + SSH** | the `ssh-stage1.sh` hook: telnetd recovery on 172.16.42.1:23, key-only Dropbear on :22 (public key in `boot/ssh/authorized_keys`), over the ECM USB link |
| 3 | **Debug console** | bootargs `console=tty0 loglevel=8 ignore_loglevel rdinit=/init PMOS_NO_OUTPUT_REDIRECT pd_ignore_unused clk_ignore_unused`, postmarketOS debug-shell flow |
| 4 | **Tablet overlay** | `/usr/bin/tablet-status`, `/usr/bin/tablet-dashboard` (read-only status screen; run on demand) |
| 5 | **Universal probe** | stage B below; today's Wi-Fi-specific query interface is the prototype |

## How it is enforced
- **Payload:** `mkJ81BasePayload { name, kernel, bootargsExtra }` in `flake.nix` builds the standard layout (Pongo, m1n1, DTB fix, debug
  initramfs plus one overlay with items 1-4). New payloads call it instead of copying a recipe. The Wi-Fi H1B payloads (model A and B)
  are the first users. No Bluetooth userland and no I2C tools are included (the Wi-Fi payload rules forbid them).
- **Kernel:** the base patch set is `0001-0011` plus `0017`, in that order, at the start of the kernel recipe.
- **Tests:** `kernel/test_j81_base_contract.py` (offline suite) fails if a listed kernel recipe drops a base patch, if `mkJ81BasePayload`
  loses any overlay piece or bootarg, or if a listed payload stops being built through it. `boot/verify_pcie_j81_reg_on_payload.py`
  (`j81_base_problems`) checks the built payload: executables present, the hook has telnetd + dropbear + charging-policy, the
  authorized key and the Dropbear binary are in the initramfs, the kernel has the J81 charger driver, the bootargs are intact.
- Historical one-off payloads (ANS1, PCIe stage tests, ...) are left as they are; only new/run-on-hardware payloads must use the base.

## Stage B: universal probe (not built yet)
Today's query interface lives inside brcmfmac (patches 0071-0073) and only exists in the Wi-Fi test kernel. Proposal:
- A small always-built core, `drivers/misc/j81-probe.c`, creating `/sys/kernel/debug/j81-probe/{targets,query,result}` and a registration
  API. Drivers register **targets** with their own allowlist of what may be read (the Wi-Fi driver keeps its safe-register list, the
  gated ROM reads, `snap`/`diff`, `arm`, `shared`), so a probe is safe by construction and nothing here writes a register.
- Generic targets that need no device driver: `pci` (config-space dumps of any device, using the PCI core), `dt` (read a device-tree
  property), `sys` (kernel log, interrupts, clocks/power domains as already exposed), and a `ram` snapshot/diff helper.
- A userland wrapper in the base overlay (`/usr/bin/j81-probe`) and a host tool replacing `boot/h1b_query.py` with the same allowlist
  validation. Results land in a private, ignored folder as today.
- Migration: move the brcmfmac query code onto the registration API without changing its commands, so recorded workflows keep working.
Open decisions for Martin: whether the probe core should be allowed to carry any MMIO-read targets beyond drivers' own allowlists (the
default proposal: no; each block's driver owns its safe list), and whether `tablet-dashboard` should start automatically on the screen.

## Status
Stage A (items 1-4 for the Wi-Fi payloads, tests, verifier) implemented 2026-10-08; stage B designed only.

### Stage A build record
Base payload (Wi-Fi H1B model A, kernel with 0017): `/nix/store/nvp2sdsxvpidnscfkm05mjcnknsv90g1-ipad-air2-m1n1-hoolock-pcie-j81-wifi-h1b-base`, `m1n1-linux.bin` 12,689,385 bytes (the existing tablet payload is 12,706,466).
Payload verifier (`--wifi-h1b-base`, now including `j81_base_problems`) passes; offline suite 54 passed, 0 failed, 7 skipped.
Private test payload M2 = this base + `h1b_hold=1` + `device_wake=1` + the test MAC (supersedes M1, which lacked the base package).

## Item 6: Wi-Fi (added 2026-10-10, to do once the production Wi-Fi payload is established and tested)
Request from Martin (2026-10-10): once the base is established and tested, revisit this base package with all the working pieces already in, and bundle in the Wi-Fi.
State on 2026-10-10 (research/2026-10-10-wifi-bringup-root-cause-and-permanent-fix.md, runs 38-44 in research/2026-10-07-wifi-h1b-modelA-run.md):
- Working and device-tree driven: brcmfmac PCIe, the DART options (`apple,ios-pte`, `apple,pci-alias`, error-reflector/fetch/diag-config), the `wifi0` endpoint node whose MAC m1n1 fills, link bootargs `pcie_aspm=off pcie_apple_t7000.device_wake=1`.
- Working userland: static `iw`/`wpa_supplicant`/`wpa_cli` (flake `wifi-userland-static`), `boot/wifi-up.sh` (association with retries, then DHCP; started by the public boot hook when `/usr/bin/wifi-up` exists), `boot/wifi-udhcpc.script`; 5 GHz ~178 Mbit/s down, 2.4 GHz ~50 Mbit/s.
- Production kernel/payload `m1n1-hoolock-wifi` (diagnostic code compiled out, quiet logs) built through `mkJ81BasePayload`.
To bundle into the base (mkJ81BasePayload) as the sixth always-present item:
1. Make the production Wi-Fi kernel the base kernel (it must keep patch 0017 for charging; `kernel/test_j81_base_contract.py` enforces that) and move `pcie_aspm=off pcie_apple_t7000.device_wake=1` into the base bootargs.
2. Put the public, generic Wi-Fi userland (iw, wpa_supplicant, wpa_cli, `wifi-up`, `udhcpc.script`) into the public base overlay; relax the assembler's "no Wi-Fi client tools" rule to "tools identical to the flake package".
3. Keep private: firmware/CLM/TxCap/NVRAM (overlay by the assembler, as today) and the credentials file (`--wifi-credentials`, mode 0600, never recorded). A base without credentials simply does not connect; `wifi-up` logs that and exits.
4. Show the Wi-Fi state (SSID, signal, address) in `tablet-status`/`tablet-dashboard`, and let the universal probe query it.
5. Tests: contract test that the base carries the tools and the hook line, a test that a base without credentials boots and does not start wpa_supplicant, and a hardware pass with the full base (charging + telnet/SSH + console + dashboard + Wi-Fi).
Open: whether the base should also carry a regulatory database, and the default behaviour for several remembered networks (current private file: 5 GHz hidden network first, 2.4 GHz fallback).
