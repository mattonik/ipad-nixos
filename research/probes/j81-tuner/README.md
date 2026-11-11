# J81 iOS SoC-tuner policy probe

Experimental temporary 19H394 iPadOS boot probe. It extends the previously
hardware-tested [PMGR/GPC poll comparison](../j81-pollcompare/README.md),
without adding MMIO reads or writes. It hooks the entry and the single static
return instruction of the candidate `AppleT7000SOCTuner` policy routine
`0xfffffff006cd827c`. It records whether each was reached after the GFX
clock-provider hook starts and before the GPU identity logging boundary.
At identity it logs the existing `P`, `G`, and `I` values and:

```
U=<window-flags>:<reservation-failed>:<entry-seen>:<exit-seen>
```

Each field is eight hexadecimal digits. `window-flags` bits are:

| Bit | Meaning |
| --- | --- |
| 0 / 1 | policy entry observed on provider thread / another thread |
| 2 / 3 | policy return observed on provider thread / another thread |
| 4 / 6 | entry / return with a missing thread-context value |

`reservation-failed=1` means a bounded 16-attempt atomic update did not
complete. `entry-seen=1` and `exit-seen=4` are global positive controls:
that hook ran at least once since patch installation, possibly before the
window, including on unrelated threads. Zero means not observed. The policy
window starts just before the provider call and closes in the identity hook,
which runs after the original identity loads return. It is **not** an exact
pre-first-load timestamp. Phase and thread snapshots can race with another
CPU; an event can be delayed before publication, including past the output
snapshot. Multiple entries and returns are not paired, so matching flags do
not prove that one particular call returned or caused a GPU effect. A same
thread observation does not exclude an interrupt. No flag alone proves GFX
causation, a successful MCC operation, or completion of queued work.

No entries, a missing identity log, an unseen positive control, reservation
failure, a crash, or loss of logs are inconclusive. The trace records the
policy routine, not every possible tuner entry or all provider-to-tuner call
edges. It uses the existing kernel log format and avoids raw pointers. The
full log archive may contain personal information and stays private.

## Build and host checks

The sources use the same PongoOS checkout/newlib build as the poll comparison,
component `j81_tuner_capture`, flag `KPF_CFLAGS=-DJ81_TUNER_DEVICE_BUILD`.
The host KPF harness on the exact 19H394 kernel prepared and applied the
11-site patch (722 shellcode words), rejected each individually missing or
duplicated signature, and rejected a modified UUID. The full policy function
contains one `ret` in the inspected static 364-byte range. Branch-range checks,
all-or-nothing site checks, register/NZCV restoration, and a bounded exclusive
update are present. `python3 research/probes/j81-tuner/test_tuner.py` compares
the host and device hook bodies and tests closed-window behavior, same/other/
unknown thread flags and logging. These tests mock kernel context; no hardware
run, independent review, real concurrency/timing, stack-headroom or fault-path
validation has been performed.

Private module: `artifacts/live/private/j81-ios-tuner-probe/tuner4`; SHA-256
`58188332889230879ebe922c222031cc09c1479def4b6dc14700eebc1907f694`.
This hooks a global kernel routine and changes scheduling/timing. It may hang
or reboot the iPad; logs may be lost and recovery may need DFU. Do not run on
another kernel build or without checking the module hash. Follow the
[existing capture procedure](../j81-page5writer/MORNING.md) with this module
and a fresh private log directory.
