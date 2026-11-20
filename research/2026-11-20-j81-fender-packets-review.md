# Review of the three 2026-11-20 Fender / observer packets, and how we can take the measurement

Packets: `to-builder/2026-11-20-j81-ios-fender-id-8d0886b` (REVISION 8d0886b6...), `...-ios-fender-id-probe` (539a5b51...), `...-ios-observer-receipt` (bcad3c9c...). The two object packets carry the same `probe.o` (cmp identical); `8d0886b` adds `verify_capture.py`. The receipt packet points at our own 19H394 run (boot 846527FB..., observer module 3f409df1...).

## Offline checks (done on this Mac, no device)
All SHA256SUMS verify (three packets and the pregpc receipt). `sh check.sh`: `PASS: missing map, closed gate, bit 29 clear/set, zero ID, pre-ID fault checkpoint` and `PASS: host-tested and iPadOS __text bytes match` (macOS and iPhoneOS objects have identical __text). `verify_capture.py` is the third PASS line in OFFLINE.txt (rejects missing/partial/page-low/duplicate/cross-boot/out-of-order/malformed rows).

## What they ask
One paired record on iPadOS: page-5 +4 (gate, bit 30), Fender +0 (physical 0x201e00000, the sleep-control word, bit 29) and GPU ID (+0x20 of 0x201000000) read in that order in one invocation, as the only ID read, with the Fender word taken through the ORIGINAL Fender mapping (not logging scratch), one `J81_FENDER_ID` row per boot with boot UUID, plus the same-boot `GPC TICKS` row. Their object needs a "diagnostic host with the three live mappings"; the packet ships no host.

## Why our existing probe already is such a host, and what it lacks
Our run-3-derived module owns all three mappings on 19H394 (page 5 via the PMGR region, the Fender block via `ml_io_map(0x201e00000)` kept in x23, the core via `ml_io_map(0x201000000)`) and is the module that returned 0x00070500 before. Its P1 `G=` field is, as the packet says, NOT a Fender read: x23 is re-pointed at the log buffer at 0x437c before the P1 prints, so `G=` read the first word of the log buffer (text-like values 0x30303000, 0x33303800). So no Fender +0 value exists for any iPadOS boot yet.

## The probe we can build now: `fender` variant (3 words, `boot/make_j81_ios_state_probes.py`)
- 0x42e8 `mov w25,w0` -> `str x23,[sp,#0x440]` (saves the original Fender mapping pointer right after the map call and the +0x1000 state read; the slot is inside the module's 0x500 frame and unused);
- 0x42ec `cbz w25,...` -> `cbz w0,...` (same test, on the register that still holds the state word; the only side effect is the V= value in the abnormal "state != 0" STOP record);
- 0x43f0 `mov x0,x23` -> `ldr x0,[sp,#0x440]` (the P1 `G=` read now loads the saved pointer: a real 32-bit read of Fender +0 through the original mapping, after the three page-5 samples and just before the core read).
Output: P1 `G=` = Fender +0 raw word of that boot; the core ID is read next as before. Everything else in the record keeps its meaning. This is not the packet's object (their read ordering and DSB differ and it has a stage/checkpoint record), so it satisfies the intent (a clear-or-set Fender +0 sample immediately before a successful ID on a labelled boot) but is not the exact component; the result will be reported as such. The disassembly of the patched words is checked; the module is `j81-ios-state-probes/checkra1n-kpf-pongo-j81-fender` (sha256 in SHA256SUMS next to it). Read-only; no store added. Still not run.

## Reading
Our Linux data already say: before the hanging ID read, Fender +0 = 0x40000000 (bit 29 clear) on boot 49df36fd and on the 2026-11-06 wake logs. The paired iPadOS word decides it: bit 29 set on the working boot means a real Linux difference; clear means this packet's hypothesis is excluded at that point and attention stays on the page-1/page-4 pair, CPU TVM/DPE and the unwritten startup stores.
