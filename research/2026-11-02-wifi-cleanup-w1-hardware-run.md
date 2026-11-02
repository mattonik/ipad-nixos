# Wi-Fi cleanup W1: hardware run (2026-11-02)

Branch `wifi-cleanup-w1`. The production Wi-Fi kernel gains eight OrchardLinux/orchard
(`b5e3769`) patches, copied unchanged as `0101`-`0108`: brcmfmac reset work, RX buffers
mapped for device reads, port authorized, dwc2 resume L0, f_ecm notification resend,
GPIO chip-select delays applied once, pinctrl GPIO wakeup, bq27xxx discharging at full
charge. Plan: `research/2026-11-01-orchardlinux-org-review.md` ("What is usable", item 3).

## Off-device checks

- All eight apply on top of our full production series (patch(1), pinned `6831bc70`).
- `tools/check_offline.py`: 48 passed, 0 failed, 8 skipped.
- `j81-dtbs-check`: 9 warnings, 0 new, 0 fixed.
- `j81-kunit`: 23 tests, 22 passed, 1 skipped (the known echo-matcher SKIP).

## Hardware run

Payload `m1n1-hoolock-wifi-nixos` (public `/nix/store/5gzzzm71...-ipad-air2-m1n1-hoolock-wifi-nixos`),
assembled privately with `--production` (run id `27070e503241158c1c4ff4fe17176305`), NixOS root
from the unchanged `gcroot-nixos-ram-serve`. One DFU cycle. palera1n timed out once waiting for
download mode, then recovered by itself; the PongoOS bootm disconnect is the normal hand-off.

| Check | Result |
|---|---|
| NixOS hand-off, `systemctl is-system-running` | running |
| USB ssh (172.16.42.1) | works |
| Association | 5 GHz (5180 MHz), signal -56/-57 dBm, rx 526-702 / tx 351 Mbit/s |
| DHCP | 192.168.0.205, default route via wlan0 |
| Internet | ping 1.1.1.1 0% loss |
| 5-minute soak | ping gateway 300/300, 0% loss, avg 2.4 ms, max 15 ms; still associated after |
| Download | 100 MB in 2.6 s, about 320 Mbit/s (HTTPS) |
| dmesg | no DART fault, no brcmfmac error/timeout, no deauth/disassoc |

Boot messages seen: `of_irq_parse_pci: failed with rc=-22` (known since the MSI work,
`research/2026-10-10-wifi-bringup-root-cause-and-permanent-fix.md`), the built-in `g_multi`
failing with -22 (present in 475 earlier session logs; usb0 comes up through the initramfs
gadget anyway) and one `bq27xxx` temperature read error at boot. None is new.

**Result: no regression. W1 is fine to merge.** The faster download than the 2026-10-11
figure (about 228 Mbit/s) is a different link and server, not attributed to the patches.
`0106` halves the effective GPIO chip-select delays the touch-diag payload configured
(`0097`); touch runs after the merge see the configured values, not double.
