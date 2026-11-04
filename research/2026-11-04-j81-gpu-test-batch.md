# J81 GPU test batch: preparation

2026-11-04. This is the start of a staged diagnostic, not a GPU driver or a
hardware result. Do not execute a stage until its capture, ownership and
recovery requirements in `research/2026-11-04-j81-gpu-diagnostic-recovery.md`
have been reviewed. The first-stage binary is built but has not been copied
to or executed on the iPad.

## Orchard comparison

OrchardLinux/gpu `main` was checked at commit
[`42f6add03616d065d137e60c2cd7fde8780e5203`](https://github.com/OrchardLinux/gpu/commit/42f6add03616d065d137e60c2cd7fde8780e5203)
on 2026-11-04. Its [A10 README](https://github.com/OrchardLinux/gpu/blob/42f6add03616d065d137e60c2cd7fde8780e5203/a10/README.md)
reports accelerated desktop rendering on J71b. The driver depends on A10's
GFX coprocessor and RTKit, whereas J81's 8.1 code and firmware use META; it
is not an A8X driver. Its [power notes](https://github.com/OrchardLinux/gpu/blob/42f6add03616d065d137e60c2cd7fde8780e5203/a10/bringup/power-display.md)
identify Fender `+0x1000` as the A10 performance-state request and report a
silent reset caused by a state-0 ordering error. Our own 8.1 G4G trace
independently finds a similar register and bit, but A10's state count,
timing, RTKit setup and fastest-state defaults are not validated for J81.

## Stage 0: control and inventory

The previously completed control boot is documented in the recovery note:
Linux's simple-framebuffer is the only DRM device, and the PMGR power-domain
platform driver binds. The control root is RAM-backed and no internal-storage
mount was observed. This inventory does not read the GFX power register and
cannot say whether the GPU is actually powered.

## Stage 1: one PMGR state observation

`boot/gpu-pmgr-peek.c` opens `/dev/mem` read-only, maps the fixed PMGR page
read-only, prints and flushes a stage marker, waits for the host's `READ`
acknowledgement, reads exactly one 32-bit word at physical `0x20e020320`,
and prints the raw word and target, actual, auto,
and reset fields. The address is the GFX PMGR state register independently
identified from both J81 ADTs and the 8.1 controller code. It never maps or
accesses the GPU core or Fender and does not write a register. A physical
MMIO read can still hang or fault; read-only does not guarantee safe recovery.
The software fields do not prove that the GPU is clocked or safe to access.

Build on the documented Linux builder and run the host-only fake-memory test:

```sh
tools/builder.sh status
tools/builder.sh build --who j81-gpu '.#packages.x86_64-linux.gpu-pmgr-peek-static' -o artifacts/live/gcroot-gpu-pmgr-peek
/opt/homebrew/bin/python3 boot/test_gpu_pmgr_peek.py
/opt/homebrew/bin/python3 boot/test_gpu_pmgr_capture.py
shasum -a 256 artifacts/live/gcroot-gpu-pmgr-peek/bin/gpu-pmgr-peek
```

The 2026-11-04 build is a statically linked AArch64 ELF with SHA-256
`78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd`.
The host test exercises the fixed read-only mapping, argument rejection,
open/mmap failure, acknowledgement rejection, and decoding against a fake
memory page. A socket-pair test checks that the collector persists the marker
before acknowledging and rejects incomplete or stale completion. These do not
test real hardware, `/dev/mem` permission, telnet transport, the selected
kernel or bus behavior.

`boot/gpu_pmgr_capture.py` is a dedicated live collector for this one
stage: after it has written and fsynced the marker to a new private host log,
it sends `READ` and waits for the result. The existing
`boot/ipad_telnet_run.py` buffers output until completion and must not be used
as this collector. The handshake and transport have only been simulated;
the binary must first be staged at `/tmp/gpu-pmgr-peek` on the intended
control boot and checked against the approved hash. No unattended run or
automatic recovery is established. Confirm operator availability and the
device's recovery path before any eventual MMIO read.

## Later stages, not built

A managed, bounded power-and-Fender test and an identity read require separate
implementation and review. They must establish domain ownership, check each
return, preserve raw values, use timeouts, avoid an unproven power-off or
rollback after failure, and handle the possibility that one MMIO access never
returns. A GPU firmware upload or workload is outside this first batch. The
existing G4G LDR findings suggest a related firmware container, not an already
compatible Linux firmware ABI.
