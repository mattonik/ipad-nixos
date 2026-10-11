# Follow-up brief for the research agent: exact register semantics of the iOS UART baud routine (needed to write the Linux patch)

Context: your note `research/2026-10-11-uart-3mbaud-static-analysis.md` (commit `543b834`) shows that `AppleSamsungSerial::setBaud`-equivalent (`0xffffff8002d76bb8`) reads `nclk` and `uart-version`, searches a divider/oversampling candidate (version 1 down to a factor of 4) and writes `0x28`, `0x34`, `0x38`.
That is the right lead and we want to implement it in `drivers/tty/serial/samsung_tty.c` (`TYPE_APPLE_S5L`). The note does not yet give enough to implement it safely: a wrong bit in a baud register could also break the 115,200 rate that works today (measured accurate on the iPad). We need exact, checkable semantics.

Our check on the arithmetic: with `nclk` = 24,000,000 and a requested 3,000,000, `scaled = (nclk << 17) / baud` = 8.0 (in 17-bit fixed point); a sampling factor of 4 with a divisor of 2 gives exactly 24e6/(4*2) = 3.0 MHz. The legacy /16 path gives 24e6/(16*1) = 1.5 MHz at best. So the model fits; the bits do not yet exist on paper.

## Questions (static analysis only; same constraints as the previous briefs)
1. **Pseudo-code of the routine for `uart-version` 0 and 1.** Give the candidate loop explicitly: the factor values tried and their order (16, 8, 4? or a table), how the divisor is derived from `scaled`, the error/tolerance criterion, tie-breaking, and what is stored. A C-like listing of the arithmetic (no raw decompiler dump) is the deliverable.
2. **Bit layout of each stored register.** For `base+0x28`, `base+0x34`, `base+0x38`: which bit fields carry (a) the divisor, (b) the sampling-factor/mode selection, (c) any fractional/slot correction, and which other fields of those registers the routine preserves (read-modify-write or whole-register store). Also the same for `base+0x08` and UCON (`base+0x04`) if the baud routine touches them.
3. **Worked examples.** For `nclk` = 24,000,000 give the exact values written to `0x28`, `0x34`, `0x38` for requested rates 115,200, 921,600, 1,500,000, 2,000,000 and 3,000,000, for `uart-version` 1. Sanity condition: 115,200 must produce a `0x28` value equal to the Linux result `(24e6 + 8*115200)/(16*115200) - 1` = 12 *or* you must say what differs and why Linux's 115,200 currently works while writing only `0x28`
   (i.e. what the power-on/iBoot-left values of `0x34`/`0x38` must be: factor 16, no correction).
4. **Collision check.** Linux's S3C layout names `0x30` UINTP, `0x34` UINTSP, `0x38` UINTM, `0x2c` DIVSLOT. In the pinned Apple-S5L path Linux uses UTRSTAT/UCON bits for interrupts (not UINTP/UINTSP/UINTM). Confirm from the iOS side that on this UART block `0x34`/`0x38` are baud registers (not interrupt registers) and that
   nothing Linux's S5L path relies on lives there.
5. **Runtime changes.** Does iOS re-run this routine on every `setTermios`/baud change after open (needed because `hci_bcm` changes speed after the first HCI exchange), and does the divider change need the UART disabled, FIFOs flushed or a specific order (0x34/0x38 before 0x28?).
6. **`nclk` value.** The ADT uart3 node's `clock-ids` (`15 01 00 00 04 00 00 00`) / the `nclk` property source: which clock rate does iOS pass as `nclk` for UART3 on this board (24 MHz, or another PMGR clock)? Our measurement says the input at the divider is 24 MHz with the current Linux setup.

## Deliverable and constraints
One note `research/2026-10-11-uart-baud-register-semantics.md` with the pseudo-code, the field tables, the worked-example table and the answers to 4-6, each marked direct evidence / inference. Static only; no hardware, no builds, no raw bytes or identifiers; path-limited commit with the usual trailer. If something cannot be determined from the stripped binary, say exactly what and which hardware read
(read-only) would settle it (we can read UART registers on the running iPad through `/dev/mem` with a read-only tool if needed; tell us the offsets and expected values).
