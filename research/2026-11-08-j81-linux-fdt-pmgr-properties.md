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
