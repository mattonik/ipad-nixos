# Research request 24 result: why the META slave port never completes on J81 (MSLVCTRL1 = 0x06000040), and host-visible liveness

Sources:
- the 19H394 AGXG4G kext;
- upstream `pvr_rogue_cr_defs.h` and `pvr_fw_meta.c`;
- the decoded META firmware (Orchard's `minim.py`, provisional, private);
- the run notes.

Tags: **code**, **source**, **fwdis**, **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

- **Apple's J81 host never reads META through the slave port while the firmware runs normally** (t1). It uses the port in only three places:
  1. after the firmware posts **event type 6** (its park/stop request): it *writes* TXENABLE = `0xfffffffe` to T0, then T1, then resets META;
  2. in **stop-for-inspection**, with the same T0 write first;
  3. in the **failure dump**, which reads core registers only after thread 0 has been stopped.

  So our read of a running firmware is a use Apple never makes. The precondition both Apple and upstream use is MSLVCTRL1 READY | GBLPORT_IDLE (`0x05000000`) before and after each request.
- **`0x06000040` means a request was accepted and is waiting inside META:** both idle bits are set and READY is clear. Bit 6 isn't defined upstream (t2).
  - Slave-port reads worked in runs 54–61, while the pre-E1 firmware was busy. They stall since E1, when the firmware first reaches its idle loop and blocks in a TXSTAT read with thread 1 off. Run 76 ruled out the protect bit.
  - The most likely cause is that **the META core doesn't service core-register requests while every thread is blocked on a trigger** (clock or idle gated) until a trigger wakes it (inferred).
  - That makes the stall and the ignored kick one symptom: thread 0 never gets a trigger.
- **The best liveness signal that needs no slave port is MSLVIRQSTATUS bit 2** (RGX `0xac8`, TRIGVECT2), the META-to-host interrupt (t3). The firmware enables it (`0xad0 = 4`, level `0xad8 = 1`). Upstream clears it with a write of `0xfffffffb`. Clear it after alive, kick, and watch for it to come back.
- **The pending slave-port request is a liveness probe in itself.** If MSLVCTRL1 READY rises on its own later, META woke, probably on its first timer tick (S1).
- **RGX `0xb08` ignores host writes**, so request 23's L1 can't be used.

## Q1: Apple's host and the slave port (t1)

Every `0xa00`–`0xa18` access in the kext is in t1. Besides the three paths above, a `0x17` core-register query exists only for configurations without a GPC object; J81 uses the Fender "can park" check instead.

## Q2: MSLVCTRL1 (t2)

t2 decodes every bit and gives the reading. Is it normal for a read of a META sleeping on a trigger to wait until the thread wakes? That is the reading that fits all the runs (inferred), but there's no public statement of it in upstream.

## Q3: liveness without the slave port (t3)

The candidates, from best to worst:
1. `0xac8` bit 2;
2. MSLVCTRL1 READY rising by itself;
3. the DC consumer and the event write index (already used);
4. a marker through the type-8 handler: it copies state `+0x1020` to root `+0x1480`.

The idle loop writes only core memory and META registers, so DDR has no heartbeat.

## Q4: what drives external line 0 (t4)

It's not visible in the code. The firmware routes line 0 and listens, the host never touches META's trigger block, and no host register other than MTS_SCHEDULE raises a trigger. That line 0 is the MTS background request is inferred.

The firmware enables everything it can see (associations, interrupt enables, vectors, TXMASK). The ConfigRAM list still has 12 computed entries I couldn't resolve. An interrupt-context kick (`0x30`) may take a different path to META (inferred).

## Q5: next boots (t5)

1. **S1 (read-only):** log MSLVCTRL1 before the first request. After the stall, poll it for 30 s, and read `0xac8` after alive.
2. **S2:** clear `0xac8` bit 2 (`0xfffffffb`), kick, and poll bit 2 for 1 s.
3. **S3:** a `0x5a` marker in state `+0x1020`, then check root `+0x1480`. It's lower priority, because the handler may walk that many list entries.
4. **P3:** `0xb00 = 0x00`.
5. **P4:** `0xb00 = 0x30` (interrupt context).

A slave-port read before alive is already known to work. Stopping thread 0 with a TXENABLE write is only for an end-of-run snapshot.

## Not resolved

- Whether a sleeping META really gates slave-port core access (S1 tests it).
- What drives line 0 in hardware.
- How the firmware raises TRIGVECT2. No META kick or trigger-block write for it was found in the decode.
- Bit 6 of MSLVCTRL1.

## Files

- `t1-apple-slave-port.tsv`: Q1, every Apple slave-port path with its order and preconditions.
- `t2-mslvctrl1.tsv`: Q2, the bit decode of `0x06000040` and the reading.
- `t3-liveness.tsv`: Q3, host-visible liveness signals: asleep against running.
- `t4-line0.tsv`: Q4, what drives external line 0 and what is enabled.
- `t5-next-boots.tsv`: Q5, the ranked boots.
- `SHA256SUMS`.
