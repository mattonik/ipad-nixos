# J81 soc-tvm requests bit 0 at 0x20e02d000

On the ordinary 19H394 startup path with the J81 property value of 1, ApplePMGR reads a **32-bit** SoC TVM control word at PMGR region 0 +0x2d000 and requests `old | 1` at that same address. It immediately returns on the enable branch. The startup request does not establish the old word, readback, or a change of bit on a particular boot. MiscACG at +0x32000 has a different descriptor.

## How the address and operation were resolved

Instruction addresses below omit the common 0xfffffff000000000 base.

1. Descriptor index 3 names `soc-tvm`. The J81 PMGR property contains little-endian 1. After the lookup, 6bb951c can override the saved four-byte value. Its stub at 6bed620 loads the pointer at 6fcd668 to 7788510, named `_PE_parse_boot_argn` in this kernel. The valid byte and the object flag at +0xe4 gate the later dispatch; the effective value is converted to Boolean. Thus the property establishes the default request. The return packet does not include a trace of this setter on the successful core boot.
2. The index-3 jump target 6bccd7c passes rail 1, the Boolean value, 1 and 0 through instance slot +0x6a8. The T7001 slot resolves to 6c88df0. For nonzero rail it forwards through the explicit parent vtable pointer and offset +0x6b8 to 6bcf590. Rail 1 takes 6bcf658. Rail 0 takes a different CPU path. The kernel diagnostic names the method `ApplePMGR::enableTVM` and the rail-1 assertion names `kRegGroupSOCTVM`.
3. At 6c88510..520 the subclass registers group 3, selector 0, offset 0x2d000. Group 3's valid byte is at object +0x2358 and its offset word at +0x2360. The rail-1 method checks validity before using the descriptor. The ordinary read at 6bcf674, mask and OR at 6bcf678..67c, and write at 6bcf68c all address the same word, instance 0. Region 0 translates to physical 0x20e000000.
4. Enable skips the entire polling tail at 6bcf690. Disable requests `old & ~1`; with the wait argument set it then calls the masked poll at offset +0x2d100 with mask 2 and expected value 0. A zero at +0x2d100 is therefore not an enable acknowledgement. The earlier 12B410 quiesce analysis independently identified the clear-and-wait sequence on shutdown. [Historical shutdown path](2026-11-09-j81-pongo-m1n1-pre-linux-writes.md)

## What the stalled boots establish

The archived November 11 Linux post-GPC1 `volman.log` contains +0x2d000 = 0 and +0x2d100 = 0. Its MiscACG word was also zero; sibling `plls.log` had page-5 +4 clear. This is evidence that Linux can reach GPC state 1 with the TVM control clear in that recipe. The newer Linux core-stall snapshots cover seven offsets and omit both TVM words. The successful iPadOS recipe's five markers omit them too. Neither the historical Linux zero nor the static iPadOS enable can fill those later runtime observations.

An unenabled SoC TVM path remains a candidate for the core aperture to stall after page 5 rises. The trace gives no direct operation on the core aperture, a GPU reset, or page 5, and provides no transaction-level link between TVM and the stalled CPU load. The matching GFX VID word is a digital request and does not measure delivered rail voltage. If the core-stall boot already had bit 0 set, a missing retained enable cannot explain that stall. If a working iPadOS boot has it clear at the corresponding point, a retained 1 there is unnecessary for that successful read. A stock 1 and Linux 0 at comparable phases would prioritize the difference without establishing causality. [Page-5-high hardware outcomes](2026-11-19-j81-page5-high-core-stall.md)

## Verification

The [stock startup audit](../tools/audit_j81_pmgr_start.py) checks the exact kernel and ADT digests, dispatch targets, descriptor registration, rail branch, bit operations and physical translation. On an ARM64 Mac the original two arithmetic instruction words also matched the 32-bit enable and disable expressions on 65,536 distinct input words each. This exercises the calculation in host registers. The actual control/status values on the two target operating systems remain the next measurement.
