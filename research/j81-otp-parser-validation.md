# J81 OTP parser validation and hardware evidence handoff

Software-only research, 2026-10-04. This follows the
[BCM4350 NVM shadow source audit](j81-bcm4350-otp-source-audit.md).

## Reproduced behavior in the pinned source

The harness extracts and compiles the actual two Apple-record parser
functions from Hoolock `pcie.c` at
`6831bc701a6ce059e71e5aaa9488c9195bea6927` ([source](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c)).
It requires SHA-256
`2bc4ff2f06eb515b404e08973a39c029ec975155a17a7baaf6f62e76ca181b4c`.
No private firmware or real OTP capture is used.

| Synthetic input | Original result | Prepared patch result |
| --- | --- | --- |
| Complete `M=TEST V=x m=1.0` record | Valid identity | Same valid identity |
| First record has only M; second has only V/m | Combines fields into a valid identity | Rejects; clears all identity state |
| Complete identity followed by truncated CIS record | Returns success and retains identity | Rejects; clears all identity state |
| Zero-length input | ASan reproduces a header read beyond the provided length | Rejects without reading input |
| Complete identity followed by one nonzero byte | Ignores incomplete header | Rejects |

The zero-length issue comes from unsigned `size - 1` underflow in the
outer loop. The actual reader currently supplies fixed positive chip-specific
sizes. **This is a host reproducer, not evidence of a reachable kernel fault
or a cause of J81's present Wi-Fi failure.** The current J81 reader does not
even enter the OTP path for BCM4350.

The mixed-record result comes from updating shared identity fields before
validating completeness. A later record can supply the previously missing
fields, and the final return code overwrites the first error. Truncated
trailing data similarly breaks the loop without replacing a prior success.

## Inactive hardening candidate

[`0049-brcmfmac-pcie-otp-parser-bounds.patch`](../kernel/patches/0049-brcmfmac-pcie-otp-parser-bounds.patch)
uses a size-typed cursor, checks available header/payload bytes without
underflow, and validates each system-vendor record in a local zeroed identity.
Only a complete record is committed. The stream starts with cleared state,
fails on an invalid system-vendor record or a truncated record, and clears
state on failure. Debug cursor formats follow the new cursor type.

Unknown bounded record types, bounded CIS records, the zero-type terminator,
unknown parameter tags, and multiple complete system-vendor records remain
supported. For multiple complete records the last complete identity wins,
as before. The existing string grammar and 15-character field limit remain.
It does not scan arbitrary offsets for identity strings or guess a tuple.

Failing at the first invalid system-vendor record is intentionally stricter
than the original behavior. A real Apple capture containing alternative or
partial records might require a documented format-specific policy instead.
Do not activate this candidate until its assumptions are checked against the
captured record layout. No kernel, Nix or payload references this patch.

## Reproducible offline checks

```sh
python3 kernel/test_brcmfmac_otp_parser.py --source /path/to/pinned/pcie.c
ASAN_OPTIONS=detect_leaks=0 python3 kernel/test_brcmfmac_otp_parser.py \
    --source /path/to/pinned/pcie.c --sanitize
```

[`test_brcmfmac_otp_parser.py`](../kernel/test_brcmfmac_otp_parser.py)
applies the candidate to a temporary copy with zero fuzz and compiles the
unmodified/patched functions against bounded host string-helper stubs.
Debug format checking remains enabled. Signed comparison and pointer-sign
warnings are suppressed for existing baseline kernel idioms; other enabled
warnings are errors. No parser algorithm is reimplemented in Python.

Checks cover complete/incomplete identities, mixed records, trailing
truncation, zero/one-byte inputs, malformed headers, missing string
terminators, empty/missing/overlong fields, exact 15-character fields,
whitespace, unknown tags, CIS/unknown records, zero terminators, multiple
complete records, stale state and every truncation of a valid record.
Each normal/sanitized run additionally processes 30,000 deterministic
synthetic streams of length 0–1024, half seeded with a valid identity before
random trailing data. Exact-sized heap allocations expose boundary reads.
The sanitizer run separately expects and confirms the original zero-length
heap-buffer-overflow, capturing its diagnostics rather than printing bytes.

GCC and ASan/UBSan checks pass. LeakSanitizer is disabled due the previously
observed environment restriction; no leak-check claim is made. This is
bounded deterministic input testing, not exhaustive fuzzing. No full kernel,
Nix, AArch64 or hardware test was performed.
The existing `0048` filename-selection harness also passes; applying `0048`
then `0049` to the pinned source succeeds with zero fuzz. These checks do not
activate either patch in a kernel build.

## Evidence to collect during the next hardware session

The ordering below preserves the latest
[corrected Stage 5H / REG_ON gate](t7000-pcie-hardware-findings.md#correction-after-stage-5h-vtable-mapping-and-bcm4350-power-state-2026-09-26),
including its following section on passive capture. The radio is still
blocked earlier than OTP.

| Phase | Useful evidence | Dependency / interpretation |
| --- | --- | --- |
| Control boot | Exact payload hash, boot log, kernel version, USB-shell availability | Establish a reproducible working baseline |
| Passive iPadOS Wi-Fi bring-up | Cold-boot D2207 SDA/SCL capture with transaction timing and prerequisite accesses | Recover persistent GPIO3 REG_ON behavior before proposing another GPIO-write payload |
| Future approved power/link experiment | GPIO3 readback high, documented delay, link state, PCI endpoint ID | No identity reads until the endpoint actually enumerates |
| Future bounded NVM diagnostic | BCM chip/revision, ChipCommon core base/revision, capabilities, layout, SROM control, mapping path and captured length | Register evidence must agree with the selected source-supported path |
| Private raw capture analysis | Explicit little-endian shadow bytes, proven record start/span, complete M/V/m within one record | Check parser assumptions before enabling 0048/0049 or selecting C2/C4/calibration |

For the control payload's existing shell, these observations do not load a
driver or change the radio:

```sh
uname -a
cat /proc/cmdline
dmesg
ls -l /sys/bus/pci/devices
```

Record the payload's SHA-256 on the host too. Keep full logs and captures
private because addresses, serial identifiers and command-line values may
be device-specific; publish only the findings needed for comparison.
This note provides no new PMIC writes, guessed MMIO reads, or automatic
firmware-loading commands. Patches 0048/0049 should stay out of the control
payload while the earlier power gate is unresolved.

Next source-only work: trace the old Apple loader's revision and calibration
selection. Actual capture decoding can proceed offline once hardware produces
the required bytes; filenames alone still cannot prove the correct quartet.
