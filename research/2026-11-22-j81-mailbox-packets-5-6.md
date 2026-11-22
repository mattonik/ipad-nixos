# Mailbox packets 5 and 6 (2026-11-22), offline research requests

Placed in `builder-mailbox/to-builder/` on the NAS (results expected in `from-builder/`). No hardware.

- `2026-11-22-j81-research-rgx-post-id-bringup`: stock sequence after the core-ID read until GPU firmware runs (firmware processor, image and memory, GPU MMU, interrupts/clocks) and a smallest-step Linux plan.
- `2026-11-22-j81-research-gpu-voltage-minimal-recipe`: DWI voltage code and D2207 mapping (is 0x64 a voltage, which buck), DVFM table, which recipe steps are needed with dwi on, always-on early-boot assumptions, voltage bounds.

Context given: the dwi summary, dwion-core result, identity plan and result notes.
