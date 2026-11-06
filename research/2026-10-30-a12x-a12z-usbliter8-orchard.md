# A12X/A12Z, usbliter8 and OrchardLinux assessment

Date: 2026-10-30

## Bottom line

There is now a credible *research path* to Linux on the A12X iPad Pro, but
there is still no public, runnable A12X/A12Z boot chain.

The situation has improved since the September assessment in
`research/t7001-handoff-options.md`:

- `usbliter8` proves its SecureROM technique on A12/T8020 and A13/T8030, and
  explicitly says A12X/A12Z support is theoretically possible, but its source
  still has no T8027/CPID `0x8027` target.
- `l41ka` is a newer A12/A13 Pongo loader. It contains the beginnings of a
  T8027 target, including USB, DART and SRAM addresses, but the target returns
  immediately and is not dispatched. Its public README says T8027 support is
  in progress; neither the public branch nor the recently active forks
  complete it.
- `badapple` now demonstrates a substantial mainline-Linux stack on A12/T8020,
  including display, touch, USB, storage, SMP, cpufreq, Wi-Fi and Bluetooth.
  This is the closest Linux reference for an A12X/T8027 port, but it is not a
  drop-in A12X device tree or kernel.
- OrchardLinux's `hardware` repository is a software catalogue of device
  profiles and boot/runtime resources, not exploit hardware. Its current
  profiles use `checkm8-pongo` and cover A7-A10-era devices; it has no T8027,
  A12X, `usbliter8` or iPad8 profile. Orchard is useful as the eventual
  packaging/orchestration layer, not as the missing entry point.

The first go/no-go gate is therefore a stable T8027 SecureROM exploit. Until
that exists, kernel work and Orchard integration cannot be validated on the
device.

## Target identity

A12X and A12Z iPad Pros use the T8027 SecureROM target, CPID `0x8027`, and the
same listed SecureROM revision. This makes a shared exploit target plausible,
while board support remains model-specific.

Relevant 12.9-inch boards are:

| Generation | SoC | Models | Board IDs |
|---|---|---|---|
| iPad Pro 12.9-inch (3rd generation) | A12X | iPad8,5 through iPad8,8 | J320/J320x/J321/J321x |
| iPad Pro 12.9-inch (4th generation) | A12Z | iPad8,11 and iPad8,12 | J420/J421 |

The exact model and BDID should be captured from DFU before choosing a board
device tree. The exploit layer should be developed for T8027 first; the first
Linux board target should be only the device actually owned, rather than all
six boards.

Source: [The Apple Wiki SecureROM table](https://theapplewiki.com/wiki/SecureROM).

## usbliter8 audit

The original repository is no longer available at its old URL. The surviving
source mirrors agree on the current scope:

- supported targets are A12/T8020, A13/T8030 and S4/S5/T8006;
- A12X/A12Z support is described as theoretically possible but unimplemented;
- the exploit requires low-level malformed USB SETUP traffic, so it runs from
  an RP2350 board rather than a normal host USB stack;
- `exploit.c` dispatches only CPIDs `0x8020`, `0x8006` and `0x8030`;
- T8020 uses target-specific heap, SRAM, ROM, USB, ROP and shellcode offsets.

Adding `case 0x8027` is therefore not a port. T8027 needs its own SecureROM
analysis, memory layout, overwrite location, gadgets, USB controller setup,
payload offsets and cleanup path.

I also checked the changed `exploit.c` files in 27 modified forks from the
largest visible mirror network. None added T8027, CPID `0x8027`, A12X or A12Z
support.

Source: [JoshAtticus/usbliter8 mirror](https://github.com/JoshAtticus/usbliter8).

## RP2350 hardware

The simplest appropriate development board is the Waveshare RP2350-USB-A:

- RP2350A with a dedicated USB-A PIO port;
- USB full-speed host/device support;
- it is the reference board used by the public usbliter8 and l41ka work;
- Waveshare documents removal of R13 when USB host hot-plug is required. That
  modification also prevents using the PIO port as a USB device.

Because the iPad Pro is USB-C, the conservative physical setup is the USB-A
receptacle board and a known-good USB-A-to-USB-C data cable. This is an
engineering inference from the board interface and iPad connector, not a
demonstrated T8027 configuration. Avoid treating the stock usbliter8 UF2 as
A12X-capable: it can identify an unsupported DFU target, but it cannot pwn it.

Buying the board does not create T8027 support. It is justified only as an
inexpensive development platform for contributing to the missing target, or
after working T8027 firmware appears.

Sources: [Waveshare RP2350-USB-A product page](https://www.waveshare.com/product/rp2350-usb-a.htm),
[board wiki and R13 note](https://www.waveshare.com/wiki/RP2350-USB-A).

## l41ka: the best current exploit-side lead

`0cyn/l41ka` independently loads Pongo on A12 and A13 using an RP2350. Its
public T8027 scaffold is the strongest concrete sign of ongoing A12X/A12Z
work. It records:

- payload physical address `0x19c384000`;
- SRAM base `0x19c000000`;
- USB complex `0x25d000000` and DWC2 `0x25d100000`;
- DART base `0x25d028000` and stream mask `0xf`.

However, `T8027()` ends with `return 0` without preparing, writing or booting
the payload, and the public payload dispatcher handles only T8020 and T8030.
The device database knowing all iPad8 board IDs does not change that. Four
recently active forks checked on 2026-10-30 retain the same inert stub.

This is the most sensible project to watch or contribute T8027 work to. It is
not evidence that a private or nearly finished exploit exists, and the public
repository gives no delivery date.

Sources: [l41ka](https://github.com/0cyn/l41ka),
[public T8027 scaffold](https://github.com/0cyn/l41ka/blob/public/src/rom-patcher/iBootPatcherSetup.cpp),
[device database](https://github.com/0cyn/l41ka/blob/public/src/control/AppleDeviceDatabase.cpp).

## badapple: the closest Linux reference

`kieroid/badapple` is more relevant than Orchard for the post-exploit port.
It boots mainline Linux on an iPhone XS Max (A12/T8020) through:

1. usbliter8 SecureROM execution;
2. a patched iBSS;
3. device tree and trust cache loading;
4. m1n1 in place of the restore kernelcache;
5. a 16 KiB-page Linux kernel and initramfs.

Its kernel and m1n1 work cover many of the blocks T8027 will need: AIC, DART,
SART, ANS/NVMe, USB, display, touch, PCIe, Wi-Fi, thermals and cpufreq. A12X
shares the Vortex/Tempest generation, so this is a strong sibling reference,
but T8027 addresses, interrupt topology, CPU layout, ADT data and board
peripherals still need measurement and validation. A T8020 device tree must
not be booted unchanged on T8027.

Source: [kieroid/badapple](https://github.com/kieroid/badapple).

## OrchardLinux assessment

OrchardLinux is useful, but at the end of this path rather than the beginning.
Its current `hardware` tree consists of device manifests, patches and boot
resources. Every current manifest declares the `checkm8-pongo` method, with
CPIDs from A7 through A10-era targets. There is no iPad8/T8027 manifest and no
usbliter8 boot method.

The repository has already started absorbing this project's J81/Air 2 work,
which makes it a credible long-term home for a working A12X profile. It does
not supply any of the three missing foundations:

1. stable T8027 SecureROM execution;
2. a T8027-capable pre-boot/m1n1 chain;
3. a T8027 plus J320/J321/J420/J421 Linux platform port.

Only after a minimal kernel boots should Orchard gain a new usbliter8/l41ka
method, T8027 device manifests and the matching payload/kernel resources.

Sources: [OrchardLinux/hardware](https://github.com/OrchardLinux/hardware),
[current J81 manifest](https://github.com/OrchardLinux/hardware/blob/main/devices/j81/device.toml),
[J81 integration commit](https://github.com/OrchardLinux/hardware/commit/4bf26bac34b2270660ad71eb59c005266dd4f3d2).

## Recommended path and gates

### Gate 0: identify the owned board

Capture CPID, BDID, SRTG, product type and board config in normal/DFU mode.
Expected CPID is `0x8027`; the other values decide whether the first board
port is J320/J321 or J420/J421. This step is read-only.

### Gate 1: T8027 pwned DFU

Work upstream with l41ka or usbliter8 rather than creating a third exploit
fork. A pass requires repeatable code execution after cold DFU entries and a
reliable arbitrary read/write/execute primitive or equivalent pwned-DFU
state. A device merely being identified by USB is not a pass.

Stop here if that primitive cannot be made stable. No Orchard or kernel work
can compensate for this gate.

### Gate 2: minimal pre-boot execution

Use the proven badapple structure as the primary reference: patched iBSS to
m1n1, initially with no storage writes. A pass is a repeatable serial or USB
console from a small known payload with the correct T8027 memory and DART
setup.

### Gate 3: minimal T8027 Linux

Port only the owned board. Bring up one CPU, RAM, interrupt controller, timer,
USB console and a RAM-only initramfs first. Add SMP, cpufreq, display, storage,
touch, Wi-Fi and charging one subsystem at a time, reusing badapple drivers
only where the hardware and ADT evidence agree.

Keep internal NVMe read-only until the IOMMU, storage and shutdown paths are
repeatably stable. Do not modify SEP, restore, activation or Face ID data.

### Gate 4: Orchard integration

Once the same minimal kernel can be booted manually on repeated cold starts,
add an Orchard T8027 profile and boot method. Orchard then becomes valuable
for reproducible artifact selection, installation and user-facing workflow.

## Decision

Proceed only as an exploit and platform-port research project, not as a
short-term way to install Omarchy on the iPad.

The smallest sensible investment is one RP2350-USB-A board and a data-capable
USB-A-to-C cable, but purchasing even that can wait until someone is ready to
work on Gate 1. The highest-value next action is to coordinate with l41ka's
author around the public T8027 scaffold. Do not fork Orchard first.

Compared with September, the outlook has moved from "no practical path" to
"a credible but difficult path with two unproven gates": T8027 SecureROM
execution and a T8027 Linux/board port. Neither is publicly complete today.

## Rejected leads

Two repositories found during the search were not treated as evidence:

- `failbr34k/USBurst` identifies A12Z with the wrong CPID, calls the target
  controller DWC3 while the relevant public work uses DWC2, and labels x86-64
  bytes as ARM64 shellcode. It is not a demonstrated exploit.
- `Cyber-Scholar/usbliter8` is an iBoot patchfinder, not a SecureROM entry
  exploit. Its A12X/A12Z claims do not provide pwned DFU and have no published
  device validation artifacts.

These may contain ideas worth independently checking, but they do not change
any gate above.
