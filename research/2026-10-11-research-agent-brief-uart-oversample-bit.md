# Follow-up 4 for the research agent: which bit turns on the UART's divide-by-8 base mode?

Your clock note (`research/2026-10-11-uart-clock-source.md`, `4dbea6e`) closed the PMGR question (bits 9:8 are `WAS_*` history flags). One more fact from the captured ADT (details in `research/2026-10-11-uart3-register-capture.md`, last section): the `arm-io,t7001` `clock-frequencies` table gives the UART's
clock ids `{0x115, 0x4}` as index 21 = **24 MHz** (baud clock) and index 4 = 100 MHz (peripheral clock), so iOS's `nclk` is 24 MHz = what we measure. The ADT has no 48 MHz source for the UART.

Therefore your worked table (`0x19` = 115,200, `1` = 1.5 M, `0` = 3 M at 24 MHz) only makes sense if the UART divides by **8 x (+0x28 + 1)** in iOS's mode, not by 16 x (+0x28 + 1) as at power-on. We replicated iOS's four stores (`+0x08` = 0x1c1, `+0x28`, `+0x34`, `+0x38` = 0x55555555) on the live iPad: the result was 1.40 Mbaud (= the /16 mode with the slot slowdown),
so the /8 mode is selected by something else. Also tested with no effect on the baud rate: UCON bits 8, 10, 11, 15; UFCON 0x131/0xc1.

## Please deliver (static; `research/2026-10-11-uart-oversample-bit.md`)
1. **Every store to the UART register block in `AppleSamsungSerial`** (not just the baud routine at `0xffffff8002d76bb8`): `start`, `startPort`/open, `setLineControl`/`setParity`/`setFlowControl`, interrupt-enable routines, `powerOn`/reset paths. List each by register offset (`+0x00` ULCON, `+0x04` UCON, `+0x08`, `+0x0c`, `+0x20..`, `+0x28`, `+0x34`, `+0x38`, anything else), the immediate or computed value, whether it is a read-modify-write and with which mask.
2. **Identify the bit(s) that change the baud divider mode.** Reason from the values: which written bit is set only when `uart-version` = 1 (or when the requested rate is high) and is otherwise absent? ULCON bits above the 8N1 fields (bits 3..7), UCON bits 3, 5, 6, 9, 12-14 and 16-31 are the untested candidates on our side. The Linux names for the Apple UCON bits are in `include/linux/serial_s3c.h` (`APPLE_S5L_UCON_*`).
3. **What does Linux's Apple S5L driver set in ULCON/UCON that iOS does not (or vice versa)?** A diff of the final register values for an 8N1 port at 115,200 would show it.
4. If the /8 mode is a UART-version-1 feature that Asahi (M1) also has, say so: Asahi's `samsung_tty.c` S5L variant may already contain or omit the bit.
Constraints as before (static only, no raw bytes/identifiers, path-limited commit, trailer).
