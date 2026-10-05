# T7000/J81 PCIe MSI domain: design

Date: 2026-10-05. **Design only: nothing here is built, booted or written to the device.**
It turns the research agent's contract
([`2026-10-05-t7000-pcie-msi-domain-research.md`](2026-10-05-t7000-pcie-msi-domain-research.md))
into a reviewable architecture with a no-hardware acceptance matrix and a staged hardware plan.
Labels: **E** observed/read in code or on the device, **I** inference, **U** unknown.
Source tree read: the `0053`-applied kernel source (`pcie-apple.c`, `irq-apple-aic.c`,
`probe.c`, `pci-host-common.c`); the iPad5,3 iOS 8.1 kernelcache (`AppleEmbeddedPCIE`).

## 1. Why this is needed (E)

`brcmfmac` calls `pci_enable_msi()` and then requests `pdev->irq`, ignoring the enable result
(`pcie.c:977-978`). `pci_host_common_init()` sets `bridge->msi_domain = true`
(`pci-host-common.c:235`); with no domain and no `msi-map`, `probe.c` marks the bus
`PCI_BUS_FLAGS_NO_MSI`, so `pci_enable_msi()` fails and the IRQ request then fails. A domain
that exists **before** `pci_host_probe()` is therefore mandatory. The BCM4350 exposes a plain
MSI capability (no MSI-X): control word `0x0088` (64-bit capable, up to 16 messages, no
per-vector masking), so one 64-bit MSI vector with parent-level masking is enough.

## 2. New evidence gathered for this design

| # | Finding | Evidence |
| --- | --- | --- |
| 1 | **J81's AIC reports `256/1024 IRQs`.** The 32-vector MSI range 224..255 ends exactly at the last valid line (AIC translate rejects `irq >= nr_irq`). The port interrupts 212/215/218/221 sit just below it. | read from the running tablet's boot log; `irq-apple-aic.c:707` |
| 2 | **iOS's MSI-config encoding is the M1 `PORT_MSICFG` encoding.** `FUN_ffffff8002befa14` writes `+0x124` = `0x00`/`0x01`/`0x11`/`0x21`/`0x31`/`0x41`/`0x51` for 0/1/2/4/8/16/32 vectors = `EN | log2(n) << 4`, and `+0x128 = base \| base << 16`. The in-tree M1 driver uses `PORT_MSICFG 0x124` (`EN`, `L2MSINUM << 4`) and `PORT_MSIBASE 0x128` (`<< 16` for the second half). J81's recovered `0x31` / `0x00080008` are exactly these for 8 vectors, base 8. | iOS decompile (this session); `pcie-apple.c:81-85,425-443` |
| 3 | **iOS never programs the doorbell register `+0x168`** (the M1 `PORT_MSIADDR`). No store to offset `0x168` exists in the PCIe kext; the one literal `0x168` hit is an unrelated vtable thunk. So on J81 the doorbell is hardware-fixed or defaulted to the ADT `msi-address` (`0xbffff000`). | immediate search over the kext |
| 4 | **iOS builds its own MSI controller as a child of the AIC.** `AppleEmbeddedPCIE::start` reads `msi-address`, `msi-crypto-address`, `#msi-vectors` (32), `msi-vector-offset` (224) and `msi-parent-controller`, resolves the AIC's `InterruptControllerName`, and initialises a child controller with (vector count, offset, parent). That is a plain **hierarchical** vector map: vector `v` is parent line `224 + v`. No chained handler is implied. | iOS decompile |
| 5 | **J81's tail unmasks exactly the M1 "interesting" port events.** The mask `+0x104 = 0xff70afff` clears bits 12, 14, 16, 17, 18, 19, 23. In the M1 map: 12 `LINK_UP`, 14 `LINK_DOWN`, 17 `REQADDR_GT32`, 18 `MSI_ERR`, 19 `MSI_BAD_DATA`, 23 `CPL_TIMEOUT` (bit 16 is not in the M1 header). `+0x100` is the status register (`PORT_INTSTAT`). | recovered writes + `pcie-apple.c:61-79` |
| 6 | `aic_irq_set_type` accepts both `LEVEL_HIGH` and `EDGE_RISING` ("MSIs implicitly have edge semantics"). | `irq-apple-aic.c:465-472` |
| 7 | The DART reserved region now follows the controller's `apple,msi-doorbell` (patch `0055`, hardware-confirmed). | earlier result |

Findings 2 and 3 together mean the register block is the M1 block on J81; the *only* thing the
M1 driver does that iOS 8.1 does not is write `+0x168`. We therefore do **not** write it
(a guessed write is out of bounds); see U2 for how to look at it read-only.

## 3. Architecture

```text
 BCM4350 (MSI cap @0x58, 1 vector)
      | memory write: address 0xbffff000, data = global slot (8..15)
      v
 T7000 controller (port 1: +0x124 = 0x31, +0x128 = 0x00080008, already programmed by 0053/0054)
      | asserts one of the 32 MSI lines
      v
 AIC (aic,1, 256 IRQs)  hwirq 224 + slot          <- parent domain, DOMAIN_BUS_WIRED
      ^
 T7000 MSI parent domain (linear, 32 slots, only 8..15 allocatable)   <- new, owned by the PCIe node
      ^  created with msi_create_parent_irq_domain(); fwnode = the PCIe controller node
 per-device PCI-MSI domain (msi_lib_init_dev_msi_info)                 <- created by the core
      ^
 pci_alloc_irq_vectors / pci_enable_msi in the endpoint driver
```

No chained handler and no register access is needed for delivery: the domain only allocates a
slot, programs the parent line through the AIC, and composes the message. This is the same
structure as the in-tree M1 driver (`apple_msi_*`, `pcie-apple.c:218-282, 669-722`); the
differences below are what make it J81-specific.

### 3.1 J81-specific rules

1. **Global numbering, restricted window.** The domain has 32 hardware-vector slots but only
   **slots 8..15** may be allocated (port 1's slice). Slots 0..7 and 16..31 are pre-reserved in
   the bitmap. Shrinking the domain to 8 and composing data `0..7` would silently contradict
   the already-programmed `+0x128` base of 8.
2. **Message.** Address `0x0000_0000_bffff000`, data = the global slot. The address comes
   from the same DT property the DART uses, `apple,msi-doorbell`, so the two can never disagree.
3. **Parent mapping.** Parent fwspec `<AIC_IRQ 224 IRQ_TYPE_EDGE_RISING>` with the number
   incremented by the slot (`param[param_count - 2] += hwirq`, as in `apple_msi_domain_alloc`).
   Slot 8 -> AIC 232 ... slot 15 -> AIC 239; all below `nr_irq = 256`.
4. **One source of truth for port constants.** The current driver hard-codes `0x31` and
   `0x00080008`. The domain needs the same facts (base 8, count 8). Define
   `T7000_PCIE_MSI_PORT_BASE = 8` and `T7000_PCIE_MSI_PORT_COUNT = 8` once and *derive* the two
   register values (`EN | ilog2(count) << 4`, `base | base << 16`). The write-sequence harness
   (`kernel/test_pcie_write_sequence.py`) proves the derived values equal today's constants.
5. **Flags.** Copy `apple_msi_parent_ops` (`MSI_FLAG_USE_DEF_DOM_OPS`, `USE_DEF_CHIP_OPS`,
   `PCI_MSI_MASK_PARENT`, `CHIP_FLAG_SET_EOI`, `bus_select_token = DOMAIN_BUS_PCI_MSI`). The BCM4350
   has no per-vector masking, so parent-level masking is required. Advertise plain PCI MSI;
   do not advertise MSI-X. `MULTI_PCI_MSI` can be allowed (power-of-two blocks inside 8..15)
   but the first feature needs one vector; start without it and add it only with a reason.
6. **Port scope stays J81 port 1.** No claim about ports 2-4.

### 3.2 DT contract (one atomic change, with the domain)

On the PCIe node (`t7001-air2.dtsi`, J81 only; not generic `t7001.dtsi`):

```dts
msi-controller;
msi-parent = <&pcie>;
msi-ranges = <&aic AIC_IRQ 224 IRQ_TYPE_EDGE_RISING 32>;
/* apple,msi-doorbell = <0x0 0xbffff000>;   already present (0055) */
```

plus the binding document update. These must not land without the domain.

### 3.3 Probe ordering and lifetime

```text
apple_t7000_pcie_probe():
  1. REG_ON assert (existing)                     <- board gate
  2. devm_pci_alloc_host_bridge(), parse ports    <- existing
  3. t7000_msi_init():  parse msi-ranges, find the AIC wired domain with
        irq_find_matching_fwspec(..., DOMAIN_BUS_WIRED)  (-EPROBE_DEFER if absent),
        build the bitmap (only 8..15 free), msi_create_parent_irq_domain()
        register the teardown with devm_add_action_or_reset()   <- NEW
  4. pci_host_common_init()   <- enumerates; the bus inherits the MSI domain
```

The domain must exist **before** step 4: after enumeration the bus already carries
`PCI_BUS_FLAGS_NO_MSI`, and that cannot be repaired. Failure at step 3 fails the probe cleanly
(REG_ON stays asserted, as already documented).

## 4. Pure logic to isolate for host testing

Keep the policy in small functions with no kernel types beyond integers:

| Function | Contract |
| --- | --- |
| `t7000_msi_slot_alloc(bitmap, nr_irqs)` | returns a slot in 8..15 aligned to `order_base_2(nr_irqs)`, or `-ENOSPC`; never returns 0..7 or 16..31 |
| `t7000_msi_slot_free(bitmap, slot, nr_irqs)` | returns the block; double-free is detected |
| `t7000_msi_parent_hwirq(slot)` | `224 + slot` for slots 8..15 |
| `t7000_msi_compose(doorbell, slot, &msg)` | `address = doorbell`, `data = slot`; no other field |
| `t7000_pcie_msi_cfg()` / `_base()` | the register values derived from base and count |

## 5. No-hardware acceptance matrix

| # | Check | How |
| --- | --- | --- |
| A1 | allocation is confined to 8..15, aligned, exhausts at 8 single vectors, frees correctly | host unit test compiled from the real functions (extend `kernel/pcie_trace` with the small irq-domain stubs) |
| A2 | compose gives `0xbffff000` / slot; parent hwirq `224 + slot` | same |
| A3 | the derived `+0x124` / `+0x128` values are bit-identical to `0x31` / `0x00080008`, and the **whole write/read/delay trace is unchanged** | `kernel/test_pcie_write_sequence.py` against the golden `0053` trace |
| A4 | the MSI code performs **no controller write**: no `+0x168`, no `+0x100`/`+0x104` change, no new PMU or GPIO action | trace harness invariants (the harness already asserts no write to `+0x88`/`+0x8c`) plus a text check |
| A5 | the domain is created before `pci_host_common_init()` in probe | source-order test |
| A6 | DT properties and the domain land in one patch; the DT carries all three MSI properties and `apple,msi-doorbell` | patch-text test |
| A7 | zero-fuzz apply on the `0055` tree, kernel builds, `BRCMFMAC_PCIE` stays off | build + verifier |
| A8 | the compiled DTB has the properties; the kernel image has the new strings | verifier mode |

## 6. Hardware plan (each step is a separate explicit approval)

The first real MSI will come from `brcmfmac` after firmware boot, which is gated on private
evidence. To avoid waiting on that, validate the plumbing earlier, in increasing risk:

- **H0, read-only (already possible after the DT change):** boot and confirm the domain
  registers (`/sys/kernel/debug/irq/domains`), `lspci`/config space unchanged, link and
  enumeration identical to the `0055` payload. No device interaction.
- **H1, allocation self-test (writes to the endpoint's MSI *capability* only):** a built-in
  test driver, in the test kernel only and never in a default payload, binds to `14e4:43a3`
  and calls `pci_alloc_irq_vectors(..., 1, 1, PCI_IRQ_MSI)`. It then checks that the virq's
  parent chain is AIC `232`, **reads back the endpoint's MSI address/data registers** (expect
  `0xbffff000` / `8` at capability `+0x58`), and frees the vector. This exercises
  alloc, compose and free end to end without any endpoint-originated interrupt. It writes
  the endpoint's MSI capability and, because binding a driver enables the device, its command
  register. That is a config-space write to the endpoint, which the standing rules treat as a
  new category (the rules forbid OTP/NVRAM and firmware access, not this), so it needs the
  user's explicit approval and a recorded session.
- **H2, delivery:** only with `brcmfmac`, firmware and NVRAM (private-capture gated). Out of
  scope here.

## 7. Unknowns and risks

| # | Item | Plan |
| --- | --- | --- |
| U1 | **Does J81's DART pass an endpoint write to `0xbffff000` through, or translate it?** The M1 comment says the doorbell must be excluded from the IOVA range (done by `0055`); whether it is also untranslated on this DART is unknown. | needs a real MSI (H2), or DART register inspection (separate study) |
| U2 | **The hardware default of `+0x168`.** iOS never writes it (finding 3). A read-only debug dump after init would show whether it already holds `0xbffff000`. | optional `dev_dbg` read in a diagnostic variant; hardware approval |
| U3 | Whether the 32 MSI lines are level or edge at the AIC. AIC accepts both; the M1 convention is `EDGE_RISING`. | keep `EDGE_RISING`; confirm during H2 |
| U4 | Port-event interrupts (`AIC 212/215/218/221`): unmasked in hardware (finding 5) but no Linux handler. A handler that logs `MSI_ERR`/`MSI_BAD_DATA` would help diagnose the first MSI test but requires a W1C write to `+0x100`. | optional phase 2, gated like H1 |
| U5 | No suspend, hot-reset or link-down handling; domain lifetime vs unbind. | stated limits, as for `REG_ON` |
| U6 | `msi-crypto-address` (second ADT doorbell) has no known use here. | ignore; note only |

## 8. Proposed patch series (not started)

| Patch | Content | Gate |
| --- | --- | --- |
| `0056` | derive the `+0x124`/`+0x128` values from the port base/count constants; behaviour-neutral | A3 trace identical; compile |
| `0057` | the MSI parent domain (section 3), `msi-controller`/`msi-parent`/`msi-ranges` in `t7001-air2.dtsi`, binding update. One atomic change. | A1-A8 |
| `0058` | the H1 self-test driver, **test kernel variant only** | review; explicit hardware approval |

## 9. Decisions (resolved by the user, 2026-10-05)

1. **One vector.** The first domain does not advertise `MSI_FLAG_MULTI_PCI_MSI` and has no
   block allocation beyond a single slot. `brcmfmac` asks for exactly one vector, and
   multi-vector would rest on the unobserved low-bit routing assumption (hardware has never
   delivered a J81 MSI). Revisit only after one vector has been seen to work.
2. **H1 self-test concept approved.** The allocation self-test (config writes to the
   endpoint's MSI capability and command register, test kernel only) is approved as a concept.
   Each hardware run of it still gets its own go-ahead at run time and a recorded session.
3. **The read-only `+0x168` dump is included** in a diagnostic variant (U2): a `dev_dbg`-level
   read of the port's MSI address register after the existing init, so the hardware default can
   be compared with `0xbffff000` without writing anything.

Series state: `0056` (derive the register values from base/count) is implemented, host-verified
(zero-fuzz apply, real driver compiled in the trace harness with the new `static_assert`s, trace
identical to golden) and built as `m1n1-hoolock-pcie-j81-msi`. `0057` (the domain, atomic with
the DT) and `0058` (H1 self-test driver, test variant only) follow.

## 10. `0057` implemented and host-verified (2026-10-05)

`kernel/patches/0057-pcie-apple-t7000-msi-domain.patch` applies with zero fuzz on top of `0056`
and changes five files atomically (driver, Kconfig, `t7001.dtsi` comment, `t7001-air2.dtsi`,
binding): the DT's `msi-controller`/`msi-parent`/`msi-ranges` exist only together with the
domain that serves them.

What it implements, matching sections 3-5:

- a parent domain created with `msi_create_parent_irq_domain()` on the AIC (found by
  `irq_find_matching_fwspec(..., DOMAIN_BUS_WIRED)`; the probe returns `-EPROBE_DEFER` if the AIC
  is not up yet), created **before** `pci_host_common_init()` so the root bus inherits it;
- one 32-bit slot bitmap with all slots reserved except the port's window 8..15; every
  allocation takes exactly one slot, `nr_irqs != 1` is refused (`-EINVAL`);
- message = (`apple,msi-doorbell`, slot number); AIC line = 224 + slot; the slot is returned if
  the parent allocation fails or when the vector is freed;
- `supported_flags = MSI_GENERIC_FLAGS_MASK` only: no `MSI_FLAG_MULTI_PCI_MSI`, no MSI-X;
  `MSI_CHIP_FLAG_SET_EOI` because the AIC child needs the EOI chained;
- no register is written for MSI (the doorbell `+0x168` stays hardware-default) and the unchanged
  PCIe write sequence is byte-identical to the `0053` golden trace.

Evidence (all host-side, no hardware):

| Check | Result |
| --- | --- |
| zero-fuzz apply on the `0056` tree | pass |
| default trace (MSI not declared) vs `golden-0053.trace` | identical |
| `kernel/test_pcie_msi_domain.py` (250-line golden `golden-msi.trace`) | pass: ordering REG_ON -> parent lookup -> domain -> host init; 8 allocations take slots 8..15 on AIC 232..239, the 9th returns `-ENOSPC`; compose = `0x00000000_bffff000` / data 11; free + re-alloc; two-vector request refused; parent failure returns the slot; no-AIC defers; wrong vector count and missing doorbell fail without leaving a domain |
| nine one-line mutations of the driver (window at slot 0, wrong doorbell, local-index data, parent line ignoring the slot, multi-vector allowed, slot leak on parent failure, domain after host init, multi-MSI flag, doorbell register write) | all caught |

Not proven by the host harness: that the real `msi_create_parent_irq_domain`/`msi_lib` accept
these flags (the build of `m1n1-hoolock-pcie-j81-msi` is the compile gate), that a J81 device's
write reaches the AIC through the DART, and edge-vs-level behaviour (U2, U3). Those are the H0/H1
hardware gates and still need the user's go-ahead.

Next: `0058` (H1 self-test, test kernel only) and the read-only `+0x168` dump diagnostic.

### 10.1 Build result (2026-10-05)

The first `m1n1-hoolock-pcie-j81-msi` build failed to compile: `0056`'s
`static_assert(is_power_of_2(...))` is not a constant expression in the real kernel (the host
stub had made it a macro, hiding it). Fixed in `0056` (plain bit test) and the stub is now a
function so the harness catches this class. The rebuilt payload (0052-0057) compiles cleanly;
`boot/verify_pcie_j81_reg_on_payload.py DIR --msi` passes (checksums, composition, DTB
`msi-controller`/`msi-parent`/`msi-ranges` = `<&aic 0 224 1 32>`, doorbell `0xbffff000`, the
`t7000-pcie: MSI domain:` string in the kernel). `result` points at it. **Not booted.**

## 11. H0 hardware result (2026-10-05, read-only boot of the `0057` payload)

Payload `m1n1-hoolock-pcie-j81-msi` (0052-0057), booted via the usual palera1n/PongoOS route;
read-only checks over telnet (session recorded under `artifacts/live/sessions/`, not committed).

- Boot normal, USB networking up in ~12 s. The one PMU write happened as usual
  (`J81 Wi-Fi REG_ON: 0x0403 0x09 -> 0x0b`).
- `t7000-pcie: MSI domain: slots 8..15 of 32, doorbell 0xbffff000` at 0.240 s: the AIC was
  found (no deferral), the parent domain was created, before host init.
- Link and enumeration unchanged from `0054`/`0055`: `link active=1 lnksta=0x3011` at 0.349 s,
  `14e4:43a3` enumerated behind `106b:1002`, BARs assigned, iommu group 0. Same two benign
  messages (`retraining failed`, `iommu-map id 0x8`).
- No new warnings or errors; the only other failure line is the long-standing `g_multi` gadget `-22`.
- `/sys/kernel/debug/irq/` does not exist (generic IRQ debugfs not enabled in this kernel), so the
  domain was confirmed from the probe log and the absence of the `NO_MSI` failure path only; no
  endpoint driver is bound, so `msi_irqs` is empty as expected.

H0 passes. Open for H1: allocate a vector on `01:00.0`, read back the endpoint's MSI capability
address/data (`0xbffff000` / `8`..`15`), free it. (Enabling `CONFIG_GENERIC_IRQ_DEBUGFS` in the H1
test variant would also give the domain listing.)
