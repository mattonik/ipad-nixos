# J81 Apple packed view offsets

The Apple layout calculator stores four packed allocation offsets at
`param+0x524`, `+0x534`, `+0x544`, and `+0x554`. The firmware-preparation
routine passes those offsets through vtable `+0x210` as the four indexed view
addresses.

For the extracted J81 image, the recovered values are:

| Apple segment | packed offset |
|---:|---:|
| 0 | `0x00000` |
| 1 | `0x0f000` |
| 2 | `0x13000` |
| 3 | `0x14000` |

This exactly matches the metadata-only model's 4 KiB-aligned extents. The
remaining unknown is now the address-view method's conversion from these
packed offsets to the four Apple provider views; the offsets themselves are no
longer ambiguous.

No firmware or device state was changed.
