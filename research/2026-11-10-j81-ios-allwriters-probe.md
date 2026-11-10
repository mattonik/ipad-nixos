# J81 all-selector bridge writer probe

> Hardware result: 93 requests were captured, including 27 for selectors
> 7, 11 and 6; see [the result](2026-11-10-j81-ios-allwriters-result.md).

Prepared 2026-11-10 after the [66-request comparison](2026-11-10-j81-ios-corrected-bridge-result.md).
This module has not been run on the iPad.

The last capture found 66 selector 9/10 requests while the same provider
window counted 93 calls to the writer hook across all selectors. The 66
records included a wider early window than the 93-call count, so subtraction
does not identify the other calls. This probe records the selector, instance,
offset and value of **all** calls through that same writer hook, including
calls before the selected GFX provider call and during it. It retains the
client and aggregate decisions, transition count, GFX target comparison,
bridge mode, and provider-window writer count. It adds no GPU or PMGR MMIO.

Each record is `Pp:ssssssss/iiiiiiii:oooooooo=vvvvvvvv;`, with `P0` for
before the provider starts and `P1` for the provider window. Phase is
sampled by the hook after record reservation; a concurrent event at the
window boundary could be classified on the other side. All hooks are global,
so unrelated concurrent work can also appear. Reservation order does not
prove store completion or globally ordered hardware writes. The 128-slot
buffer is shared across both phases; `B1` means overflow and `?` means an
unready slot. If `B0`, no `?`, and logging is complete, compare the number
of `P1` records with `W`; differences remain possible near phase boundaries.
Output has two records per log message, so log loss must be checked.

The writer is only one path. No records before this hook is installed,
before XNU, or through other writer functions should be inferred from the
output. This capture does not establish that any register value persisted.

## Build and host verification

Module: `artifacts/live/private/j81-ios-allwriters-probe/checkra1n-kpf-pongo-j81-allwriters`

SHA-256: `7f1f6eeb78fc8ac97556148505d1de16ca705bb39a1a762306b557821defc0c9`.

The six patch sites and exact XNU UUID are unchanged from the previous
successful probe. Host KPF accepted the target 19H394 image and refused each
of six missing or duplicate signatures and a wrong UUID. Native ARM64 host
tests covered phase labels, selectors outside 9/10, all-writer counting,
batched output and 128-entry overflow. Device build completed without
compiler warnings. The private artifact directory contains source,
registration and test inputs. These are simulations: boot-time mapping,
logging volume, concurrency and timing on the device remain unverified.

## Temporary boot

After a fresh DFU and checksum verification:

```sh
cd /path/to/ipad-nixos
printf '%s  %s\n' 7f1f6eeb78fc8ac97556148505d1de16ca705bb39a1a762306b557821defc0c9 artifacts/live/private/j81-ios-allwriters-probe/checkra1n-kpf-pongo-j81-allwriters | shasum -a 256 -c - && sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-allwriters-probe/checkra1n-kpf-pongo-j81-allwriters --debug-logging
```

If palera1n stays at “Booting PongoOS” while PongoOS is visible, stop it and
rerun as in prior boots. Once iPadOS is up, unlock and collect its startup
log privately. The probe can stall or reboot the iPad and may require another
DFU cycle. Full device log archives can contain personal information.
