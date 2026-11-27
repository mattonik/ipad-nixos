# Research request 22 result: J81's firmware idle loop, decoded with Orchard's MiniM expander (19H394)

Sources:
- the J81 19H394 META firmware (seg0 and coremem), expanded with Orchard's `minim.py` (blob `fc30a863…`, from `tools/orchard-minim/`, read before use) and our own binutils-2.30 metag `objdump`. The output stays private;
- the 19H394 AGXG4G kext;
- run 70;
- request 9's root table.

Tags: **fwdis** (the decoded firmware), **code** (the kext), **capture**, **orchard**, **inferred**. There is no firmware or kext content here beyond addresses, offsets, field names and small constants, and no listings. `minim.py` is provisional: 730 of 33,375 seg0 lines and 119 of 6,466 coremem lines are UNKNOWN, so every fwdis claim is a reading of a provisional decode.

## Short answer

- **The firmware never touches `0xbc8`, and neither does Apple's host.** I searched immediates, constructed addresses and data words in every segment. The firmware's MTS accesses (t3):
  - it sets the thread association (`0xb30 = 0xffdf`, `0xb40 = 0xffff`, exactly run 70's values) and two interrupt enables;
  - it kicks itself through `0xb00`;
  - it writes `0xb08` (0 before each sleep);
  - it reads `0xb10` (the DM of a presented task) and `0xb20`.

  So `0xbc8 = 0` is what an iOS boot has too, unless one of Apple's 12 computed ConfigRAM entries sets it. It is not a firmware gate (inferred).
- **The idle loop sleeps on a META trigger, not on memory** (t2).
  - Thread 0 sets TXMASK `0x21` and routes hardware vector `0x04820700` to trigger 5. Then it blocks in a TXSTAT read at `0x80009c1c`.
  - Trigger 0 is its timer tick (it re-arms and goes back to sleep). Any other trigger means the MTS presented a task.
  - On an MTS trigger the firmware reads `0xb10` for the DM, checks a gate, and on success runs the DM pass. The pass reads the four producers, then consumes **the device-control ring first** (`0x10001cfc`), then TA.
- **The gate for DM0 depends on two host-provided root pointers** (t4):
  - root `+0x70` → POLICY, which needs `+8 <= 1`;
  - root `+0x74` → a `0x28`-byte object, which needs word 0 = 0 and a further check (`0x1000374c`) to return 0.

  If the gate fails, the firmware goes back to sleep with no write the host can see. That matches run 69/70 exactly, but so does "the trigger never arrived". **P1** tells them apart with three RGX reads (`0xb08`, `0xb10`, `0xb20`).
- **Corrections:**
  - The alive record's `+4` is a literal the loop builds once at entry. The firmware posts alive once per entry, so **one alive record is normal on J81**. Request 20's "scheduler not running" reading was wrong.
  - `+8` (`0x8000a2c8`) is a data pointer, not a PC.
  - The run PCs that requests 16 and 20 called "outside the text" (`0x80009c74`, `0x100228xx`–`0x100229xx`) are inside it under MiniM's 2:1 addressing. `0x80009c74` is the loop's timer-wake path, so the firmware does wake on its timer.
  - RGX is at META `0x02000000`, not fwaddr 0.

## Q1: memory map (t1)

- **Code addresses:** MiniM code PCs are segment base + 2 × storage offset; data uses plain storage addresses.
  - seg0 code reaches `0x1002f2e0`; its initialised data starts at `0x10013c00` (GbP).
  - coremem code reaches `0x8000a668`. It holds the idle loop (`0x80009b34`–`0x80009e70`) and a far-call stub table into seg0.
- **Data:** `0x8000a000` and `0x8000a2c8` are data in zeroed core memory above the coremem image.
- **Pointers the firmware uses:**
  - GbP `+28` = root;
  - root `+0x454` = config;
  - GbP `+36` = `0x02000000` (RGX);
  - GbP `+100` = `0x8000a000` (the private struct).
- `0x10000358` (request 17's halted PC) is an UNKNOWN line.

## Q2: the loop (t2)

**At entry:**
1. Build the wait-PC literal.
2. Post alive.
3. Clear kick state.

**Each pass:**
1. Acknowledge trigger 5 (TXSTAT = `0x20`).
2. Store 1 to the trigger-status block `0x04820000`, and RGX `0xb08 = 0`.
3. Run the sampler, if config `+0x250` and `+0x258` are both nonzero (the same gate pair as Orchard's A9 `priv+0x228`/`+0x22c`).
4. Sleep in the TXSTAT read.

**On waking:**
- **Timer only:** re-arm the period from priv `+0x2c4` (or `+0x270`) and sleep again.
- **Otherwise:** DM = RGX `0xb10 & 0xf`, then gate(DM). If it passes, run the DM pass; if not, sleep again.

## Q3: firmware MTS accesses (t3)

See t3 for every access with its PC, value and guard. There is no access to `0xb98`–`0xbc8`. `0xb70`/`0xb78` show no store in the decoded code; they may be reset values.

## Q4: what gates the device-control pass (t4)

There are four conditions:
1. The MTS raises the trigger routed by vector `0x04820700`.
2. `0xb10` names DM0.
3. The POLICY / `0x28`-object gate passes.
4. priv `+0x170` bit 1 is clear.

Only the gate pointers are host inputs. iOS fills root `+0x64`..`+0x74` from its fw `+0x240`..`+0x260` objects (`0x6689b04`–`0x6689b88`); request 9 named them channel, scheduler, POLICY and a `0x28` object. **Please confirm that blob f sets root `+0x70` and `+0x74`.**

## Q5: ring protocol (t5)

The firmware side matches Apple's host and run 69:
- control at root `+0x18`, buffer at `+0x1c`;
- consumer at `+0`, producer at `+0x10`, stride 20;
- type at `+0`, with types 3–10 in a jump table (8 included);
- no size or mask fields read.

The producer is read once at the start of each pass.

## Q6: next boots (t6)

1. **P1 (read-only):** read RGX `0xb08`, `0xb10` and `0xb20` before the kick, right after it, and 10 ms later. This shows whether the kick reached META.
2. **P2:** root `+0x70`/`+0x74`, only if blob f lacks them.
3. **P3:** a non-counted kick, `0xb00 = 0x00`, the firmware's own self-kick value.

N2 (`0xbc8 = 1`) drops to a hardware-only test. N3 (CONTROL `+0x20 = 1`) is unchanged.

## Not resolved

- Whether the MTS needs `0xbc8` to raise its trigger (hardware). This includes the 12 computed ConfigRAM entries.
- The handled-entry path for type 8 inside the jump table.
- `0x1000374c` (the `0x28`-object check).
- The meaning of RGX `0xb08`/`0xb10`/`0xb20`, beyond how the firmware uses them.

## Files

- `t1-memory-map.tsv`: Q1, addressing, segments, the alive words, the RGX base and the pointers.
- `t2-idle-loop.tsv`: Q2/Q4, the loop step by step, the trigger routing and the gate.
- `t3-firmware-mts.tsv`: Q3, every firmware MTS access.
- `t4-gate.tsv`: Q4, the conditions for a device-control pass and who provides each.
- `t5-ring.tsv`: Q5, the consumer as the firmware sees it.
- `t6-next-boots.tsv`: Q6, the ranked boots.
- `SHA256SUMS`.
