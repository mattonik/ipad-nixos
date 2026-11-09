# J81 A8X and upstream PowerVR: pre-ID comparison

Date: 2026-11-09. Offline comparison, no hardware access. Upstream Linux
PowerVR files checked against commit `7475ea8b58616b33c04afb976cf0fbaad9dd63fb`.
The relevant upstream routines are
[`pvr_device_init()` and `pvr_gpuid_decode_reg()`](https://github.com/torvalds/linux/blob/7475ea8b58616b33c04afb976cf0fbaad9dd63fb/drivers/gpu/drm/imagination/pvr_device.c),
[power sequencing](https://github.com/torvalds/linux/blob/7475ea8b58616b33c04afb976cf0fbaad9dd63fb/drivers/gpu/drm/imagination/pvr_power.c),
[firmware start](https://github.com/torvalds/linux/blob/7475ea8b58616b33c04afb976cf0fbaad9dd63fb/drivers/gpu/drm/imagination/pvr_fw_startstop.c), and
[register definitions](https://github.com/torvalds/linux/blob/7475ea8b58616b33c04afb976cf0fbaad9dd63fb/drivers/gpu/drm/imagination/pvr_rogue_cr_defs.h).
The comparison is about source order, not a claim that upstream supports
Apple's GXA6850 or that its platform implementation is the same.

## What runs before identity

The generic upstream manual-power path obtains a required core clock,
optional system and memory clocks, and an optional external reset control.
Runtime resume enables the clocks, delays 1 µs, and deasserts that optional
reset before the device initializer maps registers and requests the GPU ID.
Another supported platform delegates power to its own power sequencer. The
platform-compatible string chooses the power implementation. These are
platform operations, not writes to Rogue's internal soft-reset register.

Upstream first reads 64 bits at Rogue `+0x20` as `CORE_ID__PBVNC`. If the
branch field is zero it falls back to 32-bit `CORE_REVISION` at `+0x20`,
then 32-bit `CORE_ID` at `+0x18`. Apple's iOS 8.1 and 15 G4G paths use
32-bit reads at `+0x20` then `+0x18`; test4 stalled on its first 32-bit
read at `0x201000020`. The upstream names and offsets independently
corroborate that this is a plausible Rogue identity-register location, not
that the access is valid or safe on the A8X in its present state. Upstream's
initial 64-bit access is a different operation; it is not a reason to retry
with a different width.

Upstream performs the internal Rogue soft-reset sequence at `+0x100` in
`pvr_fw_start()`, after GPU identity and firmware selection/initialization.
Apple's traced G4G probe also reads identity before the later firmware path.
Thus the upstream source does not support the theory that issuing this
internal soft reset or booting firmware is an established prerequisite to
making J81's first ID read respond. Do not replay it on this basis.

## Concrete difference and limitation

Test4 obtained the J81 PMGR power-domain reference, issued the captured
selector 9/10 table sequence, and initialized GPC. It did not call the
upstream generic PowerVR driver's `clk_prepare_enable()` or optional
`reset_control_deassert()` path, and it did not call Apple's provider code.
That comparison identifies platform integration as a remaining question,
not proof of a missing external reset or clock on J81. Apple's traced
clock/power provider callbacks are SoC-specific; no mapping from upstream's
optional reset or its `core`/`sys`/`mem` clocks to a distinct A8X control
has been established.

The test4 PMGR read was `0x3ff`, with bit 31 (the Linux PMGR reset bit)
clear. That rules out the **observed PMGR word reporting reset asserted** at
that checkpoint; it does not prove that another reset, clock, or fabric gate
is correctly configured. Generic Linux PMGR state changes do not themselves
identify Apple's full provider callback or whether all bridge entries took
effect. See [test4 readback boundary](2026-11-07-j81-test4-raw-readback-boundary.md).

## Support and next step

[Mesa's PowerVR status](https://docs.mesa3d.org/drivers/powervr.html) lists
GX6250 revision `4.40.2.51` as partially supported and a different GX6250
revision plus GX6650 as unsupported. It does not list GXA6850; product family
is not sufficient to prove BVNC, firmware or ABI compatibility. The upstream
Linux driver's existence is useful reference material, not a turnkey J81
bring-up.

A bounded check of the J81 gate and reset properties follows. It found no
independent external-reset mapping. No new MMIO read or write is justified
by this comparison alone.

### Bounded J81 reset-property check

The local decoded 8.1 J81 `sgx` node lists `clock-gates = [124]` and
`power-gates = [124]`; a search of that node's property names found no
property containing `reset`. Its two `reg` windows are the GPU core and
GPC windows used above. The iOS 15 pre-ID trace identifies the same two
provider calls, but the absence of a reset-named property in this one 8.1
ADT node cannot exclude a reset implemented indirectly by the provider,
a firmware side effect, or a reset property elsewhere. The observed PMGR
reset bit was already clear at test4's checkpoint. This check yields no
independent J81 external-reset operation to add to a probe.
