# J81 Fender ready condition: iOS 15.8.5 static audit

## Question

The Linux replay reaches GPC state `1`, but the PMGR page-5 `+0x4` bit 30
acknowledgement stays clear and the first RGX-core read stalls.  Is bit 30 a
software-controlled enable that Linux should write, or evidence of a missing
Fender/GPC condition?

## Artifact and method

The inspected artifact is the J81 iPadOS 15.8.5 (19H394) extracted
`AGXG4G.macho`.  Its embedded source strings identify this component as the
G4G Fender implementation (`agxk_fender_common.cpp` / `agxk_fender.h`).
The relevant virtual table is at `0xfffffff006f2ff30`.

## Direct observations

* The virtual entry at `+0x20`, `0xfffffff00669c3c8`, stores its requested
  32-bit value directly to the Fender register-base `+0`.  This is compatible
  with the observed iOS `0x40000000` store at the Fender control register; it
  does not establish that this store sets the later PMGR page-5 bit.
* The virtual entry at `+0x48`, `0xfffffff00669c4a8`, is an iOS GPC
  transition-completion guard.  Before it accepts the transition it requires
  `(~fender[0] & 0x60000000) == 0`, i.e. both Fender register-0 bits 29 and
  30 are already set.
* That same guard checks `fender[0x1000]` bit 4.  When set, it waits and
  rereads until the bit clears; a timeout emits the embedded diagnostic
  `GPC state transition is stuck!`.
* After this, it invokes another Fender virtual operation and requires the
  word at Fender `+0x8` to be zero before returning success.

The implementation uses a data-memory barrier before the first Fender read.
The G4G strings explicitly call this path `setGPCPerformanceState` and refer
to `GPC/Fender`; this is not a guessed PMGR/MCC interpretation.

## Consequence

Bit 30 is a *ready acknowledgement*, paired with bit 29, in the stock
Fender/GPC transition guard.  It is therefore not safe to treat the Linux
page-5 bit-30 difference as a write-one control.  The existing Linux result
(`GPC state 1`, page-5 `+0x4 == 0`) is stronger evidence of an upstream
Fender condition that the replay has not caused.

This also explains why merely making the `0x11` request and observing the
state poll succeed is insufficient: iOS has a separate readiness test and
an in-flight request check.

## Next evidence, not a new write recipe

The narrow next capture is read-only and should correlate, on a Linux replay
that has reached GPC state 1:

1. Fender register 0 bits 29 and 30.
2. Fender `+0x8`.
3. Fender `+0x1000` bit 4.
4. PMGR page-5 `+0x4`.

The same four words should be captured at the matching iOS post-poll
boundary.  Only a differing word can justify investigating an additional
prerequisite.  No register write is proposed from this audit.

## Limits

The static result proves the semantics of the G4G driver's transition guard,
not the physical producer of Fender bits 29/30.  The current J81 captures
establish page-5 bit 30, not yet all three Fender status words at the same
boundary.
