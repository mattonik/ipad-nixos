# J81 GPIO55 display-sync run: payload/build identity record

Status: **partial identity only**. This record is intentionally explicit about
what was and was not preserved alongside the reported run transcript.

## Reported run identity

| Field | Value | Evidence quality |
| --- | --- | --- |
| Payload name | `m1n1-hoolock-touch-spi` | Reported in `j81-touch-diagnostic.md` |
| Source commit said to contain the feature | `7aa92279a71ac36a68c6b0381c21a93d21cdca60` | Git object, committed before the report |
| Feature | guarded GPIO55 function-1 pinmux with exact restore | Commit and source tests |
| Boot type | cold boot | Reported only |
| Payload Nix store path | unknown | **not captured for this run** |
| `m1n1-linux.bin` SHA-256 | unknown | **not captured for this run** |
| On-device build identifier | unknown | **not emitted/captured** |

## Nearby control evidence — not identity for the reported run

The preserved preflight session
`artifacts/live/sessions/20261005T063017Z-24754818b6c54430a4842194f243d510/`
was recorded at source commit `770b03acd5ed09e8487a700d22c9f562a1253180`,
which predates the GPIO55 implementation. Its payload was:

```text
/nix/store/8ssi0vkjax230l97b0cyq1mkfp94bcpw-ipad-air2-m1n1-hoolock-touch-spi/m1n1-linux.bin
SHA-256 c320196bb3c367bc3e5a311692987d78786951e0dbac00d0eab4d9000088b006
```

It proves the earlier preflight environment and must **not** be attributed to
the display-sync execution.

## Required record for every future hardware run

Create one private `artifacts/live/sessions/<UTC-id>/` directory before the
run containing:

1. `manifest.json` with source commit, clean/dirty state, exact Nix store
   path, payload size and SHA-256;
2. an unchanged `commands.jsonl` with the command, stdout/stderr, timestamps,
   completion and return code; and
3. the first on-device log lines that uniquely identify the feature under test.

Where possible, add a harmless compile-time source revision string to the
payload/kernel log. A host SHA-256 alone does not prove which payload the
tablet booted; the run report should state that limitation if no on-device
identifier exists.

