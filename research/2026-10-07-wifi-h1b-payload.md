# Wi-Fi H1B test payload (Model A + private C2 firmware): build and assembly design

Date: 2026-10-07. Implements the coding-agent step from the research handoff: an updated Model A
payload containing the known-good PCIe/MSI path (0052-0057), the DMA window with Apple's rebase
(0063 + 0064), brcmfmac PCIe, and the **private** C2 `rieslinga` firmware, CLM, TxCap and the
tuple-selected NVRAM. **Nothing was booted. The hardware run needs the user's go-ahead.**

## Split: public base in Nix, private overlay assembled locally

Firmware and NVRAM must never enter Git or the Nix store, and a flake only sees tracked files, so:

1. `m1n1-hoolock-pcie-j81-wifi-h1b-base` (Nix, public): kernel with brcmfmac PCIe built in
   (`CONFIG_BRCMFMAC=y`, `_PCIE=y`, `BRCMDBG=y`, CFG80211 without the signed-regdb requirement),
   the Model A DTB, the stock initramfs with USB recovery, and bootargs with
   `brcmfmac.debug=0x001c0004` (INFO | MSGBUF | PCIE | FWCON) for the H1B evidence. No firmware.
   Patch list is exactly 0016, 0040-0045, 0052-0057, 0063, 0064: no `0060`, none of
   0058/0059/0061/0062 (probe, self-test, shadow, diag drivers would bind the endpoint first),
   no SDIO/USB bus support. `kernel/test_wifi_h1b_payload_contract.py` pins all of this.
2. `boot/assemble_private_wifi_payload.py` (local, stdlib only): adds a newc initramfs overlay and
   writes the final `m1n1-linux.bin` under the Git-ignored `artifacts/live/private/` only
   (refuses elsewhere, exclusive creation, mode 0600/0700).

## Explicit private filename selection (no driver change)

The device tree has no `brcm,board-type` (the root-port node `pci@0,0` has devfn 0, not the real
root port's devfn, so adding an endpoint node would also mean touching the hardware-proven PERST
path), so the pinned loader requests only the canonical names. The assembler therefore stages, by
an explicit mapping made from the OTP-proven identity (`2026-10-06-bcm4350-otp-parser-result.md`):

| Source (Apple, private) | Staged as `lib/firmware/brcm/...` |
| --- | --- |
| C2 `rieslinga.trx` | `brcmfmac4350c2-pcie.bin` |
| C2 `rieslinga.clmb` | `brcmfmac4350c2-pcie.clm_blob` |
| C2 `rieslinga.txcb` | `brcmfmac4350c2-pcie.txcap_blob` |
| the selected NVRAM (named in the parser-result note) | `brcmfmac4350c2-pcie.txt` (whitespace-normalised as Asahi does) |

BCM4350 chip revision 5 maps to the `brcmfmac4350c2-pcie` base in the pinned `pcie.c` (revisions 0-7),
agreeing with the OTP record's `s=C2`. The overlay contains only these four files and only in this
payload, so no generic fallback can silently supply a different calibration; the verifier fails on any
other firmware file. The driver's OTP/SKU filename path (patches 0048/0049) is not used.

The three binaries are checked against the SHA-256 and size already recorded in
`j81-private-firmware-assets.md` (C2 set); the NVRAM must be non-empty ASCII with at least ten
`key=value` lines (its hash is recorded only in the private manifest).

## Run identity

The assembler appends a 128-bit `j81.run_id=<token>` to the bootargs and records the token, the
public payload path and part hashes, every private asset's name/size/SHA-256 and the final payload
hash in `PRIVATE_MANIFEST.json` (private). On the device, `/proc/cmdline` must show the token
before any observation counts as identity-qualified (`2026-10-05-hardware-run-identity-protocol.md`).

## Checks before any hardware (all automated)

| Requirement from the handoff | Where it is enforced |
| --- | --- |
| no `0060` | `kernel/test_wifi_h1b_payload_contract.py` (exact patch list) |
| payload hash and private asset hashes recorded locally | `PRIVATE_MANIFEST.json` |
| non-empty NVRAM actually selected | assembler (ASCII, >=10 pairs) and `--verify` (staged file present, non-empty, hash equals manifest, only 4 firmware files) |
| no scan, association, intentional transmission | `--verify` and `--wifi-h1b-base` fail if wpa_supplicant/iw/NetworkManager/hostapd/iwd/connman exist in the initramfs; the driver does not scan by itself; nothing brings `wlan0` up |
| USB recovery remains enabled | ECM `deviceinfo` override and `rdinit=/init` debug shell checked in both |

`python3 boot/assemble_private_wifi_payload.py --public <nix payload> --assets <private asset dir> --out artifacts/live/private/<name>`
then `--verify <name>`. Tests: `boot/test_assemble_private_wifi_payload.py` (synthetic assets only;
NVRAM rules, newc overlay round trip, private-directory policy, tamper and policy detection; three
mutations of the assembler are caught).

## Status

- Public base payload: built and verified (see the build section below once updated).
- Private assembly: **blocked on the private source assets**: the matching iPad5,3 `12B410` filesystem
  (the earlier read-only mount) is no longer on this Mac, so `rieslinga.{trx,clmb,txcb}` and the NVRAM file are
  not available locally. They must be provided or re-extracted (a download) by the user's decision.
- Then: review the assembled payload, wait for an approved run, classify with
  `2026-10-07-wifi-h1b-evidence-matrix.md`; build Model B only if Model A fails at the DMA setup stage.

## Private asset extraction (2026-10-07, with the user's approval of the download)

Re-extracted the C2 set from the matching iPad5,3 `12B410` restore without mounting through `ipsw`
(its mount step needs an admin password, so that path was cancelled; no credentials were entered):

1. `iPad5,3_8.1_12B410_Restore.ipsw` (2,178,168,430 bytes) from Apple's public download host to a
   private scratch directory outside the repository; `ipsw extract --dmg fs` produced the still
   encrypted (`encrcdsa`) `058-01629-167.dmg`.
2. The RootFS key was read from the public firmware-key page through the wiki API (the same source
   `ipsw --lookup` uses; the page's browser challenge was not touched). It stays out of Git.
3. `tools/vfdecrypt_ios8.py` decrypted the image (blocks of 512 bytes, AES-128-CBC, HMAC-SHA1 IVs).
   **The result's size and SHA-256 equal the values already recorded in `j81-private-firmware-assets.md`**
   (2,123,313,195 bytes, `b187f71f...`), so it is the same filesystem used for the earlier audit.
4. `hdiutil attach -readonly -nobrowse` (no prompt), then only the four needed files were copied to
   the ignored `firmware/j81-12B410/wifi/C-4350__s-C2/` (mode 0600): `rieslinga.trx`, `.clmb`, `.txcb` and
   the selected NVRAM. The three binaries match the recorded size and SHA-256 exactly; the NVRAM is
   a 3.4 KB text file. The image was detached and the IPSW, encrypted and decrypted DMGs and the key were
   deleted from scratch.

## Private firmware store (kept locally, never in Git)

So the restore never has to be fetched or reconstructed again, the following live under the
Git-ignored `firmware/j81-12B410/` (directories 0700, files 0600; `git check-ignore` confirms):

| Path | Content |
| --- | --- |
| `ipsw/iPad5,3_8.1_12B410_Restore.ipsw` | Apple's public restore, 2,178,168,430 bytes, SHA-256 `d9cb4feda3d98fdb3c1d92713bac2bc6f5d1f317a2707770a248cbd1829ebc07` (valid zip, contains `058-01629-167.dmg`) |
| `keys/Keys_OkemoTaos_12B410_iPad5,3.txt` | the public RootFS key lines for this build from the firmware-key wiki (the key itself is not recorded here) |
| `wifi/C-4350__s-C2/` | the four extracted files described above |

To rebuild the extraction from the stored IPSW: `ipsw extract --dmg fs --device iPad5,3 <ipsw>`, then
`tools/vfdecrypt_ios8.py <encrypted dmg> <out dmg> keys/<file>`, check the decrypted image against the recorded
SHA-256, attach it read-only with `hdiutil`, and copy the four files. Back this directory up with the
other private material; it is not recoverable from Git.
