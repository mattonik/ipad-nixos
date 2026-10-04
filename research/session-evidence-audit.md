# Session evidence audit, 2026-10-04

## Finding and outcome

PR #7's console records confirmed completion, shell status and private
transcripts. A recording/fsync failure is surfaced, but a later reader still
needs to distinguish a readable session from a truncated file and explicit
host-artifact matches from stale paths. Inspection of `boot/session_evidence.py`
and `IPadShell._record()` in `boot/ipad_console.py` at base commit
`20d131192dee79d43cce22718e6882591fa40e6c` established the fields emitted by the current producer.

Added `boot/audit_session.py`, a host-only reader that validates those key
fields, reports transport-completion categories, and optionally compares
explicit host files against saved artifact sizes and hashes. It emits fixed
issue codes and record numbers, keeping private output and identifiers out
of its report. It does not interpret driver messages or hardware success.

## Evidence and limits

Eight synthetic tests exercise real producer output, known command failures,
incomplete commands, duplicate JSON keys, malformed statuses, partial JSONL,
invalid metadata, missing files, bounded record reads, moved artifacts,
changed artifacts and CLI exit semantics. The host suite also runs these
checks via `tools/check_offline.py`.

This checks internal consistency, not authenticity or proof of recording
completeness. Whole-record deletion and crashes before recording cannot be
detected by the present format. A future version could add command-start
records plus session-finalization metadata, but that needs a producer schema
change and still cannot prove the physical device's outcome. This outcome
leaves the recording and device-execution paths untouched.

Usage, exit codes and review limitations are documented in
[hardware-session-evidence.md](../docs/hardware-session-evidence.md#audit-a-collected-session-offline).
