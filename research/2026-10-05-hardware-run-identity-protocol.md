# Reproducible J81 hardware-run identity protocol

Status: research handoff; protocol proposal only.  No loader or payload was
changed while preparing this note.

## Problem

Current session evidence is valuable host-command evidence, but it explicitly
says it does not prove the payload running on the device.  This is accurate:
the loader sends a byte stream and checks a returned byte count, while a USB
disconnect after `bootm`/`bootl` means only that handoff may have started.

An identity-qualified result needs a device-visible binding in addition to
host-side hashes.  It is still not remote attestation; it is an effective
detector for accidental payload, transcript, and run mismatches.

## Protocol

### 1. Prepare a durable run record before touching the device

Create `artifacts/live/runs/<UTC>-<128-bit-random>/prepared.json` and a
dedicated raw-transcript directory.  Record:

* run token and UTC start;
* Git commit, branch, dirty state, and `flake.lock` hash;
* resolved store/output paths, never merely a mutable `result` symlink;
* SHA-256 and byte length of every relevant component: Pongo, m1n1, final
  upload artifact, kernel, DTB, initramfs, bootargs, and `SHA256SUMS` itself;
* exact launcher argv plus launcher executable hashes/version strings;
* USB device identifiers observed before transfer.

The final upload artifact is the identity anchor.  Preserve its exact path,
size, and SHA-256 even when its inputs are also recorded.

### 2. Bind the exact upload to a device-observable token

After separately verifying the canonical build components, compose one
run-specific, immutable staging payload in the known boot-container order.
Its bootargs must include `j81.run_id=<128-bit-token>`.  Hash and size this
staging payload and record it as the actual upload identity.

Do not mutate an already-concatenated artifact in place or claim that the
canonical pre-token payload hash was uploaded.  A run-specific payload has its
own hash; preserving both identities makes that distinction auditable.

The project boot chain already uses a text `chosen.bootargs=...` record, and
Linux exposes the resulting kernel command line through `/proc/cmdline`, so
this needs no speculative new protocol.

### 3. Preserve every phase as raw, append-only evidence

For every launcher, DFU, upload, Pongo, and serial-console phase, append a
JSONL event with UTC time, phase, argv reference, input/output hashes, USB
identities, expected and returned byte counts, process exit status, and raw
stdout/stderr filename plus hash.  Each record includes the previous record's
hash to detect simple truncation or reordering.

Classify transfer outcomes precisely:

* `not_uploaded`;
* `upload_ambiguous`;
* `handoff_only`;
* `device_token_observed`;
* `experiment_complete`.

A disconnect, short write, loader crash, or retry ends that attempt.  A retry
must begin a new run directory rather than silently extending the old record.

### 4. Qualify the result on device

Once the console is live, make `cat /proc/cmdline` the first captured command.
Only an exact match of the run token promotes the run from `handoff_only` to
`device_token_observed`.  Then capture kernel version, live DT identity,
relevant PCIe/DART observations, and the existing SessionEvidence reference.

`final.json` should reference every raw transcript by SHA-256 and state the
strongest claim actually supported.  Optional detached signing can later make
host-side tampering more evident, but it is not required for the protocol's
first useful version.

## Acceptance rule

Call an H0/H1/H2 observation identity-qualified only when all four are
retained together:

1. prepared record with exact uploaded-artifact hash;
2. complete transfer/handoff raw transcript;
3. on-device `/proc/cmdline` containing the exact run token;
4. final record linking the hardware observation to that token and its raw
   logs.

Anything weaker may still be useful, but must be described as host evidence or
handoff evidence rather than proof of the payload that produced a device-side
observation.
