# J81 early power-state audit and controlled comparison

Host-only source review, 2026-11-13. No hardware test or boot-policy change.
The checked Linux source is Hoolock `6831bc701a6ce059e71e5aaa9488c9195bea6927`:
`drivers/pmdomain/apple/pmgr-pwrstate.c` SHA-256 `4b0adc3013e2fabe9ca1cb8228f8f6b7934af4b667f7f0f893b675102d8710df`,
`drivers/pmdomain/core.c` SHA-256 `32e2f6b0988eba52a2f662fdc2d7132022fbe980f281b2a82babcf3d7f46e18a`.
Those match the repository's pinned source audit. The GPU cycle kernel also
has `kernel/patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch`; this
review incorporates its PMGR changes, but does not prove a missing payload's
exact bytes or every patch in its kernel.

## Boot and provider path

- The documented path is DFU → Pongo → uploaded m1n1/Linux concatenation →
  Linux DTB, kernel and RAM initramfs. `boot/run_m1n1_debug.sh` and
  `boot/load_m1n1.py` describe the transport; the payload builder concatenates
  m1n1, bootargs, DTB, kernel and initramfs. This is a cold tethered boot,
  not a transfer out of a running iPadOS kernel. What Pongo/m1n1 or other
  boot consumers change before Linux PMGR probe remains unaudited.
- The still-present once-test payload manifest passes for Pongo, m1n1 and
  combined image; its bootargs include `pd_ignore_unused clk_ignore_unused`.
  The cycle payload and cycle module symlinks currently resolve to missing
  store paths. They must be rebuilt or recovered and independently verified;
  the once payload is **not** a drop-in replacement for the cycle test.
- In the pinned PMGR probe, a node with `apple,min-state` causes a register
  update before the initial `is_active` read. An inactive `apple,always-on`
  node is actively powered on; for any active node the probe sets AUTO_ENABLE.
  Both are potential changes before userspace and before a later hold. The
  exact live DT properties and runtime ordering need capture; do not assume
  DWI had or lacked a property merely from source.
- `pd_ignore_unused` prevents the `genpd_power_off_unused()` late-init pass.
  It does **not** guard `of_genpd_sync_state()` or the simple-provider
  `genpd_provider_sync_state()` path: each clears `stay_on` and calls
  `genpd_power_off()` directly. The latter still checks active consumers,
  subdomains and always-on flags before it reaches the PMGR power-off callback.
  The provider registration selects the relevant synchronization arrangement.
  This establishes a mechanism compatible with the observed DWI shutdown,
  not that a particular DWI invocation caused that observed transition.
- The fail-stop test patch makes PMGR stores and polling errors return early;
  its no-poweroff guard is restricted to J81 `gfx` at offset `0x20320` and
  is not a DWI hold. Other drivers, PMGR reset calls, automatic gating and
  firmware can change state independently of this one callback.

## Proposed two-boot control

Build **two separate, hash-identified RAM payloads from the same pinned source,
configuration and DTB**, differing only in a narrowly scoped, test-only PMGR
instrumentation/hold toggle. Include the prior fail-stop patch and equivalent
non-GPU workload; capture source/patch IDs, kernel, DTB, initramfs and full
combined image digests. Do not use the dangling payload. Preflight a reliable
host capture and the prior recovery process first.

1. **Observe-only control:** at DWI PMGR provider entry log one register
   read before `apple,min-state` or AUTO_ENABLE updates, then after those
   updates. Log the DWI power-off callback's entry and result, with a bounded
   read before/after. Use `0x20e020120` only after confirming the actual DT
   resource-to-physical mapping; log kernel offset/name and boot ID. Limit
   instrumentation to the exact J81 compatible, DWI label and offset. Capture
   kernel logs from the earliest available channel and later genpd debugfs.
   Existing safe read precedent reduces uncertainty but does not prove a new
   early access or logging context harmless. A missing log is inconclusive.
2. **Hold variant:** the same observations and guards, plus reject the DWI
   genpd power-off callback for that boot. Do not force power on, alter its
   auto-PM bit, or change other domains in the hold code. Abort comparison if
   entry shows DWI off, a probe write differs, markers are absent, or the
   callback/return contradicts the assumed path. A rejected callback may change
   genpd behavior and will not prevent hardware auto-gating or another writer;
   check observed target/actual and AUTO_ENABLE, not just genpd accounting.
3. At matching post-boot times compare DWI state, genpd accounting, PMGR
   `0x2300c` and already-vetted page-5 snapshots. Preserve full raw logs and
   exact boot identities. This first comparison makes **no GPC request, PMU
   access, GPU-core read or manual power-domain write**. A later matched GPC
   comparison requires its own reviewed run; the prior late-DWI-on result is
   not identical to uninterrupted early retention.

Interpretation: an observed callback and transition in control, absent
transition with successful hold, supports the Linux gating mechanism for this
boot. A page-5 difference alone would not establish GPU readiness, a physical
rail voltage, or causal responsibility. Equal results leave other prerequisites
open. A hold cannot recreate state lost before provider entry and a watchdog
cannot guarantee recovery from every stall. No implementation or build has
been made yet.
