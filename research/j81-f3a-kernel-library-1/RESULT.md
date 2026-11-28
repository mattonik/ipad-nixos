# Research request 36 result: an A8 compute kernel library for J81

Offline only; nothing touched the hardware.

## Sources

- **Orchard's A8 compiler and driver**, read through the GitHub API: OrchardLinux/mesa `7df85604e5`. These are the A8 paths behind `g5p_usc_g4p`:
  - `src/imagination/g9p/g9p_isa.h` and `g9p_compile.c`;
  - `src/imagination/g5p/g5p_cdm.h`;
  - `src/imagination/vulkan/pvr_arch_g5p_compute.c`;
  - `common/device_info/apple-a8.h`;
  - `csbgen/rogue/cdm.xml` and `pds/pvr_rogue_pds_defs.h`;
  - the four A8 commit messages from 2026-11-20.
- **Orchard's GPU repo** (OrchardLinux/gpu `e03c572de2`, which is also this request's context):
  - `a10/ISA.md`;
  - `tools/a10/tools/isa/g9p.py` and `gen-tests.py`;
  - `a8/n102/SHADERS.md`, `BRINGUP.md` and `README.md`;
  - `tools/a8/ladder`.
- **Our own runs:** run 99's result and the request 33–35 results.

## Tags

- **J81**: run 99 shows the form working on this iPad.
- **orchard-HW**: Orchard ran it on an A8 (iPod touch 6, N102). Their notes say the Vulkan ladder passes 51 of 52 rungs. The compute rung `compute64k` writes out[gid] = gid over 2048 workgroups of 32 and checks every value.
- **captured**: Orchard quotes the form from Apple's own A8 compiler output (25 kernels captured on the iPod).
- **inferred**: A10 hardware-tested, and emitted unchanged by Mesa for the A8, but with no A8 test documented. Each one has a first test in t1.

There is no Apple binary content here. Every word comes from Orchard's MIT-licensed encoders, which I transcribed. I checked the transcription by compiling Orchard's `g9p_isa.h` in A8 mode and diffing 78 instruction encodings: they all match (`check/`). The library's store kernel equals the run 99 kernel word for word.

## Short answer

### 1. Local ID

- **At entry, r0 holds the thread's index in its workgroup.** It comes from PDS temps q0: `f0024001` plus data `0x80000000`, which is run 99's DOUTW.
- **The `0x00010001` at common dword 2 is the threads-per-group count**, in both halves. The prologue `1181 8189 4100 acb7` compares r0 with it and disables the lanes past it. For a group of N threads, the binding DMA writes `N | N << 16` there.
- **The kernel record carries the group size in KERNEL8**, the record's last word:
  - workgroup_size_x − 1 is in bits 18–26;
  - max_instances is in bits 27–31.
  - Our `0x40000000` is max_instances 8 with a 1×1×1 group, which is what Metal writes.
  - For N threads, KERNEL8 = (hw_threads − 1) << 18 | max_instances << 27. hw_threads is N rounded up to a multiple of 32 when N > 32.
- **Nothing else changes.** The PDS has no instance count, and K0 has no task size.

### 2. Thread and workgroup IDs, and address arithmetic

- **out[i] = i is four steps:**
  1. `r1 = r0 << 2`, using the A8 literal shift `119a 8302 0101 0120 0105 0120 14f0`.
  2. The A8 64-bit address build, four instructions.
  3. The A8 store.
  4. 0x82 bytes of code in all.
- **The address build** is out + r1. It works from 32-bit adds plus a carry:
  - the carry goes into the high half of r3;
  - r2 = s1;
  - r3 = r2 + r3.hi;
  - r2 = s0 + r1.

  Orchard found the A9 64-bit add faults on the A8. They also found and fixed a wrong-half bug in this build on the device.
- **The workgroup ID** is threadgroup word 0, read with `1516 0002`, then `004d`. The kernel task's PDS writes it in its once-per-workgroup part:
  - code: `c2c00003 f0024001 d3000000 f0034001 fc000002 d3000000`;
  - data: `{USC offset, 0x10, 0x90000002, 0x80000000}`.

  The kernel record then needs `K0 = 0x42106` (common store 1), and the prologue takes the form `0189`.
- **Workgroup counts minus one go in KERNEL3–5**, words 3–5 of the record. These have been 0 so far.
- **There is no A8 form for reading workgroup ID y or z.** Orchard's compiler refuses them by name, so the library is 1D.

### 3. Loads and adds

- **The A8 load** is the store's form without the store bits:
  - words: `2510 05(2d) 01(2p) 0020`;
  - then `004d`, which waits for all outstanding loads.

  There is no other fence.
- **Integer add, register form:** `3199 03(2d) srcs 00a1`.
- **Integer add, 6-bit immediate form:** `1199 03(2d) 0101|imm<<1|s<<10 0120 09a1 0070`.
- **Larger constants:** a move-immediate, then the register add.
- **Do not use the register subtract on the A8.** It returns x in A8 fragment programs. Add `0xffffffff` instead.

### 4. Several buffers

- **One DOUTD per buffer**, two dwords each into common dwords 2k, then the count into dword 2 × nbuf. This is Apple's slot layout, as run 99 uses.
- **For three buffers**, the binding data is 16 dwords, its code is `f0080000 f00a0100 f00c0200 f40e0300 d3000000`, and its record K0 is `0x40010`.
- **The prologue W1** is `0x8181 | 8 × nbuf`.

### 5. The vector add

c[g] = a[g] + b[g] with g = wg × 32 + i is 0x102 bytes of code. t4 gives every heap and stream word with its offset.

### 6. Loops and branches

The bounded loop (uniform and divergent variants) and the odd-lane conditional store are built in the compiler's own shapes. One A8/A9 rule applies: intermediate pops leave the last-read bit clear.

### 7. The test order

There are 33 tests. Each has its exact words (`kernels/*.txt`), a payload in your `j81_j2c_payload.py` format, and an expected-output sidecar. Run them in t3's risk order, starting with `store1`, which is run 99's kernel in the new layout.

## Q1: thread and instance IDs (t1, t2, t3)

| Item | Value | Tag |
|---|---|---|
| Local index | r0 at entry (PDS temps q0 low → r0, control word `0x80000000`: last, unified store, offset 0, lower 32 bits) | J81 |
| Threads per group | common dword 2 × nbuf = `N \| N << 16`, read by the prologue | J81 (N = 1); orchard-HW |
| K0 | unchanged: `0x2106` (8 registers, PDS temps 1, data 1 unit, any cluster, no fence) | J81 |
| KERNEL3–5 | 0 for one group | J81 |
| KERNEL8 | N = 4: `0x000c0000`; 16: `0x003c0000`; 32: `0x007c0000`; 64: `0x00fc0000`; 128: `0x01fc0000` | Rogue cdm.xml + Apple's A8 max_instances formula (via Orchard) |

**max_instances.** Apple's A8 driver puts 8 groups in a task when N < 5, and 32 / N groups when N is under 32. The field holds groups × N mod 32. So N = 4 also gets 0, meaning 32 lanes.

**The address arithmetic**, `out + 4 × id`:
- the left shift `119a` (Apple's A8 form; it takes a literal amount only);
- then the carry build, `119d … 00a5`, `0198 … 0154 0038`, `3199 … 08a1`, `1199 … 00a1`.

There is no 64-bit add and no multiply. For workgroup sizes that are not a power of two, `imul` `3199 … 00a2` exists (tested on the A10 and in A8 fragment programs).

## Q2: loads and adds (t1, t2)

- **ldcopy4**, out[i] = in[i], isolates the load.
- **ldk6_4** (add-immediate) and **ldk32_4** (move-immediate plus register add) isolate the two add forms.
- **ldk32_4 also catches a 16-bit adder.** Its constant `0x01008000` makes the low add carry across bit 16.
- **The two-buffer prologue** is `1181 8191 4100 acb7`, with the count at dword 4.
- **The load is the step most likely to fail first.** Apple's A8 kernels use exactly this form for every load, but no J81 or iPod run of it is documented.

## Q3: several workgroups (t3, t5)

- **Workgroup IDs:**
  - local IDs come from PDS temps q0 per instance, into r0;
  - workgroup IDs come from temps q0 in the coefficient (IF1) part, into the workgroup's common store at word 0 (x) and word 1 (y);
  - the kernel reads them with `1516`.

  Apple writes 32 bits (`0x90000000`). Mesa writes 64 (`0x90000002`), the form Orchard tested.
- **No special registers or per-instance constants are involved.**
- **Our per-record `0x80000000` is not a workgroup field.** It is the local-ID DOUTW control word in the kernel's PDS data. The record's workgroup fields are KERNEL3–5 and KERNEL8.
- **Order:**
  1. gid1x32 (the new launch, one group);
  2. gid2x32, gid4x32, gid16x32 (Orchard's proven 32-lane shape);
  3. the four-lane tests gid2x4 to gid64x4, which pack several groups into one task.
- **wgidraw4x32 is a diagnostic.** It stores the raw ID: all zeros means the ID never arrives.

## Q4: vector add end to end (t4)

`vadd4x32`: 4 workgroups of 32, 128 elements.

**Heap layout** (VA `0x3_00000000`, offsets from it):

| Offset | Item |
|---|---|
| `+0x040` | empty USC kernel |
| `+0x100` / `+0x120` | end-of-pass PDS data and code |
| `+0x140` / `+0x160` | fence PDS data and code |
| `+0x180` / `+0x1c0` | binding PDS data and code |
| `+0x1e0` / `+0x200` | kernel PDS data and code |
| `+0x240` | argument table `{a, b, c}` |
| `+0x280` | thread-count block, on its own 64-byte line as Apple's A8 driver places it |
| `+0x300` | the kernel |
| `+0x800`, `+0xc00` | inputs a and b |

**CDM stream** (29 words at 0x200000):

| Offset | Record |
|---|---|
| `+0x00` | binding: `40010 182 1c0 0 0 0 40000000` |
| `+0x1c` | kernel: `42106 1e0 200 3 0 0 007c0000` |
| `+0x38` | empty USC task: `4 10a 120 0 0 0 40000000` |
| `+0x54` | fenced DOUTC task: `7 144 160 0 0 0 40000000` |
| `+0x70` | terminate: `80000000` |

**Inputs and expected output:**
- a[k] = `0x10008000 + k`;
- b[k] = `0x01008000 + 0x100·k`;
- c[k] = `0x11010000 + 0x101·k` (the low halves carry into bit 16);
- every word from c[128] on stays `0xdead0001`.

`vadd1x32` (one group, no workgroup ID) comes first. It isolates the three-buffer binding.

## Q5: loop and branch (t2)

- **loop5x4.** A bounded loop that counts 5 down with an add of −1 (r6 = `0xffffffff`). It breaks on `!(r4 >u 0)`, then stores the iteration count. Expected output: 5 in every lane.
- **The loop's shape:** A10 `countdown`, plus the compiler's exit jump after the break, then `86d2` without the last-read bit.
- **loopdiv32** is the same loop with count = (i & 3) + 1. Lanes leave at different iterations, so it expects 1 2 3 4 1 2 3 4 …. This is the case where Orchard's A9 lost the GPU with the wrong pop bit, so it runs last of the loop tests.
- **condodd32**, if (i & 1) out[i] = i, uses the compiler's if/else shape with an empty else:
  - `and`, then `cmp_imm eq 1`, `push_if`, a jump to the else, the store, `else`, a jump to the pop;
  - then pop 1 level without the last-read bit, then the final pop.

  Expected output: odd slots = i, even slots keep the sentinel.
- **The loop and branch encodings are A10-tested but not A8-tested** (t1 marks each as inferred).

## Q6: what can go wrong (t6)

t6 lists 14 signatures, each with its cause, the registers to read and a way to tell the causes apart. These are new compared with runs 96–99:

- **Wrong high address word.** A BIF fault with RNW = 0 and a high ADDRESS (`0x1_…` or `0xff_…`), from the carry build. `carry1` forces a carry on purpose.
- **Load faults.** RNW = 1 at the input VA.
- **Read-only page.** Expect FAULT bit 0 plus FAULT_RO bit 4 in `0x12b0`, with ADDRESS in `0x12b8`/`0x12bc` (Rogue field layout). Make the page read-only with PTE bit 1.
- **One word past the page.** A partial result, plus FAULT without RO at the next page.
- **Unaligned store.** Unknown behaviour; test it last.
- **A register beyond the allocation.** A wrong value with no fault (on the A10). `reg11a8` is meant to show this, and `reg11a16` should pass.
- **Hangs.** Uniform loops before divergent ones, so a hang points at the stack rule.

## Q7: limits and order (t7)

- **Threads per workgroup:** 512 at most.
- **Apple's A8 residency rule:** 8 registers allow 512 threads, 16 allow 256, 32 allow 128. The A8X's constants are not established.
- **Registers:** K0 field 2n = 8n registers, and the DOUTU temps are 0x10 per 8 registers. Both must cover the highest register used.
- **Register reach:** one-source forms reach r15 only, and address pairs and the mask stack stay below r16.
- **PDS data:** the binding needs (buffers + 1) units.
- **Common store:** 1 unit up to 7 buffers.
- **Kernel size:** no size field; the slot here is 0x500 bytes.

The safe order is `j81_kernel_library.py list`:

| Risk | Tests |
|---|---|
| 0 | store1 |
| 1 | lid1 |
| 2 | lid4–32, the loads and adds |
| 3 | lid64/128, gid×32, vadd1x32, wgidraw, lid48 |
| 3.5 | gid×4 |
| 4 | vadd×, loop5x4, condodd32 |
| 5 | loopdiv32, carry1 |
| 6–7 | lid256, lid512, the register limits |

Run one test per boot and stop at the first failure.

## What the module needs

1. **Fill the whole output page** (1024 words) with `fill_value` before the job, not only out+0 and out+4.
2. **Read back `read_words` words** and compare them with `expect_hex` from `<payload>.expect`. A word of `0xffffffff` in `expect_hex` means "any of 0–3" (wgidraw4x32 only).
3. **Map the heap image's 0x1000 bytes** at `0x3_00000000`. It was 0x2c0 bytes; the inputs now live in it at +0x800 and +0xc00. The payload keys are unchanged.

## Not resolved

- **The A8 load, the add-immediate, `and`, the compare, push/else and the loop forms** have no documented A8 hardware run (inferred). Each has its own first test.
- **Workgroup ID y and z** have no captured A8 form.
- **Packing several small groups into one task** (N < 32 with max_instances 0) is Apple's formula and has not been run by Orchard; gid2x4 tests it.
- **The A8X's residency constants** and its register-file size.
- **What the firmware does after a USC write fault on J81**: whether it recovers, or only the watchdog does.

## Files

- `t1-isa-forms.tsv`: every form, with words, fields, source line, evidence, tag and its first test.
- `t2-kernels.tsv`: 14 kernels, instruction by instruction: byte offset, words, meaning, form and evidence.
- `t3-launch.tsv`: all 33 tests: registers, prologue word, count dword, binding and kernel PDS data and code, K0, KERNEL3, KERNEL8 decoded, code size, risk.
- `t4-vector-add.tsv`: `vadd4x32` end to end: every heap item and stream word with VA, offset and decode.
- `t5-expected.tsv`: the expected output of every test at a glance.
- `t6-failures.tsv`: failure signatures and the registers to read.
- `t7-limits.tsv`: the limits and the order to measure them.
- `j81_kernel_library.py`: the generator. `list`, `dump TEST`, `payload TEST OUT` (writes the payload plus `OUT.expect`), and `grid`.
- `kernels/`: every test's dump.
- `payloads/`: every test's payload and `.expect`.
- `check/`:
  - `grid.c` compiles against Orchard's `g9p_isa.h` with `ralloc-stub.h` copied as `util/ralloc.h`;
  - both grid outputs, which are identical.
- `SHA256SUMS`.
