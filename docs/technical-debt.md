# Technical debt

Known shortcuts and loose ends that do not block current work. Each entry says what it is, why it was left, and what fixing it involves.
Add new entries at the end; strike an entry through when it is done.

## 1. `wifi-up` starts about 17 s after boot (recorded 2026-10-10)
- **What:** `wlan0` exists about 0.6 s after boot (the firmware is up at 0.59 s), but `/usr/bin/wifi-up` is started from the boot hook
  (`etc/postmarketos-mkinitfs/hooks/20-debug-shell.sh`), which the initramfs only reaches after about 17 s. Association then takes about 3 s, DHCP about 1 s.
  So the iPad is online at about 20 s, where the radio could be ready at about 5 s.
- **Why left:** it does not bother the user at this stage (decision 2026-10-10: record it, fix it when the basics are done). Everything works.
- **Fix:** start `wifi-up` earlier. Options: an earlier initramfs hook; or move the start into the kernel-side (a udev-style wait on `wlan0`); first measure what the
  initramfs does between 0.6 s and 17 s (probably the debug-shell and mount-probing steps) before choosing.

## 2. Test code and toggles still in the Wi-Fi kernel patches (recorded 2026-10-10)
- **What:** patches 0065-0088 carry diagnostic code and boot-argument toggles (`h1b_*`, `apple_dart.pci_rebase`, ...). The production kernel compiles the
  `CONFIG_*_DIAG` parts out, but some test toggles in `msgbuf.c` (`h1b_feed`, `h1b_rxpost`, `h1b_sync_ms`) sit outside those options and a few log lines
  (`t7000-h1b: feed:`) print unconditionally. All default to off or to the working value.
- **Fix:** fold the final behaviour into clean upstreamable patches and drop the toggles; keep the test payloads on the diagnostic kernel until then.

## 3. Which of the Wi-Fi fixes are strictly required is not isolated (recorded 2026-10-10)
- **What:** `apple,pci-alias`, `pcie_aspm=off`, `device_wake=1` and rebased DART indexing are all on in every working run; their individual necessity was never bisected.
- **Fix:** one run per setting now that DMA works (alias off, ASPM default, device_wake 0), recorded in `research/2026-10-07-wifi-h1b-modelA-run.md`.

## 4. Intermittent early-boot freeze in the initramfs (recorded 2026-10-10)
- **What:** about 3 of the first ~8 boots of some payloads stopped in the initramfs with no USB network (screen stops at various steps); the next boot of the same payload is fine.
  Not seen on the recent production boots; not tied to Wi-Fi.
- **Fix:** capture a failing boot with a framebuffer photo and the last kernel message; compare timing with USB gadget start-up.

## 5. `wpa_cli` cannot reach the supplicant socket (recorded 2026-10-10)
- **What:** the static `wpa_cli` reports `/run/wpa_supplicant/client: No such file or directory`; `wpa.log` and `iw dev wlan0 link` are used instead.
- **Fix:** build `wpa_cli` with the control directory `/var/run/wpa_supplicant`, or create `/run/wpa_supplicant` in `wifi-up`.

## 6. Battery gauge (HDQ over UART5) sometimes fails its one identification at boot (recorded 2026-10-10)
- **What:** on one production boot (run 47 payload) `bq27xxx-hdq-uart` logged `HDQ transact timeout: matched 15/16 bytes` and `HDQ device identification failed`, then never retried. No `bq27545-battery`
  power supply, so `charging-policy` gave up and the charge limit stayed at the 100 mA default (the dashboard showed the policy as not running). Re-binding the driver at run time identified it on the first try (`HDQ DEVICE_TYPE = 0x0545`):
  the read is intermittently marginal, not broken.
- **Workaround in place:** `boot/charging-policy.sh` now re-probes the gauge (`unbind`/`bind` of `serial0-0` on the driver) every 5 s while the battery is missing and waits up to 120 s (was 60 s, no retry). Tested in `boot/test_charging_policy.py`.
- **Proper fix:** retry the identification inside the driver (`kernel/patches/0004`, `bq27xxx_battery_hdq_uart.c`: a few attempts with a short delay before failing probe), and look at why a pulse is marginal (the `>= 0xf0` threshold vs observed `0xe0`/`0xc0` bytes).
