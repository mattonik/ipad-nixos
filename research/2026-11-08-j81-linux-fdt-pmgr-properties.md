# J81 Linux FDT PMGR property check

Read-only inspection of the effective Linux device tree on the already-used
J81 boot. No PMGR/GPU MMIO was read or written. The check searched the full
`/sys/firmware/devicetree/base` tree for Apple bridge and state-config property
names and inspected the PMGR subtree at
`/proc/device-tree/soc/power-management@20e000000`.

The PMGR node contains its address/size cell declarations, compatible/name,
phandle, `reg`, boot-phase, and U-Boot properties, plus power-controller
children. It does not contain `bridge-settings-version`,
`bridge-settings-9`, `bridge-settings-10`, `bridge-reg-index`, `#bridges`, or
`state-config`; none of these names appeared anywhere in the exported Linux
tree. The `mcc` child at
`/proc/device-tree/soc/power-management@20e000000/power-controller@20230`
has `reg = <0x00020230 0x4>` and `apple,always-on`.

This is the effective FDT Linux received, not a raw Apple ADT dump. It can
show which properties survived into this Linux boot tree; their absence here
does not show they are absent from Apple's ADT. It cannot establish
ApplePMGR's runtime format field, `state-config`-derived records, whether
`bcc56c` ran or had a record for GFX, or the callback's runtime target/effects.
`bcc56c` is an iOS ApplePMGR timing-accounting helper, and this check involved
no hardware register access.

## 2026-11-09 current-boot follow-up

On the connected Linux boot, a read-only sysfs check found `ps_gfx` pointing
to the PMGR power-controller at `+0x20320`. The only `opp-table` found by
name is labelled `typhoon_opp`; all three CPU nodes reference its phandle.
It is therefore the CPU table, not evidence of a GPU performance table. A
name search for `sgx`, `gpu`, `opp`, and `perf-states` found no GPU node or
GPU performance-state property; it did find the experimental GPU power-domain
guard. This is a search of Linux's effective FDT, not the original Apple ADT.

The effective FDT was saved privately as
`artifacts/live/private/j81-fdt-20261109-current.dtb` (34,055 bytes,
SHA-256 `ba60bdadb61a65637b55c5af9babe693cc545d381715ba27d26c8e2c59ac0800`).
The boot ID was `854d825f-c3b0-4a91-97bd-24999ad4f7ac`, and the kernel
reported `7.3.0-rc1 #1-NixOS`. At the check, `gpu_pmgr_once` was loaded and
its device reported runtime status `active` with usage count 1. These are
software states; they do not show which GPU clock is selected or that GPU
registers respond. No MMIO reads or writes were performed in this follow-up.
