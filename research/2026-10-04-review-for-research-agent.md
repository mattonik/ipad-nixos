# Review of in-progress research work, for the research agent

Date: 2026-10-04. A read-only review of two pieces of work that were in the
working tree and not committed by this author: the touch callback note and the
staged PCIe patch `0052`. Nothing here modifies those files; they are left exactly
as found. Labels: **E** observed, **I** inference, **U** unknown. Authoritative
current state: [`2026-10-04-session-handoff.md`](2026-10-04-session-handoff.md).

## 1. `2026-10-04-touch-callback-resolution.md` (untracked)

Sound overall; keep. Verified points:

- `function-enable_download` is absent from the J81 ADT and from the public J82
  iOS 10.3 personality; the J82 driver treats the missing callback as
  `kIOReturnUnsupported` and ignores it. Treat it as optional and non-gating.
- Do not add a guessed GPIO write for `display_sync`. Agreed.

**Correction to carry forward.** The note reads GPIO55's snapshot word `0x00072a82`
as "consistent with" Apple's requested mode because "its low two bits are `2`". That
is not the word's layout. Using the kernel `pinctrl-apple-gpio` fields (bit 0 data,
bits 3:1 mode, **bits 6:5 `PERIPH`**, bits 8:7 pull, bit 9 input enable), Apple's pin
mode 2 sets `PERIPH = 1`, and GPIO55's word has `PERIPH = 0`. GPIO51, the SPI3
chip select, has `PERIPH = 1`, which independently confirms the decode. So the
baseline is **not** in Apple's requested state, and Apple's `display_sync` enable is a
**pinmux to peripheral function 1**, not a level. Full derivation:
[`2026-10-04-display-sync-pinmux-decode.md`](2026-10-04-display-sync-pinmux-decode.md).

Suggested edit to the touch note (left to its author): replace the "low two bits"
sentence and the "baseline may already be configured as Apple requests" inference
with the `PERIPH` reading, and state that the omitted step is a reversible pin-function
selection, still needing explicit user approval before any hardware use.

## 2. Staged patch `0052-pcie-apple-t7000-j81-reg-on.patch` and its kernel variant

Intent is right: turn the hardware-proven `0050` test into a board-gated sequence.

Good (E, from reading the patch):
- Gated by an explicit `apple,reg-on-pmic = <&d2207>` phandle; no global PMIC search.
- Writes only `0x0403` with `(old & 0x1d) | 0x02`, verifies by readback, rejects
  nonzero upper bits, waits 100 ms, and **fails the probe** if a declared resource
  cannot be asserted. No Bluetooth `0x0402` reference.
- Separate payload without Bluetooth userland or I2C tools; the test file guards
  that contract.

Gaps to close before relying on it (I):
1. **Not built or applied.** `kernel/test_pcie_j81_reg_on_patch.py` only greps the patch
   text. Add a zero-fuzz apply check against the exact pinned source (as done for
   `0011`) and a real `nix build` plus a static payload gate before any boot.
2. **"Production" is a misnomer.** It stacks on `0016`, `0040`-`0045`, the test-stage
   patches with DBI/tunable/link-speed writes and test log strings. It is "Stage 5F
   plus DT-gated REG_ON", the proven base, not a cleaned-up driver.
3. `of_find_property()` is deprecated; prefer `of_property_present()`.
4. The new `apple,reg-on-pmic` property needs a binding note (even a short
   `Documentation` stub in the patch) before it can be upstreamed or reused.
5. REG_ON is not de-asserted on probe failure after assertion or on unbind; document
   whether that is intended (the PMU resets the GPIO on reboot anyway).
6. Link-wait: the stage code still polls `+0x88` bit 6. The proven success signal is
   the root port's DLLLA (see the PCIe warnings section of
   `j81-d2207-gpio-register-correction.md`).

No hardware test of `0052` is justified until items 1 and 2 are addressed and the user
decides.

## 3. Open items this review adds to the handoff

- Possible next touch experiment (needs explicit user approval, not scheduled):
  `GPIO55` `PERIPH = 1` only, the four existing frames, restore the saved word.
- `0052` follow-ups above.
