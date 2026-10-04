# Console session evidence, 2026-10-04

The console now creates a private evidence directory before connecting to
the iPad. It records command completion and shell exit status so a failed
command is distinguishable from a lost connection. No build, device probe,
upload or new hardware experiment is introduced by this tooling.

## Laptop usage

Build the intended control payload using the existing laptop workflow. Then
start the console with the local component files you want to identify:

```sh
python3 boot/ipad_console.py \
  --artifact kernel=result-kernel/Image \
  --artifact dtb=/path/to/the/actual/booted.dtb
```

`--artifact NAME=FILE` can be repeated for additional payload/bootloader
components. Names must be unique, files must be readable, and directories
are not accepted. Hash the exact files selected for the upload, not an
unrelated build directory. An invalid artifact fails before a connection is
attempted. No artifact is required to use the console; omitted components
are simply absent from the manifest.

The console prints its session directory under Git-ignored
`artifacts/live/sessions/`. Each session has:

- `manifest.json`: schema version, UTC start time, git HEAD/branch, working-tree
  dirty flag, Python/Git versions, OS/architecture, and supplied file paths,
  sizes and SHA-256 hashes.
- `commands.jsonl`: one JSON record per console command, with command text,
  timestamps, duration, cleaned output, endpoint, completion state and exit
  status. An unconfirmed completion has a null status and any available
  partial output/error. Completed nonzero exits are recorded before the
  console reports their failure.

Session directories are created with mode 0700; files with mode 0600.
Transcripts can contain device identifiers, calibration or other private
output. Keep the original evidence private and sanitize excerpts before
adding them to Git. These are command/result records, not a raw Telnet or
SPI capture; banner draining and menu keystrokes are not recorded.

The manifest identifies host files at hashing time. It does **not** prove
which payload is running on the iPad. Associate it with the actual upload
and record device-side identity observations separately. A dirty tree is
flagged but its diff is not embedded; commit the intended changes before a
session when reproducibility matters. Nix/compiler/RE-tool versions and
other laptop actions are not automatically collected.

## Exit status and failure behavior

`IPadShell.run()` now checks the POSIX shell exit status by default. A
nonzero exit raises `ShellCommandFailed` with `returncode` and `output`,
stopping that menu action. The connection remains usable after a confirmed
command failure. Scripts that deliberately expect a nonzero exit can use:

```python
result = shell.run_result("some-command")
print(result.returncode, result.output)
# Or request only output while explicitly tolerating a nonzero exit:
output = shell.run("some-command", check=False)
```

The status belongs to the final foreground command in the submitted shell
text. POSIX pipelines ordinarily report their last command; launching a
background process does not establish its later success. Commands ending
in `|| echo ...` report the fallback's status. This tool does not infer
hardware success from exit zero, and existing action semantics are retained.

Timeout, EOF, a malformed status trailer or a socket error leaves completion
unknown and closes the transport. No command is automatically replayed.
Closing a connection does not prove that the remote operation stopped.
Inspect device state before manually repeating a hardware write.

Evidence write/fsync errors surface explicitly with the known completion
state and status; the command is not retried. A transcript may be partial
after such an error. Resolve the storage failure before continuing a session.

## Offline validation and first laptop check

```sh
python3 tools/check_offline.py
```

The host suite includes twelve shell tests and four session-evidence tests.
It checks split trailers, nonzero exits, invalid statuses, connection errors,
partial-output recording, private modes, JSON lines, artifact hashes, invalid
inputs and evidence-write failures. A local `/bin/sh` fixture verifies the
actual status trailer for nonzero exits, output without a trailing newline,
quoted command text, multiple commands and a pipeline. No network or iPad
connection is used by these tests.

Before a hardware experiment, use the existing known-good payload and select
kernel info. Then use a raw command `false` to verify that status 1 is shown
and recorded, and `printf session-ok` to check that the same connection
continues to work. Inspect the manifest and both command records locally.
Keep the existing Wi-Fi passive-capture and touchscreen power/platform gates.

## Audit a collected session offline

Before using a transcript to guide the next experiment, check that its
records are readable and completion/status pairs are consistent:

```sh
python3 boot/audit_session.py artifacts/live/sessions/SESSION_DIRECTORY
```

The command emits a compact JSON report with counts of completed zero-exit,
completed nonzero-exit and incomplete commands, plus numbered issue records.
It omits command text, output, errors, endpoints, host paths, hashes and session
identifiers. There is no device connection or command replay. Reports with no
issues return exit 0; malformed or missing evidence and artifact mismatches
return exit 1. Usage errors return exit 2.

A nonzero command exit or an incomplete command is valid evidence and does
not by itself make the audit fail. An empty transcript is valid too. Neither
an audit exit of zero nor a zero-exit command establishes hardware success.
Use the counts to identify the private records requiring manual inspection.
This tool checks the current schema's key metadata and record fields; it
accepts additional fields for forward-compatible metadata extensions, but
rejects unsupported schema versions.

Artifact verification is opt-in, using explicitly supplied local files:

```sh
python3 boot/audit_session.py artifacts/live/sessions/SESSION_DIRECTORY \
  --artifact kernel=result-kernel/Image \
  --artifact dtb=/path/to/the/actual/booted.dtb
```

Names must match the manifest. A relocated copy is accepted if both byte size
and SHA-256 match. The auditor never opens file paths taken from the manifest;
missing original host files therefore do not block transcript inspection.
`artifacts_checked` counts files read, including mismatches; consult issues
and `evidence_valid` for the outcome. No arguments means no files verified.
This compares host files at audit time, without proving which payload booted.

The auditor rejects duplicate JSON keys, nonfinite numbers, invalid UTF-8,
inconsistent return codes and unfinished final records. It limits manifest
reads to 1 MiB and each JSONL record to 8 MiB, stopping at an oversized record.
A legitimate unusually large command output can exceed that limit and needs
manual inspection. It cannot detect an entire missing command, removal of a
whole final record, edits that remain internally consistent, or a session
crash between remote execution and recording: the files are not signed and
there is no terminal session marker. Keep original private evidence intact.

The offline runner includes eight synthetic auditor tests covering the real
session writer, relocation, corruption, privacy of emitted diagnostics and
CLI exit behavior. These require no build artifacts or hardware.
