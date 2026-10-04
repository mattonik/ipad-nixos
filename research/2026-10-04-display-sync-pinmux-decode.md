# GPIO55 `display_sync` is a peripheral-function pinmux request, not a level

Date: 2026-10-04. Static, with a cross-check against already recorded read-only
GPIO config words. No hardware access for this note. Review of
[`2026-10-04-touch-callback-resolution.md`](2026-10-04-touch-callback-resolution.md);
it refines, and in one place corrects, that note's reading of GPIO55. Labels: **E**
observed in code or recorded data, **I** inference, **U** unknown.

## The Apple GPIO pin-mode setter (E, from the earlier provider decode)

`AppleS5L8960XGPIOIC`'s pin-mode function writes the per-pin config word with
`word = (word & ~mask) | (mask & value)`:

| Mode | mask | value | Effect |
| --- | --- | --- | --- |
| 1 | `0x26e` | `0x202` (+ data bit in modes `0xe`/`0xf`) | output, peripheral function cleared |
| **2** | `0x260` | **`0x220`** | **bits 5 and 9 set, bit 6 clear: peripheral function 1, input enabled** |
| 3 | `0x260` | `0x240` | peripheral function 2 |
| 4 | `0x260` | `0x260` | peripheral function 3 |

The kernel's `pinctrl-apple-gpio` documents the same word: bit 0 data, bits 3:1 mode,
**bits 6:5 `PERIPH`**, bits 8:7 pull, **bit 9 `INPUT_ENABLE`**. So Apple's "mode 2" is
"select peripheral function 1 on this pin", the same field the J81 SPI3 chip-select
uses (`APPLE_PINMUX(51, 1)`).

## What that means for `display_sync` (E, I)

- **E:** the callback's enable passes `value = NULL, mode = 3`; the provider maps
  mode `3` to descriptor byte `f3`, which for GPIO55 (`01 01 00 02`) is `2`, i.e. the
  pin-mode setter above with mode **2**: peripheral function 1.
- **E (recorded read-only snapshot):** GPIO55's config word is `0x00072a82`:
  `PERIPH = 0`, mode field `1` (output), data `0`, input enable set. GPIO51 (SPI3 CS)
  is `0x00072623`: `PERIPH = 1`, i.e. already in a peripheral function, which confirms
  the field decode on a pin whose function is separately hardware-confirmed.
- **Correction to the earlier note:** it called GPIO55's "low two bits are `2`"
  consistent with the requested mode. That is not how the word is laid out. The
  requested state is `PERIPH = 1`; GPIO55 is **not** in it (`PERIPH = 0`, plain GPIO
  output low). So the baseline is *not* already what Apple requests.
- **I:** Apple's enable of `display_sync` therefore **muxes GPIO55 to peripheral
  function 1** (a display-pipe sync signal on J81), and disable returns it to a plain
  GPIO. It is a pin-function selection, not a driven level. Whether the display pipe
  actually drives a useful waveform on that pad with the inherited simplefb is **U**.

## What this changes

1. The touch diagnostic omitted a step that is a **pinctrl function selection**, not
   a made-up level: `GPIO55 -> function 1` (the Linux form is
   `APPLE_PINMUX(55, 1)`, the same mechanism as the SPI3 chip-select). The earlier
   caution against "an explicit GPIO55 high write" stands, and does not apply to this.
2. It remains an **untested, possibly relevant** difference from Apple's flow. The
   controller returned its idle pattern without it, which is consistent with the ROM
   not needing it, but the ROM state alone does not prove that.
3. A future experiment is now well specified: set only the pin's `PERIPH` field to 1
   (input enable already set), run the existing four frames, then restore the saved
   word. It is a pin-config write, reversible, and still needs the user's explicit
   approval; it is not scheduled here.
4. Keep `function-enable_download` as optional/non-gating, as the note concludes.
