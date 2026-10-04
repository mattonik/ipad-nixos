# Audio and sensors: source survey and corrected transport candidates

2026-10-04. This is offline research for J81/T7001. **The new topology below
is verified in the public J82 sibling ADT, not a fresh J81 capture.** It
narrows what to compare on the laptop and corrects assumptions in the old
hardware overview. It does not enable a driver, DT node, bus transaction,
power rail or register write.

## Sources and reproducibility

- SoMainline `adt_collection`, commit
  [`768d800c46140c9ba39a372d097fa49f7197a66d`](https://github.com/SoMainline/adt_collection/blob/768d800c46140c9ba39a372d097fa49f7197a66d/a8/J82.adt),
  `a8/J82.adt`, SHA-256
  `ee3a9ac310203254e02f6257d1d2ba9e63b3f47e7144855071a2c9636843f15a`.
- Existing sanitized [J81 Oscar findings](j81-touch-id-mesa.md#side-result-the-motion-sensors-are-behind-a-firmware-loaded-coprocessor)
  and [J81 audio plan](j81-long-term-subsystems.md#audio). These establish
  J81 identities and some power resources; they do not establish all the
  sibling transport assignments below.
- Hoolock Linux pin `6831bc701a6ce059e71e5aaa9488c9195bea6927`:
  [MCA driver](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/sound/soc/apple/mca.c),
  [MCA binding](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/Documentation/devicetree/bindings/sound/apple,mca.yaml),
  [codec Kconfig](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/sound/soc/codecs/Kconfig),
  [codec Makefile](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/sound/soc/codecs/Makefile),
  [IIO light Kconfig](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/iio/light/Kconfig).
  No CS42L81/MAX98721 codec entry or CT819 light-sensor entry was found in
  these configuration/build lists. This is a scoped source check, not proof
  that no unpublished or differently named implementation exists.

The new helper reproduces selected topology and resource cells without
copying a raw ADT or emitting its calibration/identifiers:

```sh
python3 tools/audit_j82_audio_sensors.py \
  --source /path/to/adt_collection/a8/J82.adt
```

It requires the exact public SHA-256, rejects other inputs before parsing,
checks that all 20 selected nodes exist, and emits an explicit property
allowlist. It is deliberately not a general private-J81 sanitizer. It does
not download files or connect to a device. Keep full dumps and audio/sensor
calibration private even when comparing these results locally.

## Three useful corrections

1. **Codec control is a SPI candidate.** In J82, `audio-control,cs42l81`
   belongs to `spi1/audio-codec`, while `audio-data,cs42l81` belongs to
   `mca0/audio-codec`. The prior generic I2C-control assertion in
   `hardware.md` should not drive a J81 implementation. Control and PCM
   data use separate transports. The SPI child's first `reg` cell is zero;
   the parent has one address cell. Remaining cells are Apple-specific
   configuration, not an I2C address or a proven SPI mode/rate.
2. **Oscar has a UART candidate.** J82 puts `oscar` under `uart8`, resolving
   the old overview's speculative SPI/I2C description for this sibling.
   This does not determine baud, framing, reset timing, firmware loading,
   message format or J81 resource equality. A generic Linux HID sensor
   driver cannot bind from `device-usage-page = 0xff00` alone: it is a
   vendor-defined page, not a decoded standard sensor report descriptor.
3. **Ambient light can be researched separately from Oscar.** Both J82
   `als,ct819` nodes are direct children of `i2c2`. Therefore the blanket
   motion-coprocessor dependency should not be applied to every sensor.
   CT819 remains an Apple compatible identifier here; no vendor model,
   register map or interchangeable Linux driver is established. Matching
   addresses alone would not establish compatibility with an APDS/TAOS
   driver.

## Sibling transport map to check against J81

All paths below are relative to `/device-tree/arm-io`. Addresses in the
controller column are **arm-io-relative**, exactly as decoded from the
ADT. Do not pass them to `devmem`; translate through `ranges` only after a
J81 comparison. Interrupt numbers and gate indices are descriptive ADT
values, not verified Linux bindings or power-domain references.

| J82 path | Role and compatible | Controller resource / child first `reg` cell | IRQ / gate |
| --- | --- | --- | --- |
| `spi1` | Codec control bus | `0x0a084000`, size `0x4000` | 153 / `0x4b` |
| `spi1/audio-codec` | `audio-control,cs42l81` | SPI address cell `0` | GPIO 116, raw flags `1` |
| `i2c1` | Speaker control bus | `0x0a111000`, size `0x1000` | 175 / `0x47` |
| `i2c1/audio-speaker0` | `audio-control,max98721` | address cell `0x31` | GPIO 8, raw flags `1` |
| `i2c1/audio-speaker1` | `audio-control-secondary,max98721` | address cell `0x34` | GPIO 9, raw flags `1` |
| `uart8` | Oscar transport candidate | `0x0a0e0000`, size `0x4000` | 166 / `0x58` |
| `uart8/oscar` | `apple-oscar`, `oscar1`, `oscar` | no child `reg` | reset/power described separately |
| `i2c2` | ALS control bus | `0x0a112000`, size `0x1000` | 176 / `0x48` |
| `i2c2/als1` | `als,ct819` | address cell `0x49` | GPIO 103, raw flags `1` |
| `i2c2/als2` | `als,ct819` | address cell `0x29` | GPIO 110, raw flags `1` |

The public I2C nodes spell the property `#address-cels` (one `l`), not the
Linux binding's `#address-cells`. Preserve that distinction when reading
the evidence. The first child cell is a transport-address candidate; the
remaining private cells must not be copied into a Linux I2C `reg` property.
The codec SPI parent does use the correctly spelled `#address-cells`.

## PCM routing and a concrete MCA mismatch

| J82 controller | Data child | Main region / size | Second region / size | IRQ / gate |
| --- | --- | --- | --- | --- |
| `mca0` | `audio-data,cs42l81` | `0x0a0a0000` / `0x4000` | `0x0a002000` / `4` | 169 / `0x40` |
| `mca1` | `audio-data,voice` | `0x0a0a4000` / `0x4000` | `0x0a002004` / `4` | 170 / `0x41` |
| `mca3` | `audio-data,max98721` | `0x0a0ac000` / `0x4000` | `0x0a00200c` / `4` | 172 / `0x43` |
| `mca4` | `audio-data,bluetooth-voice` | `0x0a0b0000` / `0x4000` | `0x0a002010` / `4` | 173 / `0x44` |

A separate `i2s-switch` occupies `0x0a003000`, size `0x1000`. Each MCA node
lists `mca,t7001`, `mca,s5l8950x`, version 1, and `dma-parent = 0x24`.
These are not the current Linux MCA binding. The existing driver matches
`apple,t8103-mca` / `apple,mca`, derives cluster count from the first mapping,
and treats its second mapping as DMA glue with per-cluster A/B windows.
Its compiled `USE_RXB_FOR_CAPTURE` path accesses the B window at offset
`0x4000` even for cluster zero, beyond a four-byte second region described
by each old ADT MCA node. The modern binding likewise describes a sizeable
DMA-glue/FIFO region rather than these per-controller four-byte resources.

This is a specific reason **changing compatible strings is insufficient**.
It does not prove the old silicon has no related SERDES registers; it means
its resource layout and DMA path must be established independently before
reusing code. The old nodes' `dma-channels` packing and I2S-route callback
arguments are not decoded by this audit. In particular, the visible 16 KiB
controller stride alone is not evidence that the modern DMA implementation
is compatible.

## Next offline work and evidence gates

| Work item | Useful result before another hardware experiment | Remaining device evidence |
| --- | --- | --- |
| Local J81 topology comparison | Confirm parents, resource cells and compatible strings for these 20 nodes; record only reviewed resource fields | The existing private ADT may suffice; no new boot required if it contains these nodes |
| CT819 driver analysis | Locate the matching iOS driver by the compatible string; establish register widths, ID-read behavior, power dependencies and lux/calibration transformation | Later native/light-change observations; no guessed probing or bus scan |
| CS42L81 transport analysis | Establish SPI command framing, chip-select behavior, reset/mute lifecycle, and read-only ID/status semantics | Later compare a bounded native control trace |
| Old MCA/SIO analysis | Decode route callbacks and DMA message/channel format; compare individual SERDES fields to the modern driver | Later silent DMA completion and clock measurements |
| Oscar transport analysis | Locate UART setup, firmware transfer and message/report framing; reuse serial infrastructure only after matching the protocol | Later native startup and timestamp/report observations |

The smallest newly exposed survey is CT819: it may avoid both audio DMA and
Oscar firmware, although its register protocol is still unknown. Audio's
first usable milestone remains conservative headphone playback after its
control, clock and DMA dependencies are independently understood. Existing
speaker-calibration and power gates remain in force.

## Validation

Ran the extractor against the exact public file: 20 expected nodes, both
ALS parents, SPI codec parent, UART Oscar parent and all four MCA mappings
matched direct source inspection. A one-byte-modified source was rejected
with exit status 2 and no JSON output. Checked that emitted keys are limited
to the declared allowlist and include no calibration/identifier properties.
`git diff --check` passed. No Nix build, kernel runtime, private J81 dump or
hardware was exercised; this is topology/source validation only.
