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

## Control boot result: 2026-11-04

With the user's go-ahead, the J81 was detected in DFU, entered PongoOS,
and booted the existing `artifacts/live/gcroot-clean-production` control
payload. The uploaded `m1n1-linux.bin` SHA-256 was
`b3206c51c096d9e0cb47473cdcd88157acf677388805eb3532df071ce7315781`,
matching its stored manifest. PongoOS disconnected during `bootm`; this was
followed by a visible Linux console, a successful ping and a working telnet
shell at `172.16.42.1`. The shell reported Linux `7.3.0-rc1` and `rootfs` as
the root mount. The observed mount list contained no internal-storage mount.

This verifies the control boot and shell on that run. It does **not** verify
physical force restart, booting the stock OS afterward, GPU diagnostic
recovery, watchdog behavior, or the GPU power sequence. No GPU register
access was made. The experimental diagnostic payload is still to be built and
reviewed.

## Control-system inspection: 2026-11-04

On the still-running control boot, ping and the telnet shell responded; the
kernel reported `7.3.0-rc1` and approximately 57 minutes uptime. The root
mount was `rootfs`, and the observed mount list contained no internal storage.
`/dev/dri` exposed only `card0`; its driver symlink identified
`simple-framebuffer` and `fb0` reported `simpledrmdrmfb`. There was no GPU
render node in that listing.

The platform device at PMGR `power-controller@20320` was bound to
`apple-pmgr-pwrstate`. Its device runtime-PM sysfs values were `auto`,
`unsupported`, and `disabled` for `control`, `runtime_status`, and
`runtime_enabled` respectively. These are the **controller device's Linux
runtime-PM bookkeeping**, not a read of the GFX domain's actual hardware
power state. The boot command line contains `pd_ignore_unused` and
`clk_ignore_unused`. No GPU, GPC, or PMGR register was read or written during
this inspection, and no firmware or workload was submitted.


## Recovery following the first GPU revision-read timeout: 2026-11-05

After the guarded `0x201000020` read failed to return before the host
deadline, the user reported that the iPad restarted and was placed in
DFU. The Mac observed Apple USB product `0x1227` (DFU). After the user
started the PongoOS handoff, the Mac observed `0x4141` and uploaded the
previously booted control payload, whose `m1n1-linux.bin` matched
`b3206c51c096d9e0cb47473cdcd88157acf677388805eb3532df071ce7315781`.
The bootm handoff disconnected PongoOS, then USB networking returned.
The shell reported Linux `7.3.0-rc1`, `rootfs` as root, and kernel-notes
SHA-256 `7933908f2a1ede1ab65c3c2ae35a00de2a14bc63b7bfed30d8aaad3232a1768f`;
the test-only `gpu_pmgr_once` module was absent.

This confirms that this device reached DFU and the known-good Linux
control boot after the timed-out read. The user reported a restart;
we did not independently observe the Apple logo or a usable stock iOS
boot. The control boot is not evidence that the original register read
safely completed or that recovery is guaranteed in future. No repeat
GPU, GPC, or bridge experiment was performed during recovery.


The user subsequently clarified that they successfully rebooted into
iOS after the timed-out GPU read, before entering DFU. Together with the
subsequent verified Linux control boot, this establishes both recoveries
for this one incident; it does not establish repeatability or guarantee
recovery from a future fault.


## Control-boot watchdog inventory: 2026-11-05

Read-only inspection of the running control image found an
`apple-watchdog` platform driver bound to `20e027000.watchdog` and
`/dev/watchdog` and `/dev/watchdog0` device nodes. The sysfs class
entry exposes only its device number and generic power/uevent files on
this build; it exposes no state or timeout fields. These facts do not
show the watchdog is armed, that it runs during a fabric stall, or
that it can recover the RGX-read hang. The watchdog device was not
opened or configured, and no restart was attempted. A watchdog must
not be counted as a recovery mechanism without a separately designed
and observed experiment.


The pinned Hoolock kernel's `drivers/watchdog/apple_wdt.c` uses watchdog
1 for its normal machine reset and exposes start, stop, ping and timeout
operations. Its probe reads the enable bit and sets the default timeout,
but the running image's limited sysfs interface does not reveal whether
it is currently armed. The driver's intended reset behavior is not a
measurement that the counter or reset path will function during the
observed GPU/fabric stall. No watchdog handle was opened or armed.


## Watchdog disarm and expiry experiment: 2026-11-05

On the known-good control kernel (`/sys/kernel/notes` SHA-256
`7933908f2a1ede1ab65c3c2ae35a00de2a14bc63b7bfed30d8aaad3232a1768f`),
root was RAM-backed, no `/dev/` filesystem was mounted, and the battery
reported 79% and charging. The known-good control payload matched SHA-256
`b3206c51c096d9e0cb47473cdcd88157acf677388805eb3532df071ce7315781`.
The static `watchdog-control-test` binary matched SHA-256
`73bc6d32151d8c26f6a107a732a459f8f084f9f9447b1d4e99918a91ecee0823`.
Its host-side simulated tests passed.

The host persisted and acknowledged each pre-open marker. The check
mode obtained watchdog support and a 20-second timeout, wrote the magic
close character, and reported a successful close. More than 23 seconds
later the same Linux boot, identified by uptime and kernel notes,
remained responsive. This supports disarm on this run, not a guarantee
for future runs. The capture is private at
`artifacts/live/private/gpu-observations/2026-11-05-watchdog-check-01.log`.

The expiry mode then armed a 20-second timeout and intentionally stopped
feeding it. The host captured the armed marker but received no more data
for 35 seconds; a subsequent connection to the Linux shell failed. No
new iPad USB identity was visible at the initial check. This is
**indeterminate**, not confirmation that the watchdog reset succeeded,
that iOS booted, or that the watchdog could recover a GPU bus hang. The
user was asked for the physical display state. Do not repeat the test
until device state is established. Private capture:
`artifacts/live/private/gpu-observations/2026-11-05-watchdog-expire-01.log`.


The user subsequently reported that the iPad was showing the **iOS
lock screen** after the expiry experiment. Together with the captured
armed marker and loss of the Linux connection, this is consistent with
the watchdog-triggered restart reaching iOS. The host did not capture
the reset instant or independently identify the iOS USB device, so
this does not by itself establish the precise cause or timing. The
check was on a responsive system; it does not prove a watchdog will
recover a stalled GPU transaction or that a future reset is guaranteed.


The expiry-test program deliberately does not feed the watchdog and is
not suitable to wrap the multi-stage GPU diagnostic. A GPU-specific
supervisor would need bounded, independently verified progress and a
feeding policy that stops on stalled progress; otherwise it could
reset during an ordinary long operation or continue feeding despite a
wedged GPU access. Neither such a supervisor nor recovery from a GPU
bus stall has been verified.


## Progress-gated watchdog supervisor prepared

`boot/gpu-watchdog-supervisor.c` supervises either an explicitly selected
bridge wrapper or a synthetic control child. It arms the watchdog only
after a host checkpoint, proxies the existing read/write acknowledgements,
and refreshes the watchdog only when the host acknowledges a completed
stage. The bridge host collector persists and validates each expected
stage before sending the numbered refresh acknowledgement. A missing
completion or acknowledgement leaves the watchdog unrefreshed. The
supervisor disables the watchdog only after a successful child exit,
success marker and at least one acknowledged completion.

The static ARM64 build's SHA-256 is
`ebf05195bc4682cee63515f8a63b61e5096ad1ea1a9a7e464246770572c6c44a`.
Host tests with a fake watchdog exercise completion, an unresponsive child
and a wrong acknowledgement. The collector's synthetic tests cover
ordered persistent acknowledgements, including the 68-completion bridge
protocol. Device control modes simulate child progress and a child stall
without accessing GPU, GPC, bridge or PMGR registers. The stall mode is
intended to let the watchdog expire and may restart the device. It has
not yet been run on hardware.

A software after-write marker is not a hardware readback. A watchdog
that recovers a deliberately stalled software child on a responsive
system may not recover a CPU or fabric stalled in GPU MMIO. The supervisor
does not establish that bridge replay or any GPU transition is safe.


### Supervisor control tests on the iPad

The user put the device in DFU, and the previously verified control
payload was loaded through PongoOS. Linux reported the expected control
kernel-notes SHA-256 and RAM root, with no `/dev/` filesystem mounted.
The staged supervisor matched its build hash and refused invalid
arguments before opening the watchdog.

The synthetic-success mode completed its host-persisted stage handshake,
received one `FEED 1`, disabled the watchdog and exited. More than
23 seconds later the same Linux boot was still responsive, supporting
that the watchdog was disarmed. Private host capture:
`artifacts/live/private/gpu-observations/2026-11-05-supervisor-ok-01.log`.

The synthetic-stall mode then acknowledged one completed simulated stage
and intentionally stopped producing progress. The host persisted all
expected markers and then lost the connection after the watchdog interval.
The result is **reset unconfirmed** until a new boot or display state is
observed; the user has been asked what the screen shows. Private capture:
`artifacts/live/private/gpu-observations/2026-11-05-supervisor-stall-01.log`.
Neither test issued a PMGR, GPC, bridge or GPU-core MMIO access. A
software-child stall does not replicate a blocked GPU bus transaction.


The user subsequently reported the iPad was at the iOS lock screen
after the supervised simulated-stall test. Together with the captured
armed watchdog, acknowledged synthetic completion and loss of Linux
connectivity, this is consistent with the watchdog restarting the
control system. The host did not independently observe the reset edge
or identify the iOS USB device. This was a userspace stall, not a GPU
MMIO bus hang, and does not establish recovery from one.
