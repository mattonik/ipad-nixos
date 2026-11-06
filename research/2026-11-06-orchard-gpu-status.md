# Orchard GPU status check

The local Orchard GPU checkout and `origin/main` still point to
`42f6add03616d065d137e60c2cd7fde8780e5203` (2026-11-04). A fresh remote
check found no newer `main` commit. Its published support description still
lists J71b and iPhone 6 as the experimental GPU targets; it does not add an
A8X/J81 driver or bridge contract.

The A10 material remains useful as a sequencing reference only: it depends on
the A7-IOP/GFX coprocessor and Fender state path, which the J81 hardware
description lacks. It does not resolve the J81 `0x80010004` bridge encoding.

The iPad answered ICMP during this check, but its SSH host key did not match
the repository's pinned key. No SSH probe or hardware access was attempted;
the mismatch must be resolved by a verified fresh boot before using the device
again.
