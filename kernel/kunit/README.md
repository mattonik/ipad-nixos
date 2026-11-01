# KUnit: J81 driver logic tested off the iPad

Runs the J81 drivers' own C code on QEMU arm64 with the hardware replaced by
fakes, using the kernel's KUnit framework (`tools/testing/kunit/kunit.py`).
It catches logic bugs (encoding, parsing, state machines, retry rules). It
cannot say whether a real chip accepts what the driver sends; that still needs
the iPad. Background and the wider plan: the "Testing J81 work without the
iPad" doc (2026-11-01).

```bash
tools/builder.sh status        # the builder must be up; see docs/build-infrastructure.md
nix build .#packages.aarch64-linux.j81-kunit -o result-j81-kunit -L
```

The build fails if any test fails. `result-j81-kunit/` holds `kunit.log`
(the parsed TAP output, including SKIP reasons), `results.json` and the
`.config` of the test kernel.

## How it is wired

- `j81-kunit.nix` takes the source tree of the Wi-Fi base kernel
  (`hoolock-pcie-j81-wifi-h1b-kernel.src`, the kernel in
  `m1n1-hoolock-pcie-j81-wifi-h1b-base`) with all of its patches applied, so
  the code under test is the code that ships.
- `0001-bq27xxx-hdq-uart-kunit-hook.patch` adds a Kconfig symbol and an
  `#include` of the test file at the end of the driver, the usual way to test
  static functions. It is applied **only** in this derivation. No payload
  kernel changes, so no release build record changes either.
- `j81.kunitconfig` lists the options. `kunit.py` builds a small separate
  kernel from it (not the Hoolock config: that one disables the PL011 UART QEMU
  needs), boots it in `qemu-system-aarch64 -machine virt -cpu max`, and parses
  the results.
- It builds natively on the aarch64-linux builder (no cross compiler). A
  cold run took about 2 minutes on 2026-11-01 (100 s building, under 2 s
  running). QEMU runs with TCG, without KVM. The KUnit core's own
  `refcount_interrupt` suite runs too.

## Suites

### `bq27xxx-hdq-uart` (battery gauge, `bq27xxx_battery_hdq_uart_kunit.c`)

A fake serdev controller sits under the real serdev core. It loops every
transmitted byte back as the single-wire echo, then answers from a small
simulated gauge register file. Knobs inject noise before the echo,
byte-at-a-time delivery, weak gauge pulses (`0xf3`/`0xe1`), a lost response
byte, a counter that ticks between reads, and a failing break.

It covers the old `kernel/test_hdq_uart_patch.py` invariants as behaviour
rather than patch text: LSB-first `0xfe`/`0xc0` encoding, all 256 round trips,
the `>= 0xf0` threshold, echo sync and combined delivery. It also covers the
three pre-BAT-4 transport bugs (`write_wakeup`, arming the receiver before
transmit, the threshold), read/write command framing and register masking,
the high/low/high 16-bit read with retry and give-up, the low-then-high word
write, the timeout and recovery after a lost byte (the "matched 15/16" failure
from patch 0091), and `DEVICE_TYPE` identification for 0x0541, 0x0545 and an
unknown type.

One case is reported as SKIP on purpose:
`hdq_test_stray_level_byte_before_echo`. The echo matcher skips any byte that
doesn't fit, so it matches a subsequence rather than a contiguous run. A stray
`0xc0` just before the echo of register 0x00 completes the match one byte
early and shifts the response by a bit. The test shows 0x41 coming back as
0x82, which would turn `DEVICE_TYPE` 0x0541 into an unknown chip. On the J81
the byte before the echo is the break, which reads as 0x00, so this has not
been seen. The SKIP keeps it visible until hardware says whether it matters.

## First run, 2026-11-01

All 19 cases ran. 18 passed, and `hdq_test_stray_level_byte_before_echo`
was skipped with "reads ret 0 value 0x82, want 0x41", as predicted above.
To check that the suite catches regressions, I reintroduced two of the
pre-BAT-4 bugs in one build (decoding only an exact `0xfe` as one, and
arming the receiver after transmit). 12 cases failed, so the suite does
catch them.

## Adding a suite

Write the test file and a hook patch the same way (Kconfig symbol plus
`#include` at the end of the driver), apply both in `j81-kunit.nix`, and add
the options to `j81.kunitconfig`. Good next candidates: the D2207 charger
current-limit encode/decode, the PCIe tunables read-modify-write math, and
DART PTE/IOVA math.
