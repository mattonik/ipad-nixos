# Morning run: iOS page-5 writer tracer

This is an experimental temporary rootless iPadOS boot for the J81 on
15.8.5 (19H394), not a Linux GPU bring-up. It retains five prior undocumented
reads and instruments a globally used PMGR store. It may change timing, hang,
reboot or lose the log; a normal reboot removes the boot-time patch. Keep the
iPad connected and be ready to recover with DFU. It has not been device-tested.

## Boot

On the Mac, from the repository root, check the prepared local module:

```sh
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos
shasum -a 256 -c artifacts/live/private/j81-ios-page5writer-probe/SHA256SUMS
```

The expected SHA-256 is `d0e8c2c019a469db97540eb9715efd85b6c8562430c262a37b6361bd098833b4`. Stop if verification fails; the private module is not in Git.
Put the iPad in DFU, then run:

```sh
sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-page5writer-probe/page5-writer4 --debug-logging
```

Enter the Mac password if requested. If palera1n remains at “Booting PongoOS”,
reconnect USB; if it still does not advance, interrupt it and rerun the same
command, as in prior runs. Record the terminal output, especially any
`J81_PAGE5WRITER_EMIT` and `J81_PAGE5WRITER_PATCH` messages if visible. A patch
rejection or missing log is not a hardware result. After iPadOS boots, unlock
it and reconnect USB if the Mac cannot see it.

## Capture

The archive can contain personal system information. Keep it in the ignored
private directory; do not commit or publish it. Use a fresh directory, so a
repeat run does not overwrite the previous capture:

```sh
umask 077
mkdir artifacts/live/private/ios-logarchive-j81-page5writer-01
idevicesyslog archive artifacts/live/private/ios-logarchive-j81-page5writer-01/capture.tar
mkdir artifacts/live/private/ios-logarchive-j81-page5writer-01/boot.logarchive
tar -xf artifacts/live/private/ios-logarchive-j81-page5writer-01/capture.tar -C artifacts/live/private/ios-logarchive-j81-page5writer-01/boot.logarchive
/usr/bin/log show --archive artifacts/live/private/ios-logarchive-j81-page5writer-01/boot.logarchive --style compact --predicate 'process == "kernel"' > artifacts/live/private/ios-logarchive-j81-page5writer-01/kernel.log
```

Check the command exit status at each step; if collection fails, preserve the
partial files and diagnose before retrying in a new directory. Find the latest
boot's GPU identity and probe lines (`PAGE5`, `Q=`, `C=`, `T=`, `M=`, `Z=`,
`W=`); correlate their timestamps, because an archive can include older boots.
The [probe README](README.md) explains the fields and limitations. Keep the full
log private; prepare a sanitized result note for sharing.

## Decision

A `W=00000001:00000001:<value>` line is a useful lead: this particular filtered
store completed in the coarse window, but it does not prove causation or device
acceptance. Investigate its origin before attempting a Linux write. Boundary
records are ambiguous. A zero count, missing C/M or identity markers, `seen=0`,
overflow, `W=UNREADY`, missing logs, or a reboot are inconclusive. Even a clean
zero count cannot exclude a writer delayed before reservation, another object or
alias, direct access, firmware or autonomous hardware. Do not guess a bit-30
write from this experiment.
