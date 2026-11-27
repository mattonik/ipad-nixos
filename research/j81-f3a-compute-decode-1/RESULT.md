# Research request 31 result: J81's compute record builder and microsequence (19H394)

Sources:
- the 19H394 AGXG4G kext: the compute channel's record fill (around `0x667c1b4`–`0x667c348`), its HAL hook `agxkHalConfigureOptimizedCDM` (`0x669cba0`) and the microsequence emitters (`0x669ca18`–`0x669cb30`, `0x669cd98`);
- the decoded firmware's CL reader;
- Orchard's A9 `s8003_submit_compute` (OrchardLinux/linux `059fadee`);
- Mesa (by name only).

Tags: **code**, **fwdis**, **orchard**, **source**, **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants. The microsequence words are opcode values and operand roles.

## Short answer

- **The J81 compute record (t1) is the A9's record with two J81 additions:**
  - a **cluster mask at `W+0x18`**: `0xff`, all eight clusters, or `0xf` on a command flag. On 16G77 it was `W+0x20`;
  - a **per-cluster 64-bit address array at `W+0x78`**, its count from the accelerator (8 on A8X, inferred). With stride 0 the array is all zero.

  The fields stop at `W+0x284`, so the size is the A9's `0x290`. The A8's `0x298` doesn't fit the field set.
- **The terminate word at `W+0x244` comes from user space on 19H394** (copied from the command, `cmd+0xf0`). There's no kext constant to read, so J1 has to choose: A8-family `0x00900004` first, A9 `0x00a00004` second (inferred). The whole `+0x1ec`–`+0x23c` block (state, tail, terminate, PDS store/resume) is copied from the command at the A9's offsets.
- **The microsequence (t2) uses the A9's opcodes and operand order:** `0x32` start, `0x80000018` wait, `{0x101, 0x004a000a, 1, 1}` event wait, `0x18`, `0x33` finish, and end `0x40000017` (assumed). J81 fills four `0x32` words that the A9 leaves 0; all are 0 for an empty job. The `0x33` op ends with the second stamp address, seq, and the jump back of `-0x6c`, as on the A9.
- **No host handshake gates DM2 work** (t4). There's no PM and no charge grant for compute, and the governor pins already hold the perf state. Slot 1 and its tag are loaded.

## Q1: the record builder (t1)

Apple's fill:
- **W `+0`** = `{3, 0}`;
- **`+8`** = slot;
- **`+0xc`** = the dependency object;
- **the HAL fields:** `+0x10` config, `+0x14` CDM item mode (`{0, 2, 3}`), `+0x18` cluster mask, `+0x60`/`+0x68`/`+0x70` (tail, PDS terminate, CDM control stream), and the per-cluster array;
- **the user block** at `+0x1ec`–`+0x244`;
- **the tail:** flags, the stamp addresses `+0x258`/`+0x25c`, counters, the job number `+0x270`, the wait/dependency addresses `+0x278`–`+0x284`.

Every row in t1 has its source and the A9 equivalent.

## Q2: the microsequence (t2)

The emitters are listed with every operand and its role: constant, firmware address, counter or flag. `global` is root `+0x6c` (the `0x8c0` compute block) + `0x720`. For an empty job the microsequence is 39 words, `0x9c` bytes, within the A9's `0xc0` region.

## Q3: J1 end to end (t3)

On top of J0's channel page:
- ring[0] = the record's firmware address, and the host watermark = 1;
- the record per t1 and the microsequence per t2;
- the CL entry `{2, 0xc0130000, 1}` and the `0x12` kick;
- in slot 1: a CDM control stream that is only Mesa's `ROGUE_CDMCTRL_STREAM_TERMINATE` word, and Mesa's fence-terminate PDS program in the PDS heap (Orchard A8: `0x3_0000_0000`);
- also in slot 1: the hardware objects and a zero page at VA 0.

The job is done when both stamps reach 1 and the watermarks reach 1.

## Q4: gates (t4)

There's no handshake. The perf state is held by the governor. The PM and charge grant are only for TA/3D.

## Q5: boots (t5)

1. **J1:** terminate word `0x00900004`, mask `0xff`, size `0x290`.
2. **J1b:** `0x00a00004`.
3. **J1c:** mask `0xf`.
4. **J2:** a one-word PDS store.

Telling the failures apart:
- stamps and watermarks at 1: success;
- the consumer moves but the stamps stay 0: the record or microsequence is rejected (check the event ring);
- a bank-0 fault: a bad slot-1 VA for the control stream or the PDS program.

## Not resolved

- The value user space normally puts at `+0x244` on 19H394.
- The microsequence finaliser's end word (assumed `0x40000017`).
- The exact semantics of the counters at `+0x260`–`+0x26c` (seq at `+0x260` per the A9).
- The Mesa encodings themselves (take them from Mesa's `pvr_csb` and `pvr_pds` generators).

## Files

- `t1-record.tsv`: Q1, every record field with its J81 source, the A9 equivalent and the empty-job value.
- `t2-useq.tsv`: Q2, the microsequence ops and their operands, against the A9.
- `t3-empty-job.tsv`: Q3, J1 end to end.
- `t4-gates.tsv`: Q4, what could stop a correct first job.
- `t5-next-boots.tsv`: Q5, the ranked boots and the failure modes.
- `SHA256SUMS`.
