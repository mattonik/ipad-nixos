# J81 GPU diagnostic: recovery procedure and test gate

2026-11-04. This is a proposed procedure based on the offline trace and the
existing J81 boot records. **It has not been exercised with the GPU.** The
diagnostic payload, its error handling and the watchdog are not yet built or
validated for this test. It is not authorization to boot or access hardware.
See `research/2026-11-04-j81-gpu-offline-trace.md` for the evidence.

## Recovery goal and limits

Return to a known boot environment without writing the iPad's storage, and
preserve enough host-side evidence to identify the last completed operation.
A restart is a recovery attempt, not proof that a particular GFX register,
power domain, or all hardware state was reset. Confirm the subsequent boot;
if it fails, stop and investigate rather than repeating the GPU access.

A bounded poll can stop a loop only when individual MMIO operations return.
A single access may hang the CPU or cause an asynchronous error. The project
has observed J81 DART/PCIe hangs with no console, USB, or watchdog recovery
(`research/t7000-pcie-hardware-findings.md`, `0025`). Do not rely on a shell
trap, module removal, a watchdog, SSH, or an in-guest timeout as the sole
recovery mechanism. Do not assume that loss of USB means the iPad is off.

## Before any proposed hardware run

1. Have a direct cable, charged iPad, working Home and top buttons, and an
   operator able to perform the button restart. Make sure the user can
   recover any important work; a forced restart interrupts the running OS.
2. Identify a known-good, previously booted **RAM-root** control payload and
   its checksum; verify the files and the existing DFU/PongoOS/m1n1 loader
   locally. Do not use `boot/flash.sh` as the recovery recipe. A successful
   verified control boot and a normal return to the intended OS are separate
   hardware checks; do not claim either occurred until actually observed.
   `boot/run_m1n1_debug.sh` validates a private payload manifest before
   starting the DFU -> PongoOS -> m1n1 route; use it only with the explicitly
   selected control and the required private manifest.
3. Build a dedicated, one-shot diagnostic and review its exact hash, DT,
   kernel, initramfs, register operations and error paths. The known-good
   control must remain available and must not include the GPU diagnostic.
   Confirm the boot uses RAM for its root and does not mount or write the
   iPad's internal storage. Do not assume every existing payload has those
   properties without checking its manifest and configuration.
4. Start host-side capture **before** the dangerous operation. The diagnostic
   must send an identifiable, flushed stage marker and timestamp before and
   after each power transition and each MMIO access. Capture the selected
   payload hash and final messages outside the iPad. Host silence or a
   disconnect is an indeterminate failure, not a successful read.
5. Before issuing writes, determine and record power-domain ownership and
   starting state. Do not unconditionally power down a domain that may have
   been active or shared. Reject the run if ownership, the sequence, or the
   behavior when a check fails cannot be explained. A Linux generic power
   domain may act during driver bind/unbind; merely avoiding explicit
   `devmem` writes is not a read-only guarantee.
6. Separately verify any proposed watchdog with a harmless control experiment
   before depending on it. Until then it is unavailable as a recovery layer.
   A host deadline is only a trigger for the operator to intervene; it cannot
   interrupt a stuck bus transaction. Agree on the host deadline before a
   run and distinguish it from the bounded device-side polling timeout.

## Response during the diagnostic

- **Check or transition fails before GPU MMIO:** stop the sequence and save
  the host-side stage and error. Do not advance to the next register.
- **A GPC poll times out or access returns an error:** stop further GPC/RGX
  accesses. Do not issue the next original Apple-probe write, blindly restore
  a saved register value, unbind the module, or power-gate the domain: those
  actions may themselves touch a wedged device or change shared state.
  Preserve logs and use the restart path below. A narrower cleanup can only
  be used after its exact state-dependent safety has been established.
- **An ID read returns:** save raw values and completion markers to the host.
  Do not infer that the hardware state or reset path is healthy merely because
  a value was returned. End the one-shot session through an agreed reboot;
  if that does not complete, use the physical restart path.
- **Host deadline expires, console/USB disappears, kernel reports a fatal
  error, or the device stops responding:** stop sending commands and do not
  retry in the same boot. Save all host output, including the last marker.
  Proceed to the physical restart path; a timed-out host connection cannot
  establish which MMIO operation completed.

## Physical restart and confirmation

For this Home-button iPad, press and hold the **top button and Home button
at the same time until the Apple logo appears**, then release. This is
Apple's documented force-restart procedure:
https://support.apple.com/en-ca/102642. If the iPad remains unresponsive,
stop: the procedure cannot guarantee recovery from every hardware fault.

After restart, confirm the intended stock OS starts and is usable if that is
the intended destination. For another Linux control boot, deliberately enter
DFU and run the verified PongoOS -> m1n1 control route with its approved,
known-good payload. Confirm the expected screen, USB/network shell, and
payload identity. Re-entering DFU is a separate action; do not automatically
launch the experimental payload or repeat the GPU access. No restore or erase
is part of this procedure. Apple states that a Finder restore reinstalls
software and erases data: https://support.apple.com/en-au/108925.

## Remaining blockers

- The exact GPC initialization and safe cleanup for every partial transition
  are not proven. The Apple probe uses unbounded polls; its cleanup depends
  on a consumed PMGR event flag, not solely on a saved current state.
- The GPU diagnostic, host stage capture, ownership strategy, timeouts and
  test-specific kernel error handling have not been implemented or verified.
- A physical restart and known-good control boot have not been demonstrated
  after a GPU hang. The fact that this boot chain has run before does not
  establish recovery from this particular failure.

A future run needs a separately reviewed payload and explicit authorization
for its power/GPC writes and reads. Record failures and update this procedure
from observed results rather than calling it proven in advance.
