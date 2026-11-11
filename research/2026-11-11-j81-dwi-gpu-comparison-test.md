# J81 DWI-first GPU voltage comparison: prepared test

This fresh cycle-payload Linux test measures selected PMGR words and four
previously sampled PMU buck rows around the GPC state-1 request. Its purpose
is to test the DWI voltage-transport lead while retaining the earlier
DWI-only test as a control. The PMU row-to-rail mapping and page-5 bit meaning
remain hypotheses. A row following a code is not a measured physical voltage.

## Sequence

1. Verify pinned local bundle hashes and fresh-boot preflight. Stage the
   already-built AArch64 tools, verifying remote hashes and the boot ID.
2. Capture ten fixed PMGR words and PMU rows `0x0100`, `0x0128`, `0x0150`,
   `0x01c8` before DWI. Each PMU operation uses the previously used two-byte
   register-address selection and an eight-byte read; `-f` bypasses the I2C
   kernel ownership check. This can have side effects and interfere with a
   bound driver, despite using no PMU value-write command.
3. Use `pmgr-dwi-on`, with host `READ` and `WRITE` acknowledgments only after
   the corresponding checkpoint is logged and flushed. Capture the same words
   and rows again. The DWI raw write bypasses genpd accounting and is not the
   Linux driver's full power-on sequence.
4. Run the existing supervised PMGR cycle and bridge campaign, require the
   original boot ID, and check DWI active once more after bridge setup, just
   before the GPC step. The existing one-shot kernel probe requests GPC state
   1 and reads page-5 `+4` immediately and about 100 µs later (`paired` mode).
   It does not read the GPU core or write page 5.
5. Repeat the PMGR and PMU snapshots after the campaign and after ten seconds.
   Boot ID and the three staged tool hashes are checked before every command.
   A failed check, incomplete data, changed boot, or failed stage stops the
   campaign; no repeat on that boot. The DWI checks bracket the GPC request;
   they do not continuously monitor it.

Run after a fresh `gpu-pmgr-cycle` Linux RAM boot from this worktree:

```sh
cd /tmp/j81-dwi-gpu-compare
python3 boot/j81_dwi_gpu_compare.py artifacts/live/gpu/dwi-gpu-compare-NEW
```

Replace `NEW` with a unique label; the directory must not already exist. This
worktree's ignored `artifacts` symlink points to the main checkout's local
artifacts. The prepared binaries are local, not in Git. Never publish the
full logs. The test does not restore DWI at the end; the Linux RAM boot can be
restarted, but hard-reset recovery from every possible hardware failure is not
established.

Host checks pass for bundle hashes, fixed PMGR parsing, checkpoint/ack order,
DWI failure and boot-ID stop cases, original preflight and kpoll supervision,
wrapper guards and the kernel probe. Tools and module are AArch64. These are
mocked or offline checks, not a device run of this combined campaign. PMU and
DWI stages are not watchdog-supervised; MMIO and I2C accesses can stall or
have side effects, and the watchdog itself is not a guarantee of recovery.
The GPC watchdog may reset the iPad, and a stalled transaction can lose data.

A successful or unchanged PMU sample does not independently identify a rail,
prove a voltage was applied, or establish why the core access hangs. Compare
all phases and treat a dropped DWI state, missing sample or GPC failure as
inconclusive.
