# J81 iOS page-5 power-provider boundary probe

Built for the exact iPadOS 15.8.5 19H394 kernel. Extends the successful
[three-point probe](../j81-page5min/README.md) by wrapping the original power
provider call and taking one additional read of PMGR region 0 offset `0x5004`
after that call returns and before GPC setup. The four observations are:

- `Q=` after `PAGE5-early-before`: after the clock provider return.
- `T=`: buffered immediately after the power provider return.
- `M=`: buffered after the successful GPC poll.
- `Q=` after `PAGE5-before`: after the original GPU identity reads.

`T=` and `M=` are printed at the later identity hook, so their log timestamps
are not their sampling times. A missing value is inconclusive; a stalled read
can prevent later log output. The probe takes four undocumented reads per
boot. Reads can have side effects or hang or reboot the device; the extra
instrumentation changes timing. Their interpretation also assumes the PMGR
region maps as indicated by the Pongo ADT.

The new power wrapper calls the original target, preserves its returned state,
checks captured thread and PMGR context, checks IRQ state, and accepts only the
known KASLR-adjusted PMGR read-method address. Its one-shot result is buffered.
It uses a 320-byte save frame in addition to the 16-byte wrapper frame, without
SIMD instructions in this new wrapper. The earlier clock/identity hooks still
use SIMD. No hardware run has validated object lifetime, mapping, stack
headroom, lock context or MMIO side effects.

Private module `artifacts/live/private/j81-ios-page5power-probe/page5-power4`,
SHA-256 `7ebf0af4c97fe0a27688b0679661b28c7ef1c6de29fae6e1b6322d522c033351`.
Build uses the Pongo checkout of the paired probe, registers
`j81_page5power_capture`, and sets `KPF_CFLAGS=-DJ81_PAGE5POWER_DEVICE_BUILD`.

The KPF harness positively applied the component to the matching kernel. Each
of ten missing or duplicated signatures and a wrong UUID was rejected. Native
ARM64 host simulations checked sample order and arguments, original power-call
return, repeated-call one-shot behavior, wrong thread and method skips, GPC
busy behavior, and masked-IRQ skip. These simulations do not validate the
real kernel context or guarantee hardware safety. No hardware run was made.

The hardware run completed: early `0`, post-power `T=0`, post-GPC
`M=0x40000000`, and late `0x40000000`; GPU firmware boot was reported.
See the [capture result](../../2026-11-10-j81-page5-capture-results.md#power-provider-boundary-change-observed-during-gpc-interval).
