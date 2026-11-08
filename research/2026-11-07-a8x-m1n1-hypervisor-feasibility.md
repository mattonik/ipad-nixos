# A8X m1n1 hypervisor and MMIO tracing feasibility

## Conclusion

The pinned Hoolock m1n1 can boot Linux on the iPad Air 2, but its hypervisor/MMIO-tracing path cannot run on A8X/T7001: A8X does not implement EL2. This is a hardware boundary, not a missing build option. iPadOS 15.8 can be the installed firmware/boot source for the existing tethered PongoOS route; the available evidence does not support running that iPadOS installation as an m1n1 guest.

## Evidence

- The T7001 device tree says directly: `A8X doesn't actually have a hypervisor (EL2 is not implemented).` This comment is in mainline Linux's A8X SoC file, [`t7001.dtsi`](https://gbmc.googlesource.com/linux/+/f79749a8e42b3a6dcb980e87f3ef752962b9f094/arch/arm64/boot/dts/apple/t7001.dtsi#182). Hoolock's project page separately says A7–A11 devices lack the hypervisor used for dynamic tracing on Apple Silicon Macs ([HoolockLinux overview](https://github.com/HoolockLinux)).
- The checked-out project pins Hoolock m1n1 to `d5a10ac52a6468484854419a6c5130f1d62073eb` (`ipad-nixos/flake.nix:75-81`). Its source maps `MIDR_PART_T7001_TYPHOON` to the A7 feature set (`/nix/store/xxhxsyvhl2xgn9a72052ldqzqwd3864d-source/src/chickens.c:43-49,128-132`), which is useful for bootloader CPU handling but is not evidence of EL2 support.
- Hypervisor initialization is unconditional: `proxy.c` dispatches `P_HV_INIT` straight to `hv_init()` (`.../src/proxy.c:494-496`); `hv_init()` calls `hv_pt_init()`, then sets HCR including `HCR_E2H` and accesses `VBAR_EL12` (`.../src/hv.c:56-80`). `hv_pt_init()` writes `VTCR_EL2` and `VTTBR_EL2` (`.../src/hv_vm.c:119-142`). On a processor without EL2 these system-register accesses cannot establish stage-2 translation; this path has no `has_el2()` guard. The source does define `has_el2()` in `utils.h:364-367`, but the HV init path does not use it.
- The hypervisor tracer is genuine code, but depends on that guest stage-2 path: `hv_vm.c` encodes software MMIO trace descriptors and emits read/write events (`.../src/hv_vm.c:107-110,859-880,995-1001,1080-1083`). The Python `trace_all.py` example marks each `/arm-io` range traceable (`.../proxyclient/hv/trace_all.py:5-7`). The helper `run_guest.py` initializes the HV, loads a Mach-O or raw guest payload, and starts it (`.../proxyclient/tools/run_guest.py:55-59,103-116,134-139`). This is guest-access tracing, not a passive tracer for native iPadOS.
- Arm's architecture reference explains that VHE/HCR.E2H is an optional feature for Armv8.0 and identifies `ID_AA64MMFR1_EL1.VH` as its feature field ([Arm Architecture Reference Manual, Armv8.1 extensions](https://developer.arm.com/documentation/ddi0487/latest/)). This is a further compatibility concern because m1n1 forces E2H, but A8X's lack of EL2 is already conclusive and makes VHE moot.
- The project's Orchard-derived m1n1 patches only add A9–A11 device-data and touchscreen calibration forwarding (`ipad-nixos/docs/m1n1-from-source.md:15-24,39-52`); neither patch adds A8X EL2 or HV support. The documented/tested device path is checkm8/PongoOS `bootm` → m1n1 → Linux, with Linux boot verified on the iPad (`ipad-nixos/docs/software-only-control.md:232-270,314-322`). Hoolock's setup guide is explicitly a Linux/m1n1 boot guide; it describes PongoOS and iBoot methods and builds a Linux guest/payload, not an iPadOS guest ([SETUP.md](https://github.com/HoolockLinux/docs/blob/master/tutorials/SETUP.md)). Its supported iOS/iPadOS firmware range describes boot environments, not guest OS support ([Hoolock docs README](https://github.com/HoolockLinux/docs/blob/master/README.md)).

## What remains possible

EL1 software can still perform bounded direct register reads/writes or collect traces from instrumented code. That can observe selected events when the relevant driver cooperates or is patched, but cannot trap every native iPadOS MMIO access or provide the m1n1 hypervisor's PC/address/data trace. Such tracing would be a separate XNU/kernel instrumentation project and would need its own safety and perturbation limits.

## Safe offline verification

No device action is needed to settle feasibility: inspect the pinned T7001 device-tree source for the EL2 statement; inspect `hv_init()`/`hv_pt_init()` for unconditional EL2 register use; and inspect `trace_all.py`/`run_guest.py` to confirm the intended guest-only tracing flow. A build or QEMU run would not overturn the A8X EL2 hardware limitation. If future work considers EL1 instrumentation, scope it as a separate plan and first identify which iOS 15.8 code path can be instrumented; do not invoke `P_HV_INIT` on A8X.

## Tested versus unknown

- **Tested:** this repository's PongoOS → Hoolock m1n1 → Linux boot path on A8X and the pinned source build.
- **Present in source, not validated on A8X:** m1n1's generic MMIO event and trace-range mechanisms.
- **Source-established blocker:** T7001 has no EL2; the m1n1 HV path requires EL2 stage-2 registers.
- **Not tested and not claimed:** m1n1 hypervisor execution on A8X, iPadOS 15.8 as a guest, or any replacement EL1 tracer's coverage/performance. Given the hardware evidence, testing m1n1 HV on A8X is not a useful next step.
