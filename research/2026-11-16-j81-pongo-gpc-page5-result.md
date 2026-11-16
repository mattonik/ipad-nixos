# J81 bare PongoOS GPC/page-5 comparison

## Result

The operator photo `IMG_4995.heic` records a completed bare-PongoOS,
no-RGX-core run. The visible final transcript includes the known GPC stores:

```text
poke 201e10000 ffff0000
poke 201e00000 40000000
poke 201e01000 11
```

It then shows the GPC request changing from busy (`0x11`) to state `1`, and
the following readbacks:

```text
20e005004 = 00000000   # three direct samples
20e01c200 = 80110100
20e02300c = 00000000
201e00000 = 40000000
```

The return to the `pongoOS>` prompt shows this no-core sequence completed;
there was no observed GPU-core register access.

## Meaning

This duplicates the relevant negative Linux observation in a bare PongoOS
environment: the recovered PMGR/bridge/GPC stores can produce GPC state `1`
while page-5 bit 30 remains clear. The contrast with iPadOS's post-poll
`0x40000000` result is therefore not explained solely by Linux userspace,
the Linux PMGR driver, or the Linux-to-device handoff.

The remaining candidate is the higher-level Apple GFX clock-action ownership
path and its dependencies (tracked device-clock reference, provider busy/tuner
action, or another prerequisite it establishes), rather than another replay
of the three GPC words. This still does not establish that bit 30 is a
GPU-ready control or justify writing it.
