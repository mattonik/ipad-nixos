# J81 GPU: path to the next hardware observation

2026-11-05. This plan records the evidence and the remaining work; it is
not a claim that undocumented MMIO is harmless or that rendering is ready.

## Starting point

The last observed test boot used a RAM root and the verified diagnostic
kernel. GFX was on with the one-shot consumer holding runtime usage 1;
the GPC state read zero. The bridge plan and watchdog supervisor were
staged. The supervised 66-step protocol completed with the actual plan
but with all bridge and GPC accesses redirected to RAM. The real bridge
one-shot guard was still clear. Recheck all of this on the live device:
it is a snapshot, not a guarantee that the same boot is still running.

The earlier first GPU revision read hung after GFX and GPC were brought
up. The user reported a successful iOS boot after force restart. A
watchdog control test and a supervised synthetic-stall test were followed
by the user's report of the iOS lock screen; neither proves recovery from
a CPU or interconnect stuck in GPU MMIO. The device's live GPU die
temperature is not available from the observed battery sensor.

## Sequence

1. **Complete the read-only observer.** Done offline in this commit:
   `boot/gpu_bridge_peek_capture.py` validates all three staged binary hashes,
   persists and fsyncs every checkpoint before acknowledgement, and accepts
   only one GPC state read plus one 32-bit read at `0x201f00018`. Its host test
   covers normal completion, malformed ordering/results, persistence, and hash
   rejection without MMIO. The device wrapper still gates the test-kernel
   identity, RAM root, power ownership, and one-shot state. The remaining
   validation is the real device's live preflight; no hardware read has been
   run by this change.
2. **Verify the current device and operator recovery.** Recheck payload,
   kernel and module identities, RAM root, absence of internal-storage
   mounts, GFX runtime ownership, exact PMGR word, one-shot guards, host
   log location and all staged binary hashes. Confirm the iPad and physical
   restart controls are accessible. If the boot has changed or a guard is
   consumed, stop and use a fresh verified test boot rather than bypassing
   a gate. Do not assume a watchdog resets a wedged bus.
   Once this preflight is captured, use `boot/gpu_bridge_peek_capture.py` with
   the exact probe, supervisor, and `/tmp/gpu-bridge-peek-run` SHA-256 values
   from that boot. It refuses malformed hashes and never retries an incomplete
   session.
3. **First new hardware observation, only when the read is judged within
   the user's damage-risk limit.** Run the supervised single bridge read.
   A matching Apple table and an analogous A9 access do not prove A8X read
   semantics; a read can hang or have side effects. A timeout, unexpected
   stage or lost connection is indeterminate: record the last checkpoint,
   stop, and recover physically as needed. A returned value is an
   observation, not proof that subsequent writes are safe.
4. **Prepare the smallest write experiment.** Prepared offline in this
   commit: `gpu-bridge-first` writes only `0x80010004` to `0x201f00018`
   after the same PMGR, kernel, RAM-root, and GPC-state gates, and runs under
   the progress-gated watchdog as `--bridge-first`. It does not read back or
   retry the write. The static test confirms it is one-shot and storage-free.
   Do not stage or run it on hardware until a fresh boot and an explicit risk
   decision are recorded.
5. **Decide the write experiment from evidence.** Analyze the returned
   value and its read side effects against both J81 Apple device trees and
   the Apple PMGR code. Independently review the first high-bit bridge
   control write, ordering, shared-fabric implications, failure behavior,
   and display-idle coordination. The two captured MCC configuration records
   selected in a display-active policy case are identical, but that does
   not eliminate other display effects. If the risk cannot be bounded under
   the user's condition, stop rather than assume the result authorizes a
   replay. If supported, run one supervised, one-shot table replay using
   the exact private plan; never automatically retry a partial sequence.
5. **Only after a completed, reviewed bridge experiment**, reassess GPC
   initialization and a single GPU revision read. Capture and verify each
   state and hardware checkpoint. A timed-out MMIO transaction cannot be
   interrupted by the host and must not be repeated in the same boot.
   Successful bridge stores are software markers, not register readback.
6. **After an ID is obtained**, compare the observed fields with the
   target's iOS G4G loader and firmware metadata. Build a minimal firmware
   load and job path separately; preserve proprietary firmware and captured
   bytes under ignored `artifacts/`. Firmware execution and rendering are
   distinct, later hardware experiments and are not implied by an ID read.

## Validation and records

Run `python3 tools/check_offline.py`, the bridge/tuner audits against the
private inputs, and the relevant static ARM64 builds before device use.
Keep raw captures in `artifacts/live/private/gpu-observations/`; record
only conclusions, hashes and limitations in Git. See the
[offline trace](2026-11-04-j81-gpu-offline-trace.md),
[test batch](2026-11-04-j81-gpu-test-batch.md), and
[recovery procedure](2026-11-04-j81-gpu-diagnostic-recovery.md).
