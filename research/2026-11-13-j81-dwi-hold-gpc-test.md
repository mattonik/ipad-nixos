# J81 GPC comparison with DWI held from early boot

Prepared 2026-11-13; **not run**. This test asks whether the Linux page-5
`+4` observation after GPC state 1 changes when DWI was already held at the
first sampled kernel checkpoint, rather than manually switched back on later.
It is not a GPU core-access or rendering test.

## Build and evidence

- Hold image combined SHA-256:
  `24c43c226656fea6d5eef3ab2ca4ae46f550672a5763dd85bede8bbbe49e09ce`.
- Exact instrumented kernel `/sys/kernel/notes` SHA-256:
  `5db452029d50cfaabd6cfb17f716509c895764543f87b7fee72709bca52aa9d0`.
- `gpu-pmgr-cycle.ko` and `gpc-page5-kpoll.ko` were built against that
  kernel's exact development tree; their byte hashes happen to match the
  earlier binaries, but old wrappers check a **different** kernel identity.
- Prepared bundle: `artifacts/live/private/j81-dwi-gpc-bundle-20261113/`.
  Its manifest and every component are pinned independently in
  `boot/j81_dwi_gpc.py`. The three adapted wrappers require the hold boot;
  the bridge and GPC wrappers also require the new kernel notes and the
  cycle module's build ID.
- On the existing hold boot, the runner's read-only preflight passed: model,
  kernel notes, hold argument, DWI rejection log, RAM root, watchdog, and
  unused-module/one-shot guards. This preflight did not run GPC or write GPU
  registers. Preflight must be repeated on the actual boot before use.
- Host checks passed: hold-campaign ordering and failures; GPC parser and
  lost-host handling; wrapper acknowledgment and state gate; watchdog
  supervisor. These checks do not prove the hardware accesses succeed.

## Sequence and boundaries

1. Verify the pinned bundle, repeat the read-only preflight and capture a
   boot ID. Stage files only into RAM. Read DWI `0x20e020120`, candidate
   PMGR word `0x20e02300c`, and page-5 `0x20e005004`; stop unless DWI is
   exactly `0xff` and all reads complete.
2. Run the existing one-shot GFX PMGR cycle and keep its runtime reference.
   This makes PMGR power-state writes; it is not watchdog-supervised by the
   existing cycle tool. Stop on any missing acknowledgment or error.
3. Confirm DWI again, replay the previously tested 66 bridge writes under
   the watchdog supervisor, and confirm DWI a third time. Stop at any failure.
4. Under the watchdog supervisor, check GPC initial state zero, write the
   three established GPC setup values, poll for state 1, and sample page-5
   `+4` immediately and about 100 µs later in kernel context (`paired`).
   Persist every checkpoint before host acknowledgment. After a completed,
   disarmed supervisor, read the same three PMGR words once more.

There is **no GPU-core access, page-5 write or PMU access** in this campaign.
The GFX/bridge/GPC operations still write hardware and can hang or reboot the
iPad. The watchdog cannot guarantee recovery. A failed or interrupted run
consumes that boot; do not retry it on the same boot. A missing post-GPC DWI
sample does not invalidate a completed GPC result but limits interpretation.

Run only when explicitly proceeding with the hardware test:

```sh
python3 boot/j81_dwi_gpc.py artifacts/live/private/j81-dwi-gpc-run-UNIQUE
```

A set page-5 bit would be a new cross-boot lead, not proof the GPU core works;
a clear bit would show early DWI retention alone did not produce that sampled
state. A subsequent core read needs its own decision. DWI is sampled at the
boundaries, not continuously, and iPadOS and Linux checkpoints are not fully
matched. For context, the previous late-DWI-on GPC run saw bit 30 clear.
