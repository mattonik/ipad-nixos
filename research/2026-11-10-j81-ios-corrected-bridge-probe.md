# J81 corrected iOS bridge recording probe

> Hardware result: the 66 captured requests match Linux test4's checkpoint
> sequence; see the [capture comparison](2026-11-10-j81-ios-corrected-bridge-result.md).

Prepared 2026-11-10 following the [dispatcher capture and filter correction](2026-11-10-j81-ios-dispatch-capture-result.md).
The module has not been run on the iPad.

The previous hook counted 93 calls but mistakenly filtered its detailed
records on the assumption that argument `w4` represented requested state.
It is an instance index. This build records calls for selectors 9 and 10
regardless of the instance, and records the actual instance alongside each
offset and value. It retains the dispatcher probe's comparison and mode
fields and all-writer count. It adds no GPU or PMGR MMIO access. A positive
writer-hook count in the previous boot does not guarantee that the same
path or all records will appear in a subsequent boot.

Records appear as `09/iiiiiiii:oooooooo=vvvvvvvv;`, with selector, instance,
offset and value in hexadecimal. A maximum of 96 records is retained, in
reservation order, from after KPF installation through the first GFX clock
provider return; the records are global and may include concurrent or
unrelated calls. `B1` indicates overflow; `?` indicates an unready record.
Neither a recorded dispatch nor its order proves the corresponding MMIO
write completed. The `W` count applies to all selectors and instances during
the provider call, not the preceding recording window. See the earlier
[dispatcher probe notes](2026-11-10-j81-ios-dispatch-probe.md) for `D`,
`A`, `N`, `L`, `X`, and `M`.

Compare the observed instance and sequence against the actual 19H394
tables and the Linux attempt. A mismatch is evidence for further analysis,
not a safe prescription to write those values or access the GPU core.

## Build and checks

Module: `artifacts/live/private/j81-ios-records-probe/checkra1n-kpf-pongo-j81-records`

SHA-256: `48dfbe8bc4cc1c2ca52bb8187f6e2a942b7105e698bc80eb83af9d0412a85fcb`.
Kernel UUID and exact signatures gate all six hooks together. The KPF host
harness accepted the target 19H394 kernel and refused each independently
missing or duplicated signature and a wrong UUID. Native ARM64 host tests
exercised instance 0, instance 4 and instance 15 records, all-writer
counting, three-record log batches, and the 96-entry overflow indication.
The private artifact directory also contains the corresponding source,
registration and host test inputs. The device build completed without
compiler warnings. Host execution simulates the XNU hooks and logger and
does not prove timing or safety on hardware.

## Boot command

After a fresh DFU and checksum verification:

```sh
cd /path/to/ipad-nixos
printf '%s  %s\n' 48dfbe8bc4cc1c2ca52bb8187f6e2a942b7105e698bc80eb83af9d0412a85fcb artifacts/live/private/j81-ios-records-probe/checkra1n-kpf-pongo-j81-records | shasum -a 256 -c - && sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-records-probe/checkra1n-kpf-pongo-j81-records --debug-logging
```

As before, if palera1n remains at “Booting PongoOS” while PongoOS is visible,
stop it and rerun. Once iPadOS boots, unlock the iPad and collect the startup
log privately. A stall or reboot is possible and may require another DFU
cycle. Full device log archives may contain personal information.
