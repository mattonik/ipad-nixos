# J81 iOS PMGR/GPC poll comparison probe

Prepared 2026-11-10; not yet run on hardware. This extends the previously
booted [thread capture](../j81-thread/README.md), adding hooks which record
values returned by existing iOS PMGR and GPC poll reads. It does not add MMIO
accesses. It logs after the original RGX identity reads using the same
format/logger mechanism as the previously booted identity probe.

The additional log message is `Pp=xxxxxxxx Gg=xxxxxxxx I=xxxxxxxx`:

- `P1` means the PMGR poll hook observed an existing read for region 0,
  offset `0x20320`, instance 0, mask and expected value `0xf0`, in the GFX
  provider thread. The value is the last matching poll sample. `P0` means
  no matching sample was observed, not a zero register value.
- `G1` means the existing GPC poll loop returned with bit 4 clear on the
  GFX provider thread, and the value is that original read. `G0` means no
  such result was observed, not a zero register value. The setup/poll is
  conditional in the iOS driver.
- `I` is the existing RGX `+0x20` identity read, printed after both original
  identity loads returned. It is a positive control for reaching that point,
  not a Linux result.

An unobserved PMGR hook could mean the iOS virtual poll uses another method,
the arguments differ, or the path was skipped. Poll and identity points are
not simultaneous; Linux's saved PMGR `0x3ff` and GPC state `1` were observed
on a different boot. Same-thread matching does not exclude interrupts.
Samples can differ without proving causality. No extra MMIO, reset, clock or
bridge write is performed by the instrumentation.

## Build and checks

The source uses the PongoOS iOS15 checkout and newlib revisions documented
in the [thread probe](../j81-thread/README.md). Register component
`j81_pollcompare_capture` and build with
`KPF_CFLAGS=-DJ81_POLLCOMPARE_DEVICE_BUILD`. It requires the exact checked
19H394 kernel UUID and all nine unique signatures; branch ranges and the
entire hook set are validated before patching. The built module remains in
the ignored local private artifacts, SHA-256
`e7139a6b4dfc898e00440e8ae7c1e79aae2c4c69ca2a91fa4cc6088d50f2e9e6`.

The host KPF harness accepted the target image and rejected each individually
missing or duplicated signature and a wrong UUID. Native ARM64 simulations
tested PMGR filter rejection, matching PMGR result, GPC busy and clear paths,
preserved condition flags, identity output, and unseen markers. The `.S`
simulation substitutes user-mode register values, logging, and returns in
place of on-device resume branches. It is not a hardware or timing test.
On an ARM64 Mac, from this directory:

```sh
for scenario in hosttest unseen; do
  clang -arch arm64 -o "/tmp/j81-pollcompare-$scenario" j81-pollcompare-hosttest.S "j81-pollcompare-$scenario.c"
  "/tmp/j81-pollcompare-$scenario"
done
```

The capture can stall or reboot the iPad and may require a DFU recovery.
Its full device log archive can contain private information and is not
published in this repository.
