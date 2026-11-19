# J81 MiscACG is set immediately after iPadOS enables it

## Result

The iPadOS 15.8.5 / 19H394 post-enable probe recovered two attributed kernel
records from a whole-device unified-log archive. Both measured PMGR region 0
offset `0x32000` immediately after `ApplePMGR::enableACG(true)` returned:

| Timestamp (UTC+1) | Boot UUID | Value |
| --- | --- | --- |
| 2026-11-19 15:27:19.788544 | `B5C9CF9C-F412-416E-BC8E-0DFCA7F459B6` | `0x00000001` |
| 2026-11-19 16:08:14.614075 | `6B5D51C5-D33A-4FE2-947C-E26532C14C5F` | `0x00000001` |

The messages originate from `/kernel`, use the expected AGXk logger format,
and do not carry the probe's `map=0` sentinel. The PMGR mapping and load are
therefore evidenced; bit 0 was set in both observed runs.

## What this resolves

The earlier iPadOS entry sample and Linux post-GPC sample were both zero, but
they were at different phases. This result fills the missing iPadOS phase:
MiscACG becomes set directly after ApplePMGR enables it and before the next
voltage-manager call.

## What it does not establish

This does not show whether the bit stays set through the GPC request, whether
it causes page-5 bit 30, or whether a Linux write is safe. A zero Linux sample
after GPC is not a phase-matched comparison.

## Next discriminator

On one fresh observer Linux boot, capture PMGR words `0x32000`, `0x1008`, and
`0x4008` after the successful GFX get/put/get cycle, after the existing bridge
plan, and after the paired GPC/page-5 batch. Preserve boot identity and all
watchdog checkpoints. Only a pre-GPC Linux value paired with that same boot's
GPC/page-5 outcome can justify considering an isolated MiscACG experiment.

Raw archive exports and digests remain private in the builder mailbox.
