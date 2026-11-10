# Next discriminating comparison: the existing iOS PMGR and GPC polls

2026-11-10. Offline analysis after the iOS bridge and thread captures; no
new hardware access. The goal is to compare a working iOS boot with Linux
at a state boundary closer to the stalled RGX access, without adding MMIO.

Linux's host-paced run read GFX PMGR `0x3ff`, GPC state `1`, and GPC control
`0x40000000`, then acknowledged the first RGX identity read without a
result ([paced result](2026-11-09-j81-campaign-paced-result.md)). On iOS we
captured target nibble 0 before the state transition and a 0→15 request,
but **not** the full PMGR word after that transition. We captured successful
RGX identity reads but have not captured the working iOS boot's GPC poll
value or proved the conditional GPC branch ran. Therefore equivalence of
these full state observations is currently unknown.

## Concrete passive capture candidates

The 19H394-matched `ApplePMGR` static setter `bc6ed8` reads the PMGR word,
writes an adjusted target through virtual slot `+0x988`, then requests a
poll through `+0x990` with mask `0xf0` and desired actual state `0xf0`.
The generic poll function `bd0564` calls virtual read `+0x980` and at
`bd05d0` consumes the returned raw `w0` with `and w8,w0,w21`; it compares
the masked value at `bd05d4`. Its preserved arguments at that instruction
are region selector `x19`, relative offset `x20`, mask `w21`, expected value
`w22`, instance `x23`. The captured Pongo ADT maps the GFX state to region
0, offset `0x20320`, instance 0. A capture of already-returned `w0` at this
site, conditioned on those arguments and the GFX provider thread, could
compare the full iOS poll word with Linux's `0x3ff` without issuing an extra
read. The 19H394 image contains both the setter's existing read sequence and
the six-instruction sequence beginning at `bd05cc` exactly once. The virtual
`+0x990` runtime target is not yet independently proved to
be `bd0564`; an unobserved hook must remain inconclusive. The timeout path
also has a second read site, so the first-loop site is not exhaustive.

Separately, the AGX probe's existing GPC loop reads `+0x1000` at `68399c`,
tests bit 4 at `6839a0`, and delays 10 µs before identity. The exact five
instructions around this loop occur once in the 19H394 kernel image. A
candidate hook can copy the **already loaded** `w8` and a reached marker,
then preserve the original `tbnz` semantics and defer logging until after a
known-safe boundary. The outer setup branch can bypass the loop; a missing
marker means unobserved, not zero. The final observed poll sample can then
be compared with Linux's state 1. The AGX mapping's physical identity and
the active runtime branch must be established for that boot; it is not a
new read of `0x201e01000`.

Both candidates require exact build/UUID and unique-signature checks, branch
range checks, correct condition flags and register preservation, bounded
buffering, and device/instance/thread attribution. They can change timing
and may crash iPadOS. The plan is not yet an implementation or a hardware
result. Full-word equality would rule out only the measured states at those
particular moments; inequality would narrow the investigation, not prove a
write is safe or responsible for the Linux stall.

## What the current raw word does and does not say

Linux's `0x3ff` has both state nibbles 15 and bits 8/9 set at its readback.
The generic Linux driver clears its named historical gating flags in the
*value it writes* when changing state; this does not establish those bits'
readback semantics or explain why the observed word is `0x3ff`.
[Linux PMGR source](https://github.com/torvalds/linux/blob/master/drivers/pmdomain/apple/pmgr-pwrstate.c)
defines those bit names. The Apple setter also manipulates bits 8/9 in its
written value, but the working iOS word has not been observed. Do not infer
a confirmed platform difference from static write expressions alone.

The offline disassembly was made from the existing extracted PMGR slice;
`ios15pmgr-poll-insn-20261110.log` and
`ios15pmgr-setter-insn-20261110.log` remain under the ignored private
artifacts. The test input's exact image provenance is documented in the
[19H394 comparison](2026-11-09-j81-ios1585-kernelcache-comparison.md).
