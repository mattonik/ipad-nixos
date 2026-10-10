# J81 Wi-Fi userland: from a registered `wlan0` to a working connection

Status: started 2026-10-10 after run 39 (`wifi-bringup-d21`): the BCM4350 driver is up, `wlan0` exists and is `down`. The user authorised
the scan and association steps and "anything needed" to reach working Wi-Fi (2026-10-10). Test network: a dedicated IoT SSID chosen by the user.
The network name and passphrase live **only** in `artifacts/live/private/wifi-credentials.conf` (Git-ignored, mode 0600); they are never in Git,
the Nix store, a payload, a research note or memory.

## Approach: no rebuild, tools and credentials pushed at run time

The iPad's root is a RAM initramfs, so anything pushed to it disappears at reboot; nothing secret is ever baked into a payload.

1. `packages.<system>.wifi-userland-static` (flake): static aarch64-musl `iw`, `wpa_supplicant`, `wpa_cli` (public, generic, GC root `artifacts/live/gcroot-wifi-userland`).
2. The initramfs busybox already has `udhcpc`, `ifconfig`, `route`, `ping`, `wget`, `nslookup`; `boot/wifi-udhcpc.script` is the udhcpc event script (no secrets).
3. `boot/ipad_telnet_run.py '<command>'` runs a command on the telnet recovery shell (172.16.42.1:23, no login) and returns its output and exit status.
   (Dropbear SSH is key-only and the Mac's key is not in the image's `authorized_keys`, so telnet is the control channel.)
4. A throw-away HTTP server on the Mac bound to the USB-link address only (172.16.42.2) serves the tools, the udhcpc script and the credentials file to the iPad's
   `wget`; it is stopped as soon as the files are copied.

## Steps (each logged in `research/2026-10-07-wifi-h1b-modelA-run.md`)

| Step | Command (on the iPad) | Success |
|---|---|---|
| 0 | `ip`/`ifconfig wlan0 up` | operstate `down`/`up`, no kernel error |
| 1 scan | `iw dev wlan0 scan` | the test SSID appears with a signal level (first radio TX: probe requests) |
| 2 associate | `wpa_supplicant -B -i wlan0 -c /tmp/wifi/wpa.conf` | `wpa_state=COMPLETED` |
| 3 DHCP | `udhcpc -i wlan0 -s /tmp/wifi/udhcpc.script` | an address, a router, DNS |
| 4 traffic | `ping` the router, `nslookup`, `wget` a small file | replies |

Safety: kernel log (`dmesg`/stream) watched for firmware errors (`brcmf_fw_crashed`), DART faults and oopses; the USB telnet link stays the recovery path.
If a step hangs the machine, the previous good state is the tag `wifi-bringup-d21` and its payload (`artifacts/live/gcroot-h1b-base-0090`).

## Later (permanent form)
- Put the tools in the Wi-Fi base overlay (public) and have the private assembler install `wpa_supplicant.conf` from a private file (a `--wifi-credentials FILE` option;
  the assembler's "no Wi-Fi client tools" verification must then become "tools only when requested").
- Start the connection from the boot hook instead of by hand.
- `regulatory.db` (the kernel logs `Direct firmware load for regulatory.db failed`): cfg80211 uses the built-in world regulatory domain without it; add the database
  to the firmware overlay if channel restrictions matter.
