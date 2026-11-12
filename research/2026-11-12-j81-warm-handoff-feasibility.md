# J81 iPadOS-to-Linux warm handoff: feasibility and staged experiment

Offline preparation on 2026-11-12; the connected iPad was only queried for
its iPadOS build. **No iOS-to-Linux handoff has been implemented or tested.**
The objective is to determine whether a Linux GPU identity read can return
when state established by working iPadOS is carried across a kernel change.
That outcome would make initialization a stronger lead; it would not by
itself identify which prerequisite matters or prove a usable driver.

## What exists

* The device reports iPadOS build `19H394`. Our temporary Pongo/KPF hooks
  have executed after G4G identity and logged successful GPU firmware
  startup; they are instrumentation, not a mechanism to leave XNU.
* The known Pongo `bootm` path allocates and uploads m1n1 **before** XNU,
  sets a boot flag, cleans up Pongo and branches to the m1n1 entry with
  Apple boot arguments. It is not callable as an existing Pongo service once
  iPadOS is running. In the pinned Pongo source, `src/shell/main.c` uses
  `alloc_static()` and `src/kernel/entry.c` jumps to `gM1N1Base + 0x800`.
* `alloc_static()` advances `gTopOfKernelData`; its source says its memory is
  included in the XNU static region and persists after boot. Existing small
  KPF probe buffers have been consumed after XNU starts. This supports a
  **staging candidate**, not proof a 17 MiB payload, its Apple boot arguments
  and associated device tree can be reserved and safely reused later.
* The prior once-test payload still exists at
  `artifacts/live/gcroot-gpu-pmgr-once-payload`; its Pongo, m1n1 and combined
  m1n1/Linux image passed its own SHA-256 manifest on the host. The combined
  image is approximately 17 MiB; the individual `Image.gz`, initramfs and
  DTB are also present. This is a cold-boot reference, **not** a warm-handoff
  payload. The prior cycle-payload symlink and its kernel-module symlink are
  currently dangling, so do not use their old boot commands without rebuilding
  and independently verifying the intended payload.

## Prior art and key blocker

The public [ios-kexec-utils](https://github.com/axi0mX/ios-kexec-utils)
implements an XNU-to-bootloader transfer for older systems; its README limits
arm64 support to iOS 7–8.4.1 and requires a patched kernel task port and a
patched bootloader. Its source stages an image, patches a wake trampoline,
and invokes system sleep/wake. That is **not a demonstrated 19H394 solution**,
and sleep may power down or reinitialize the GPU. It cannot be assumed to
preserve the state this experiment needs. Its hard-coded addresses and write
primitive are not suitable for reuse on the current device without a new
analysis. A8X has no EL2, so an m1n1 hypervisor running iPadOS as a guest is
not an alternative; see [the prior feasibility check](2026-11-07-a8x-m1n1-hypervisor-feasibility.md).

Linux's [AArch64 boot protocol](https://docs.kernel.org/arch/arm64/booting.html)
requires, among other things, a valid DTB address, masked interrupts, the
MMU off and appropriate cache maintenance at entry. A live XNU kernel has
other CPUs, interrupt controllers, DMA, storage and GPU firmware in flight.
The existing early hook demonstrates none of the required shutdown, memory
ownership or entry conditions. A jump without those conditions can corrupt
the iPadOS filesystem or other data; a hard reset is **not** proof that data
or GPU state will survive.

## Staged preparation and decision gates

1. **Host-only payload audit.** Verify the exact kernel, DTB, initramfs and
   m1n1 entry format and sizes, the machine's memory range, and all input
   hashes. Rebuild a dedicated cycle-capable RAM payload if needed; preserve
   the current working iPadOS boot. Identify whether m1n1 initialization or
   the Linux early boot will reset PMGR/GPC or shut down unused power domains.
   Without that audit, a Linux-side zero cannot distinguish a failed handoff
   from a successful handoff that subsequently changed GPU state.
2. **Non-transferring staging control.** Adapt the existing 19H394 KPF
   framework to stage a small tagged buffer through the proposed Pongo-to-XNU
   allocation path, then verify its contents and physical/virtual bounds in
   XNU after GPU identity and again at a later stable point. First validate
   memory allocation, ownership, uniqueness, exact target and failure paths
   on the host. Only then scale to a full payload, with strict size/bounds
   checks and a digest. This stage must return normally to iPadOS; it proves
   retention only, not that executing or jumping is safe.
3. **Transition feasibility.** Resolve a way to stage an executable handoff
   trampoline and boot data, stop other CPUs and nonessential DMA, deal with
   dirty filesystem state, enter the Linux ABI and leave the GPU in a known
   active state. Establish how success or failure is observable if USB or the
   display stops. A loss of GPU state during sleep or ordinary shutdown makes
   that particular transfer unsuitable for the intended experiment.
4. **Two-run controlled experiment, only after the above works.** First test
   the exact transition without a GPU core read and capture an early Linux
   checkpoint. On a separate equivalent boot, compare page-5/GPC state and
   perform at most one watchdog-supervised GPU identity read after a matched
   iOS pre-transfer observation. A returned nonzero identity is meaningful;
   a stall, lost marker or a changed page-5 bit is not enough to attribute
   failure to the GPU. A working marker alone is not proof state survived.

No GPU-core read, page-5 write, sleep, reboot or persistent storage change
was performed for this preparation. The actual warm transition is not ready
to run; there is no verified XNU 19H394 transfer primitive or GPU-state
retention path yet. The next buildable deliverable is the bounded,
non-transferring staging control, not a speculative jump.
