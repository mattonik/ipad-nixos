# Review of the 2026-10-05 delivery-path research notes

Reviewed after the `0058` build: `msi-selftest-review`, `j81-dart-msi-doorbell-translation`,
`t7000-pcie-port-event-contract`, `pcie-delivery-path-prestudy`, `hardware-run-identity-protocol`.

## Verdict

Consistent with our own design and evidence; no contradictions found. Actions taken and not taken:

| Note | Finding | Action |
| --- | --- | --- |
| msi-selftest-review | Real gap: `0058`'s PASS did not check the parent chain, so a wrong AIC mapping could pass if data was in 8..15. | **Fixed** in `0058`: the chain is captured numerically (levels: per-device PCI-MSI, controller slot, AIC); PASS now needs depth 3, level[1] == data, AIC event (low 16 bits) == 224 + data; teardown has its own PASS/FAIL line. Rebuilt as the self-test payload; contract test unchanged and passing. |
| msi-selftest-review | H1 approval must name the endpoint MSI-capability writes, not only the PMU byte. | **Accepted**; the H1 go-ahead request will list both. Labelled H1A (configuration path), not delivery. |
| j81-dart-msi-doorbell-translation | The `IOMMU_RESV_MSI` reservation is an address-model fact only; fabric consumption point unknown. | Agreed; matches design section 11/12. No PTE to be invented. |
| port-event-contract | Port 1 event parent is AIC 215 (level) vs MSI 232..239 (edge); keep separate from MSI domain. | Agreed; this is design U4, still later, gated by a W1C write. |
| delivery-path-prestudy | `+0x168` read-only dump is the delivery gate, independent of H1A; `brcmfmac` is not a minimal MSI trigger. | Agreed; dump still to implement (approved earlier). |
| hardware-run-identity-protocol | Host evidence does not prove the payload running on the device. | Adopt a cheap subset for H1: put a run token in bootargs and capture `/proc/cmdline` first. Not yet implemented; the full JSONL protocol is optional. |

One caveat on the note's "AIC parent hwirq == 224 + data": the AIC hwirq packs a die field above
the 16-bit event number; J81 has one die so the raw value equals the event, and the test masks
the low 16 bits anyway.
