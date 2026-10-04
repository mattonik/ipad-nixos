# ANS1 submission boundaries: offline characterization

Date: 2026-10-04. This extends the [storage bring-up report](j81-ans1-storage-bringup.md).
The result is a host-only reproducer and a narrowed repair plan. It does not
change the ANS driver, access media, or broaden the recorded single-block
hardware result.

## Source and method

The test reconstructs `drivers/block/asp.c` from the complete new-file hunk in
[patch 0015](../kernel/patches/0015-ans1-storage-driver-and-core-support.patch),
then applies [observation-only patch 0012](../kernel/patches/0012-ans1-asp-observation-only.patch)
with `--fuzz=0`. These are the isolated storage payload's source inputs. The
public implementation is Hoolock's
[`asp.c` at ed8528f](https://github.com/HoolockLinux/linux/blob/ed8528f482a526371e59711645794c91fafb2b42/drivers/block/asp.c).
No external source download is needed to run the test.

`kernel/test_ans1_submission_audit.py` extracts the actual command-buffer
address helpers, SGL builder, submit function, queue callback and constants.
It compiles them against synthetic request, scatterlist and mailbox stubs.
Request setup always succeeds in the stub: **the test deliberately bypasses
block-layer admission and DMA mapping**. The command-header stub preserves
its 48-byte size and tag use; other fields and mailbox bit encodings are
outside this test. Kernel concurrency, DMA ownership, firmware responses and
recovery are not modeled.

## Reproduced results

| Synthetic input | Existing hardened source behavior | Meaning |
| --- | --- | --- |
| One aligned 4 KiB entry, each tag 0–15 | Correct page in selected slot; one submission; no warning | Normal bounded case works in the model |
| 4,068 aligned pages | Exactly fills SGL; adjacent slot unchanged | `(16320 - 48) / 4 = 4068` entries fit |
| 4,069 pages | Bounds guard returns after 4,068 entries; caller still submits and reports success | Guard protects host memory but does not propagate failure |
| Segment length 1 byte | Unsigned subtraction wraps; loop fills SGL to capacity guard; submission occurs | Length divisibility is not locally enforced |
| DMA address `0x100001`, length 4096 | Encoded page `0x100`; no warning | Shift discards unrepresentable byte offset |
| Tag 16 | Header copied into sentinel slot before guard returns I/O error; no mailbox send | Tag check follows the memory access |
| Mailbox timeout / generic error | Request already started; queue callback returns timeout / I/O error | Error mapping reproduced; ownership/recovery not modeled |

The invalid-tag test allocates an extra sentinel slot, allowing observation
of the ordering bug without an out-of-bounds host write. The real coherent
allocation has only 16 slots. For malformed lengths and excess pages, the
existing guard bounds the host loop to 4,068 writes. ASan/UBSan therefore
remain clean during these semantic fault reproductions. A passing test
confirms the behavior, **not that the driver is repaired**.

These tests do not prove that malformed requests reach this code through
ordinary J81 I/O. Queue depth is 16 and logical block size is 4096. Moreover,
the source sets `max_hw_sectors = ASP_CMD_MAX_SECTORS`; Linux's
[documented unit](https://www.kernel.org/doc/html/v5.15/core-api/kernel-api.html)
for this limit is 512-byte sectors, not ASP's 4096-byte blocks. Consequently
4,068 here represents a 2,082,816-byte ceiling, or at most 508 whole 4-KiB
blocks before other limits. The 4,069-page fixture exceeds that ceiling and
is not a demonstrated normal-path overflow. Do not raise the queue limit as
a performance adjustment during bring-up.

## Lifecycle questions remain source-only

`asp_setup_rw()` allocates/maps the SGL. Completion unmaps/frees it without
clearing `iod->sg`; the mapping-failure path also frees without clearing.
`apple_asp_queue_rq()` returns submit errors without a local cleanup call.
These observations justify tracing request reuse and error ownership against
the pinned block layer. This harness does not establish an actual kernel
leak, double free or use-after-free. The next test should exercise a reused
request rather than assume fresh zeroed private state on each operation.

Auxiliary-read buffers are zeroed after `dma_map_sg_attrs()`. A follow-up
must check DMA ownership and platform coherency requirements. The successful
user-area read does not validate that different namespace path.

Completion looks up a tag and optionally copies `iod->buf_len` into an admin
buffer. Further tests should cover startup, duplicate/stale completions,
admin-buffer bounds, timeout and shutdown order. An in-range non-NULL tag
lookup alone does not prove correspondence to the outstanding command.
No recovery scheme or generation counter is proposed without protocol evidence.

## Repair plan before broader storage experiments

1. Validate tags before any command-buffer pointer calculation or access.
2. Return SGL validation failure to the queue callback and abort submission.
   Preflight segment alignment, count, address representability and agreement
   with command length before writing the list.
3. Establish one cleanup/ownership contract for setup, failed submission and
   completion; clear released pointers and test request reuse.
4. Add negative tests requiring no mailbox sends or queue writes on malformed
   input, then prepare an inactive candidate patch and perform a laptop build.
5. Review completion and timeout ownership before larger read workloads.

A bounds-only patch would leave request-lifecycle uncertainty unresolved.
This outcome keeps runtime unchanged and records the prerequisites. Preserve
the central read-only gate and removal of `WRITE_UNLOCK` in any future patch.
The established observation-only hardware procedure remains the scope limit;
this work supplies no evidence for bulk reads, filesystem mounts or writes.

## Run and validation

```sh
python3 kernel/test_ans1_submission_audit.py
ASAN_OPTIONS=detect_leaks=0 python3 kernel/test_ans1_submission_audit.py --sanitize
```

Both commands passed with GCC in the hosted workspace; the patch applies with
zero fuzz. LeakSanitizer is disabled because this environment cannot inspect
the process task list; ASan and UBSan remain enabled. Static/stack synthetic
objects do not model kernel allocation leaks. No Nix build, boot, storage
read or device access occurred. The standalone test leaves the shared offline
runner's check counts unchanged.
