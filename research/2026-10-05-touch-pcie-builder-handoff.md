# J81 touch and PCIe implementation handoff

Date: 2026-10-05. This is a static research handoff for the builder. It does
not authorize a boot, device connection, PMU write, SPI transfer, firmware
upload, or Bluetooth work. Evidence below is either from the checked-in source
and recorded prior sessions, or marked unknown.

## What is ready to build

Two bounded changes are ready for implementation and build-time verification:

1. extend the existing `touch-diag` *diagnostic only* with an explicitly
   requested, reversible GPIO55 display-sync **pinmux** experiment; and
2. package the hardware-proven BCM4350 Wi-Fi `REG_ON` prerequisite as a
   board-declared PCIe resource, keeping it separate from Bluetooth and from
   the broader task of turning the Stage-5 test driver into a clean driver.

Neither change is a touchscreen driver, a firmware uploader, or a Bluetooth
enablement path.

## Touch: exact result and implementation contract

### Resolved question: `function-enable_download`

The exact iPad5,3 iOS 8 binary is not in the workspace, so an exact J81/iOS-8
return-value trace remains unavailable. It is not a practical blocker:

- The public unstripped iOS 10.3 J82 sibling driver calls
  `function-enable_download`; an absent provider returns
  `kIOReturnUnsupported` without any GPIO/SPI operation.
- Its `finishStarting()` immediately continues after the enable call and does
  not branch on that return value.
- J81's captured ADT also lacks this callback.

Therefore **do not add `download-gpios`, invent a download-mode level, or
pretend that a missing callback is an error**. Treat it as optional/non-gating.
The evidence and scope caveat are recorded in
[`2026-10-04-touch-callback-resolution.md`](2026-10-04-touch-callback-resolution.md).

### Resolved question: `function-display_sync`

Apple's J81 callback does not drive GPIO55 high. Its `mode=3` request maps via
the J81 descriptor to Apple GPIO pin mode 2:

```text
GPIO55 config := (saved & ~0x260) | 0x220
                     ^ PERIPH=1, INPUT_ENABLE=1
```

This is the same pin function Linux represents as `APPLE_PINMUX(55, 1)`.
The recorded baseline word is `0x00072a82`, for which `PERIPH=0`; it is a plain
GPIO output-low state, not Apple's requested peripheral state. GPIO51's known
SPI3 chip-select state independently validates that field decoding. Details:
[`2026-10-04-display-sync-pinmux-decode.md`](2026-10-04-display-sync-pinmux-decode.md).

### Build this exact diagnostic change

Modify [`boot/touch-diag.c`](../boot/touch-diag.c), not the normal DT and not
the touchscreen binding.

- Add an opt-in `run` flag named `--display-sync-pinmux`; require it together
  with the existing `--execute --approve-pmu-write`, and add a distinct
  `--approve-display-sync-pinmux` acknowledgement. Require `--spi-dev` too:
  this experiment is specifically the missing pinmux plus the existing four
  harmless handshake frames, not an automatic boot-time configuration.
- Do **not** add a default pinctrl state to the DT. There is no userspace API
  to select that state temporarily; a probe-time DT state would silently
  mux GPIO55 on every boot. A guarded, short-lived diagnostic is the right
  scope for this unknown display-pipe signal.
- In writable diagnostic mode, map the GPIO page writable as well as readable.
  The current `open_mem(1)` only maps `g_gpio` with `PROT_READ`, so a new flag
  alone would not work. Do not make the `status` path writable.
- Immediately after the existing LDO/power delay and immediately before the
  existing dummy frame, snapshot the full GPIO55 word. Refuse to proceed
  unless `(saved & 0x60) == 0` (`PERIPH=0`); never steal a pin already muxed
  to another peripheral. Write `(saved & ~0x260) | 0x220`, then verify only
  that `(readback & 0x260) == 0x220`.
- Keep the selected mux through the existing dummy-before-reset frame, reset
  release/IRQ wait, and wake/short-ATN/long-ATN frames. It must not introduce
  any new frame, firmware blob, register command, GPIO level write, or
  download-mode action.
- On every exit after a successful mux, first assert reset as the existing
  unwind does, then restore the exact saved 32-bit GPIO55 word and verify that
  readback equals it; only then continue rail/clock cleanup. If the initial
  pinmux write or its verification fails, restore the saved word before the
  rest of cleanup as well.
- Print the saved word, requested field, readback, and restored word. The plan
  output and top-of-file safety description must say that this is a pinmux
  change, **not a GPIO-high write**, and that it remains a user-approved
  experiment.

The successful prior diagnostic already proves power, clock, reset, and a boot
IRQ. It does **not** prove command acceptance. The expected value of this
change is a tightly scoped comparison against the existing SPI idle-pattern
result, not a claim that touch will work.

### Touch build-time acceptance checks

- Add source-level tests beside [`boot/test_touch_diag_frames.py`](../boot/test_touch_diag_frames.py)
  for the exact masks/values (`0x260`, `0x220`), both acknowledgement flags,
  mandatory SPI device, `PERIPH=0` refusal, and saved-word restoration.
- Keep the existing no-firmware/no-register-write frame test passing.
- Compile both touch diagnostic payload variants. Do not boot either payload
  as part of this handoff.

## PCIe Wi-Fi `REG_ON`: production-hardening boundary

### Hardware facts that may be encoded

The already recorded, user-approved test established the narrow prerequisite:

| Fact | Value |
| --- | --- |
| Wi-Fi control | D2207 GPIO3 only, configuration register `0x0403` |
| Baseline / asserted byte | `0x09` -> `0x0b`, via `(old & 0x1d) | 0x02` |
| Required delay | 100 ms after verified assert, before PCIe setup |
| Endpoint after host sequence | `14e4:43a3` BCM4350 family, 2.5 GT/s x1 |
| Bluetooth control | D2207 GPIO2 / `0x0402`; deliberately out of scope |

The PMU resets the GPIO on reboot. Retaining asserted `REG_ON` across a later
probe failure or driver unbind is intentional until there is evidence that
deasserting it after partial PCIe setup is safe. The full evidence is in
[`j81-d2207-gpio-register-correction.md`](j81-d2207-gpio-register-correction.md).

### Immediate builder task: board-bound staging payload

The current uncommitted candidate is
[`0052-pcie-apple-t7000-j81-reg-on.patch`](../kernel/patches/0052-pcie-apple-t7000-j81-reg-on.patch),
with its Nix source recipe in
[`hoolock-pcie-j81-reg-on.nix`](../kernel/hoolock-pcie-j81-reg-on.nix). It is
the correct narrow implementation target, with these non-negotiable limits:

- Declare `apple,reg-on-pmic = <&d2207>` only in `t7001-air2.dtsi`; do not put
  it in generic `t7001.dtsi` and do not search globally for a PMIC.
- Read `0x0403`, reject unexpected upper bits, write only
  `(old & 0x1d) | 0x02`, require exact readback, and wait 100 ms. A declared
  PMIC that is unavailable must defer/fail the PCIe probe; silently continuing
  with unknown radio power is not acceptable.
- Keep both the property binding documentation and the explicit comment on
  intentional non-deassertion.
- Do not mention, write, package, or initialize Bluetooth (`0x0402`,
  `btattach`, or Bluetooth firmware) in this target. The Wi-Fi-only payload
  must also keep I2C command-line tooling out of its initramfs.
- Do not boot or hardware-test it yet. The builder may run static checks and
  builds only.

The existing `kernel/test_pcie_j81_reg_on_patch.py` has a zero-fuzz apply mode
when passed the exact Stage-5F source. Use it, then build the Wi-Fi-only
payload and inspect its DT/initramfs. This establishes a reviewable build
artifact; it is **not** a claim that the inherited PCIe driver is production
ready.

**Current-tree hygiene note:** `git diff --check` currently reports whitespace
errors inside the uncommitted `0052` patch. Regenerate or clean that patch as
part of the builder's first commit; do not normalize unrelated working-tree
changes.

### Follow-up builder task: clean the inherited Stage-5F host path

Keep this as a separate commit/series after the narrow REG_ON payload builds.
`0052` currently stacks on `0016` and `0040`--`0045`; those are evidence-led
test stages with test log strings and a diagnostic link poll. Do not relabel
that stack as production merely because REG_ON is board-gated.

The cleanup target is precise:

- Preserve only the exact port-1 enable ordering and generic Gen1 root-port
  capability RMW that the recorded endpoint enumeration relies on. Do not add
  any Stage-5G/5H deltas, new PMU actions, PHY guesses, or Bluetooth work.
- Replace the direct controller-window `+0x88` bit-6 poll. On the successful
  REG_ON run it reported false even though the endpoint enumerated; its bit
  meaning is undecoded. It is not a valid link-success criterion.
- Before endpoint enumeration creates a `pci_dev`, use the already established
  root-port ECAM view (bus 0/device 1/function 0; the current code calls it
  `cfg->win + 0x8000`) and the standard PCIe capability list. Poll/read
  `PCI_EXP_LNKSTA`'s DLL Link Active bit (bit 13) with a bounded timeout, or
  allow normal enumeration/config-space accessibility to be the success
  outcome. Do not call generic `pci_dev` helpers before enumeration.
- Keep the target link speed at Gen1/2.5 GT/s: the BCM4350 only supports it.
  The observed “retraining failed” is the generic core trying the root port's
  advertised 5.0 GT/s, then correctly ending at the endpoint's 2.5 GT/s; it is
  not a reason to widen scope.
- Remove diagnostic-only terminology and stale claims only after retaining
  comments that distinguish directly recovered writes from unresolved parts.
  The resulting driver still needs a normal review; it does not authorize a
  hardware run.

### PCIe static acceptance checks

- Zero-fuzz patch application against the exact pinned source, including the
  DT binding file.
- Kernel and Wi-Fi-only payload build. Confirm the compiled DT contains the
  PMIC phandle only for J81 and the payload contains neither `btattach` nor
  I2C command-line tools.
- Add a source-level check that `0x0402`, Bluetooth helpers, global compatible
  PMIC searches, and `+0x88` bit-6 success logic are absent from the clean
  path. For the initial staging payload, explicitly record that the latter is
  inherited technical debt rather than silently treating it as a pass/fail
  indicator.

## Out of scope and next research gate

- No touchscreen binding, event parser, firmware upload, or private firmware
  asset handling.
- No Bluetooth work.
- No new PCIe MMIO sequence beyond the proven Stage-5F base.
- No hardware execution without a separate user approval. If/when approved,
  the touch run must use the explicit dual acknowledgement and the PCIe run
  must first be reviewed as a boot payload; neither is part of the builder's
  build task.
