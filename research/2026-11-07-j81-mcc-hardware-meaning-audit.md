# J81 MCC `+0x830`: hardware-meaning audit (offline)

## Result

No public A8X/S5L8960X hardware register manual or Apple iOS 8 MCC register
description was found that assigns hardware meanings to bits in MCC
`+0x830`. The iOS 8.1 kernelcache disassembly establishes how Apple's driver
uses the word, but cannot by itself establish the peripheral's internal
semantics. In particular, the labels “MCC mode 0” and “MCC mode 4” should be
read as **configuration-table selector indices** in Apple's software path,
not as independently documented hardware modes.

The exact software-level behavior is:

| Selector | J81 20-byte record prefix | Driver writes to mapped `+0x830` | Result on mask `0x15f` |
|---|---|---|---|
| 0 | `[0x10, 0, ...]` | Replace bits 4:0 with `0x10`; clear bit 8 | `0x010` |
| 4 | `[0x55, 0x11, ...]` | OR unmasked `0x55` into the low region while preserving old bits 5+, then set bit 8 | `0x155` |

This is a driver write signature, not a decoding of hardware functionality.
Mode 4's first write also sets bit 6 and preserves bit 5, so interpreting its
word 0 as only a five-bit value would be inaccurate. Selector 0 similarly
does not prove that the hardware has entered a semantic “mode 0.” The selector
does not access the record's final three words on this numeric path.

In the 12B410 J81-targeted MCC class, the relevant static call path is
`start` (`0xffffff8002e53400`) → enable/disable routine
`FUN_ffffff8002e53924` → setup helper `FUN_ffffff8002e54128`, plus the later
numeric selector `FUN_ffffff8002e54300`. On the selector path the two loads
from `+0x830` are only inputs to read/modify/write operations; there is no
comparison with an expected value, completion poll, or separate readback
function in that selector. Startup also reads old values where it preserves
unrelated bits. This confirms what the proposed standalone read lacks: the
driver's identity, call reason, and success result.

## What one read can establish

A correctly captured raw value can be masked to test whether the present word
matches either known software signature (`value & 0x15f == 0x010` or `==
0x155`). A match means only that the bits currently have the same values as
those left by that selector's driver writes. A single read cannot establish
which selector ran, who wrote the bits, whether the hardware accepted them,
what the cache behavior is, or whether MCC is otherwise initialized. Startup,
firmware, and other writers could leave the same bits. A value matching
neither signature is also inconclusive: selector 4 preserves bit 5 and bits
9..31, and the source gives no hardware-defined reset/readback semantics.

A before/after pair around a known selector event can show a change in the
masked fields. Attribution would still require evidence that Apple's guarded
callback ran and returned successfully, or a trace of the actual write path.
The existing proposed Linux action reads once, so it is only a raw baseline.

## Sources checked

* Local original iOS 8.1 / 12B410 kernelcache and recovered J81 ADT; Ghidra
  analysis at the addresses recorded in
  [`2026-11-07-j81-mcc-ios81-record-stride.md`](2026-11-07-j81-mcc-ios81-record-stride.md).
* Public Linux A8/A8X support material and the public Apple kernel-class
  metadata listing (`AppleS5L8960XMemCacheController` and
  `AppleS5L8960XMemCacheModeFunction`). These identify the driver/class but
  do not document `+0x830` bitfields or cache-mode behavior.
* Web searches for the exact driver/property names and `+0x830` returned no
  applicable Apple/A8X register manual. Unrelated peripherals with the same
  offset were discarded.

The public class metadata is secondary reverse-engineered material, not a
hardware specification. The public Linux A8/A8X DTS patches likewise do not
describe an MCC register block or a driver contract. So there is no public
hardware documentation here that upgrades the instruction-derived write
signatures into functional register semantics.

## Cross-generation Ghidra check (iOS 15 T7000)

The local Ghidra project `artifacts/live/private/gpu-offline/ios15t7000.gpr`
contains an iOS 15 T7000 (`AppleS5L8960X`) MCC implementation. It is a useful
software comparison, but T7000 is A8, not J81's A8X/T7001, and its register
offsets/config stride differ; do not transfer its addresses or values to J81.
The stored Ghidra decompilation (`ios15-mcc-config.c`, `ios15-mcc-init.c`,
`ios15-mcc-apply.c`) provides these concrete findings:

* `FUN_fffffff006c91c3c` is the numeric config-table selector. It reads
  register `+0x794` for a read/modify/write, loads record word 0 at a 44-byte
  stride, writes it while preserving bits 5+, then writes a second value
  preserving bits 0..7, taking bit 8 from record word 1, and clearing bits
  9..31. It updates software's selected index at `self+0xa8`. The function
  does not read the resulting register as a status check or report whether
  hardware accepted a setting.
* `FUN_fffffff006c91070` is the enable/disable configuration path. Enable
  writes a group of configuration registers (`+0x79c`, `+0x7a0`, `+0x7a4`,
  `+0x7a8`, `+0x7ac`, `+0x884`), calls the shared config function, turns on
  `+0x780` bit 0, and applies record word 1 to `+0x794` bit 8. Disable clears
  the low five bits at `+0x794`, invokes the shared config function, and
  clears `+0x780` bit 0.

This newer implementation is consistent with Apple treating the low five
bits and bit 8 as software-selected configuration fields, while still
offering no physical definition for them. It also confirms that the repeated
reads of `+0x794` are RMW inputs, not independent hardware readback or
completion polling. This is an inference about the driver contract from
static code, not proof of the A8X block's internal behavior.

## Concrete next path

Keep the currently scoped one-read capture as a raw baseline only; do not
write MCC registers or guess clock/reset dependencies. Since the user cannot
perform DFU now, the useful offline cross-generation comparison is complete
for the local T7000 image. It did not expose a semantic definition. If a
device later becomes available, a controlled read-only before/after capture
bracketing an independently observed selector event is the next useful
hardware evidence. A genuine functional definition still needs a published
register spec or an observed relationship between those bits and cache
behavior.
