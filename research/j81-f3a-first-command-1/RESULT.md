# Research request 19 result: the first host-to-firmware command on J81 (19H394)

Sources:
- the 19H394 AGXG4G kext (J81 host);
- Orchard's reconstructed `pvr_apple_s8003.c` (sha256 `0efc2a93…`, request 9's pin; "S:n" = its line n);
- the run state in `context/`.

Tags:
- **code**: the J81 kext;
- **orchard**;
- **capture**;
- **inferred**.

There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

- **The J81 ring protocol is Orchard's A9 one, confirmed in Apple's own `AGXMetaFirmware::submitDeviceControl`** (`0x66914dc`, t1):
  - consumer at control `+0x0`, producer at `+0x10`, 256 entries wrapping at `& 0xff`;
  - 20-byte entries: type at `+0`, argument at `+4`, zeros after;
  - full when consumer == (producer + 1) & 0xff;
  - order: write the entry, `dmb`, advance the producer, `dmb`, Fender `+0x14 = 7`, check the state, then MTS_SCHEDULE `0xb00 = 0x10` (DM0, the same value as TA);
  - completion: the firmware moves the consumer. No event record is involved.
- **The command types have Apple's own names in the kext** (table at `0x6f2dd38`, t2). Orchard's "slot load" is type 3, **DeviceSetGARTPhysical**. Orchard's empty first command is type 8, **PerfCtrSamplerCommitCounterList**. The J81 kext builds that one from a `{8, 0, 0, 0, 0}` template and sets its payload count in state `+0x1020` (size / 32, payload at state `+0x40`; `0x668c8cc`). So with `+0x1020 = 0` it commits an empty list. This is the safest first command.
- **Drain the event ring from now on.** Orchard notes that alive is posted on every scheduler run (about 290 a second) and that a full event ring stalls the firmware in about a second. Advance event control `+0x0` as you read.

## Q1: ring protocol

t1 lists every field with Apple addresses and Orchard lines. Pointers in the entries: types 3 and 8 carry none. Their memory is found through fixed objects whose firmware addresses the firmware already has from root and state.

## Q2: the slot load (t3)

A "slot" is one of 8 GPU MMU contexts. Slot 0 is the firmware's own; the host's run from 1, one per VM (A8/J81 layout).

To load slot n:
1. Write the page-catalogue physical address into MMU_ROOT[n]. That is fw `+0x400`, 8 × u64, with its firmware address in state `+0x1048`.
2. Write a tag into TAG_HOST[n]. That is fw `+0x3f0`, 8 × u32, firmware address in state `+0x1044`. Start with `0x00400000`.
3. Send `{3, n}`.

The firmware loads the context from MMU_ROOT[n] and copies the tag into TAG_SEEN[n] (fw `+0x3f8`, firmware address in root `+0x458`); Orchard checks that copy. Orchard sends a slot load when a VM first attaches (`s8003_vm_attach`), i.e. before that VM's first job, not at boot.

Orchard also puts the kernel VM's catalogue into MMU_ROOT[0] before boot. Make sure our blob does the same as `BIF_CAT_BASE0`. Which BIF registers the firmware programs for a slot is firmware-side and not visible from the host (inferred: the `BIF_CAT_BASE` registers for context n).

## Q3: kick and completion

- **Kick:** RGX `0xb00 = 0x10`, after Fender `+0x14 = 7`, with the GPC state checked as in request 17. TA is `0x10`, 3D `0x11`, CL `0x12` (`0x6691018`, `0x66911f0`).
- **Completion:** the consumer index reaches the new producer. Apple waits up to accel `+0xc20` seconds and otherwise logs "Timeout while waiting for firmware to process submitted command (command type %s)" (`0x668d540`–`0x668d5bc`). Orchard waits 3 s.
- **A rejected command:** no specific event type for that was found. Orchard logs unknown event types as firmware faults; event type 13, AckChannelError, exists as a command, the host's acknowledgement.

## Q4: the first command (t4, C1)

1. State `+0x1020 = 0`.
2. DC entry `{8, 0, 0, 0, 0}` at DC buffer[producer].
3. `dmb`, producer = (producer + 1) & 0xff, `dmb`.
4. Fender `+0x14 = 7`, then RGX `0xb00 = 0x10`.
5. Poll DC control `+0x0` every 1 ms for up to 3 s.

It needs no memory beyond the blob. Afterwards read the DC control block, the event ring (and drain it), and the log control at root `+0x28`.

## Q5: risks and order (t4)

1. **The event ring filling.** This is the risk that can wedge the firmware by itself, so drain it on every boot.
2. **C1:** the empty counter-list commit.
3. **C2:** load slot 1 with our catalogue and tag `0x00400000`; expect TAG_SEEN[1] = `0x00400000`.

Leave TA/3D until a parameter-manager set exists for the VM (type 12 DevicePMAllocation, and Orchard's PM id per VM). Compute (type 2, kick `0x12`) needs no PM and is the natural first job. A bad catalogue in C2 should end in a BIF fault rather than a bus hang (inferred).

## Not resolved

- The exact firmware response to a malformed entry.
- The J81 host's own call sites for type 3. They go through ring wrapper objects (accel `+0x8d8`/`+0x8e0`/`+0x8e8`), not traced here; Orchard's use is the reference.
- Whether J81's firmware wants anything in the 12 tail bytes of a type-3 entry. Orchard leaves them zero.

## Files

- `t1-ring-protocol.tsv`: Q1, the ring control and entry fields, ordering, kick and completion.
- `t2-command-types.tsv`: Q2, Apple's command-type names and the two commands Orchard uses.
- `t3-slots.tsv`: Q2, the MMU_ROOT, TAG_HOST and TAG_SEEN objects and slot numbering.
- `t4-next-boots.tsv`: Q4/Q5, the ranked steps with exact values.
- `SHA256SUMS`.
