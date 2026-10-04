# Tooling audit and host-only checks, 2026-10-04

The laptop remains the build/RE workstation. The user confirms Nix and the
original offline runner are available there; their absence in the hosted
research workspace is not a defect in that setup. This audit inspects the
repository, not the laptop installation. No iPad was connected.

## Available workflows and gaps

| Area | Existing repository tooling | Assessment / next improvement |
| --- | --- | --- |
| Reproducible build | Pinned flake inputs, separate control/diagnostic targets, Linux and Darwin shells | Keep working builds on the laptop; record exact output hash and git commit per session |
| Reverse engineering | Linux shell declares Ghidra, radare2, binutils, dtc; dated disassembly findings | Tools are already used in research. More reproducible headless analysis scripts and exported source references would help more than another GUI tool |
| Device transport | Pongo/m1n1 uploaders, ADT capture, interactive USB-network console, bounded Bluetooth probe | Useful and exercised. Console completion reporting needed a fix, described below |
| Host tests | Separate standalone scripts, stubbed USB tests, patch invariant checks, native source harnesses | Existing coverage is useful but varies: textual invariants are not substitutes for builds or hardware tests. A repository entry point now makes the reviewed checks repeatable |
| Built-payload checks | Image layout check and original/control USB archive comparison | Preserve these; report unavailable inputs explicitly instead of implying everything was validated |
| Automation | No tracked `.github` workflow or flake `checks` output found | Optional future step: connect the host suite to CI and the laptop runner, with source/build-dependent jobs separated and inputs pinned |
| Evidence handling | Ignored `artifacts/adt`, `artifacts/i2c`, `artifacts/live`; firmware inspector uses private extraction | Next improvement: session manifests with payload/component hashes, tool versions and timestamps alongside private captures |

The hosted environment has Python, GCC and GNU patch. It lacks Nix, dtc,
Ghidra/radare2, AArch64 GCC, PyUSB, Capstone and LIEF at inspection time.
The USB tests work without PyUSB because they stub the device interface.
The native OTP tests use an exact-hash public source copy plus host GCC.
No installation or replacement of the laptop toolchain is required here.

## Repository test command

From any directory, invoke the script by its path:

```sh
python3 tools/check_offline.py
```

It runs 13 explicitly reviewed host-only test scripts in separate Python
processes with repository-root working directories. It removes
`PYTHONOPTIMIZE` from the child environment so assert-based existing checks
remain active. Failures and per-test timeouts produce a nonzero exit code.
It never downloads sources, builds through Nix, uploads a payload or connects
to a device. This can be called from the user's existing laptop runner.

To include the exact-pin native OTP checks:

```sh
python3 tools/check_offline.py --source /path/to/pinned/pcie.c
ASAN_OPTIONS=detect_leaks=0 python3 tools/check_offline.py \
    --source /path/to/pinned/pcie.c --sanitize
```

The native scripts check the source hash themselves. An explicitly supplied
source with a wrong hash, absent compiler or failed patch application is a
failure, not a skip. Sanitizers are optional and their availability depends
on the host compiler/runtime. LeakSanitizer was disabled in this hosted
environment; choose the appropriate setting on the laptop.

The Image layout check runs when `result-kernel/Image` exists. To include the
USB overlay comparison, supply **both** built payload directories:

```sh
python3 tools/check_offline.py \
    --usb-control /path/to/control --usb-diagnostic /path/to/usb-diagnostic
```

Unavailable optional checks are printed as `SKIP` with their requirements.
`--require-all` makes any skip an error; use it for a fully provisioned
validation session. `--verbose` prints successful test diagnostics too.
Default host-only validation initially passed 13 scripts, with four explicit
optional skips. The subsequent touchscreen harness adds a fifth optional
check: supply `--z2-source /path/to/pinned/apple_z2.c` to include it. With both
source arguments, validation passes 16 scripts with two built-artifact skips.
The subsequent [legacy Z2 comparison](../research/j81-z2-legacy-ack-calibration.md)
adds `--openiboot-source /path/to/openiBoot/plat-s5l8900/multitouch-z2.c`.
With all three source arguments, 17 scripts pass under ASan/UBSan with two
built-artifact skips. With no source arguments, 13 scripts pass and six
optional checks are skipped. This comparison validates reference behavior,
not a J81-compatible packet format.
These counts are scripts, not individual unittest cases or fuzz inputs.
The script runner's own checks exercise child exit failure, timeout handling
and preservation of assertions.

## Console completion fix

`IPadShell.run()` previously returned whatever it received when its deadline
expired or the peer disconnected, even if the unique completion marker had
never arrived. Actions could interpret partial output as a completed command.

It now requires the marker, uses a monotonic deadline and raises
`ShellCommandIncomplete` on deadline/EOF before completion. The exception
retains `partial_output` for callers, closes the affected connection, and
does not retry the command. The existing menu reports the error.
Host tests cover a marker split across receives, delayed completion after a
socket timeout, deadline/EOF with partial output, send/receive errors and
banner draining. Existing charging and diagnostic action tests also pass.

Closing a connection does not establish that the remote process stopped.
After an incomplete operation, inspect device state before manually repeating
a write. Marker receipt confirms that the shell reached the following echo;
it still does not report the command's exit status. Capturing exit status and
persisting per-session transcripts are useful future extensions, particularly
before scripting sequences of hardware experiments.

## Validation boundaries

This change is host tooling, not an OTP/kernel/payload change. Checks passed
here using synthetic/stubbed transports and exact pinned public C source.
No live telnet, USB, Mac-specific runner, Nix evaluation, kernel build or
private capture was tested. On the laptop, first exercise the console change
with an observation such as `uname -a` and a known-good control payload.
The existing passive REG_ON capture gate remains unchanged.
