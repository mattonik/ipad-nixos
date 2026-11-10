# J81 iOS writer/thread capture sources

These are the source and native host simulation used for the
[2026-11-10 capture](../../2026-11-10-j81-writer-thread-result.md). They are
research instrumentation, not a GPU driver. The device binary, Apple kernel
image and private logs are not included.

`j81_thread_capture.c` and `j81_thread_shell.S` were built in the
[palera1n PongoOS iOS15 branch](https://github.com/palera1n/PongoOS/tree/e98323f8a09abd80fc4cbcd74dee023b91a1ec22)
at commit `e98323f8a09abd80fc4cbcd74dee023b91a1ec22`, with the newlib
submodule at `f9ea5054de8fb51dff6f6d3c2e7cdd4aa89744b8`. The component must
be registered in the KPF component array as `j81_thread_capture`; build with
`KPF_CFLAGS=-DJ81_THREAD_DEVICE_BUILD`. It patches only the exact checked
iPadOS 15.8.5 19H394 XNU UUID and unique instruction signatures. The result
is a temporary kernel patch and may stall or reboot the device.

The `.S` host simulation replaces privileged thread-register and DAIF reads,
logger calls, and on-device resume branches with test substitutes; it is not
the code running in XNU. On an ARM64 Mac the principal cases can be run with:

```sh
for scenario in hosttest null overflow; do
  clang -arch arm64 -o "/tmp/j81-thread-$scenario" j81-thread-hosttest.S "j81-thread-$scenario.c"
  "/tmp/j81-thread-$scenario"
done
```

The host simulation does not establish device safety, scheduling, timing,
complete logging, or hardware write completion. Boot archives may contain
personal data and must not be committed.
