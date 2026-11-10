# J81 iOS dispatcher probe prepared

> Result and correction: `w4` in the writer hook is an instance index,
> not a requested state; see the [hardware result](2026-11-10-j81-ios-dispatch-capture-result.md).

Prepared 2026-11-10 after the [matrix result](2026-11-10-j81-ios-matrix-capture-result.md).
This module has not been run on the iPad. It is restricted to iPadOS 15.8.5
19H394 with XNU UUID `CC26BE6A-292B-3759-9ED0-290BCF18B090`.

## Question and capture

The previous probe recorded one constructed transition and no matching
selector 9/10 state 15 writer request. This probe retains that capture and
adds the first constructed list entry, the dispatcher comparison of the
existing PMGR *target* with the requested state, the PMGR bridge mode, and
a count of all calls through the instrumented writer during the selected
GFX provider call. It reads existing software data and makes no additional
GPU or PMGR MMIO access. It instruments the comparator at `bd8598`; the
comparison reads values already obtained by iOS. The mode is an ordinary
word in the PMGR object, not a hardware register read.

Output extends the matrix header:

* `Lxxxxxxxx`: first list entry's raw little-endian 32-bit word; its low
  16 bits are the device ID and the next byte is the requested state. This
  value is meaningful only when `N1` reports a nonzero count.
* `X1:old>requested`: this comparator was observed for the single-entry GFX
  list; values are the prior target nibble and the request. The comparator
  is before the branch: unsigned old >= request selects the non-increasing
  path. `X0` means unobserved, including when the list was not precisely
  one GFX entry or this comparator was bypassed.
* `Mxxxxxxxx`: PMGR object's bridge mode, meaningful only if `X1` is set.
* `Wxxxxxxxx`: number of calls to the instrumented writer dispatch for all
  selectors and states during the first GFX provider call. `W>0` positively
  demonstrates that this writer hook ran in that window. `W0` does not prove
  it is functional or that no other writer or earlier write happened.

`D`, `A`, `N`, `B` and selector-record semantics remain as in the matrix
plan. `W` is independent of the selector/state filter on the logged entries;
matching records can also precede the GFX provider call while `W` counts
only that call. Global hooks may see concurrent work; their sequence is not
proof that a hardware store completed. The comparison capture explicitly
declines to attribute the comparison to GFX when the list has multiple items.

If `X1` shows `15>15`, the equal-target path is selected: investigate the
prior state and non-increasing path. If `X1` shows a smaller target than
requested, inspect the increasing path, mode and writer count. If `X0`,
use the raw list, count and code paths to determine whether the comparison
was inapplicable or instrumentation failed. `W>0` with no matching records
constrains the missing matches; `W0` is inconclusive without a separate
positive on-device control. In all cases this does not establish GPU MMIO
accessibility or a working Linux driver.

## Build and validation

Module: `artifacts/live/private/j81-ios-dispatch-probe/checkra1n-kpf-pongo-j81-dispatch`

SHA-256: `1b334eb8063a3a73ee11b878433bdd111b987621209f7f5ab30feca9ed8711e3`.
The full source, registration, host test sources and guard test scripts are
stored privately alongside it. The build is an ARM64 Pongo KPF module; it
uses the prior successfully booted logger, buffer and provider wrapper.

Host tests on the exact 19H394 kernel produced `prepared=1` and `applied=1`.
Each of six independently missing or duplicated instruction signatures, and
a mismatched kernel UUID, was refused. Native ARM64 simulations tested
one-entry decoding, equal and increasing target comparisons and their flags,
bridge mode, a positive count of unfiltered writer calls and multi-line
logging of 66 filtered records. These are simulated calls, not actual XNU
execution. Real boot context, concurrency, logging and timing remain risks.

## Operator command when ready

After a fresh DFU and checksum verification, the operator can run:

```sh
cd /path/to/ipad-nixos
printf '%s  %s\n' 1b334eb8063a3a73ee11b878433bdd111b987621209f7f5ab30feca9ed8711e3 artifacts/live/private/j81-ios-dispatch-probe/checkra1n-kpf-pongo-j81-dispatch | shasum -a 256 -c - && sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-dispatch-probe/checkra1n-kpf-pongo-j81-dispatch --debug-logging
```

If palera1n remains at “Booting PongoOS” while PongoOS is visible, stop it
and rerun as on prior boots. After iPadOS boots, unlock and retrieve the
startup log privately. The probe may stall or reboot the iPad; recovery may
need another DFU cycle. Do not publish the complete device log archive.
