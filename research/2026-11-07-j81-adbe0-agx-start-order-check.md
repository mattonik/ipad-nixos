# J81 DISP0 / AGX service-start order: REA follow-up

Date: 2026-11-07. Static analysis only; no device, hardware, or MMIO access.

## Provenance checked

The IPSW `firmware/j81-12B410/ipsw/iPad5,3_8.1_12B410_Restore.ipsw` contains
`kernelcache.release.j81`. Its extracted IM4P bytes match
`artifacts/live/private/gpu-offline/kernelcache.im4p` exactly (SHA-256
`23327a52ee117523aade9625c1fbbbffb769df3e275471f58f96bf14b3d60d34`). The
decoded kernelcache in the same private artifact directory is SHA-256
`19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`, as
recorded in `2026-11-04-j81-gpu-offline-trace.md`.

The retained `AGXFirmwareKextG4G.raw` is a byte-for-byte split of that
kernelcache: prelink text base `0xffffff8002593000`, file offset `5,414,912`,
image load address `0xffffff8002e38000`, size `0x25000`; resulting file offset
`14,479,360`, and split SHA-256
`96ca8fa067f3503e7ca36d8f598fe15b51f1ffd5f63db47662c192aa49271957`. This
ties the fresh REA query below to the same iOS 8.1 kernelcache provenance.

## Fresh REA evidence: firmware-kext `start`

REA CLI 6.8.0 with Ghidra 12.1.4 analyzed
`AGXFirmwareKextG4G.raw`, arm64, at `0xffffff8002e3919c`:

* `ev_139f17ab434a11d1888d133a8189c5ef547a188acf9c7411d20d9b70cb132335`
  (`function`, full dossier)
* `ev_b9b0986667baf101823776f00eca4c3f25b7f1ce786cf0a8bb22ed4a5a2f25d0`
  (`decompile`)

The reconstructed body calls an indirect method from the parent vtable at
`+0x2b8`, then calls the service object's indirect vtable method at `+0x298`
with argument `0`, and returns the first call's result. The earlier vtable
resolution in `2026-11-06-j81-firmware-kext-start.md` identifies these as
`IOService::start` and `IOService::registerService(0)`. This override contains
no direct call or data reference to `AppleMobileADBE0`, display gate ID 112,
or the ID-28 dependency. REA marks both calls unresolved/indirect and reports
partial callee coverage, so this is a statement about this method body, not a
proof that the framework's matching path has no indirect dependency.

The separate main `AGX.raw` image (SHA-256
`d73035be6b81f15a179c55d10733efb5ecf26b0d77973ca4017f87587659da29`) was
searched with Ghidra's defined-string inventory:

* `AppleMobileADBE0`: empty results, Evidence
  `ev_147fe8ea1acbaf0d5238ef2183ab26fa41360eb164f57ca6f46525e8842a8aba`.
* Regex `AppleMobileADBE0|waitForService|IOResources`: empty results, Evidence
  `ev_f48264d975f747e8e30269614fa9839e7fea5e8ac89d170fe7e09daa3a9ed147`.

This is a bounded negative string search: it covers Ghidra-defined string
data, not encoded/undefined bytes or indirect service lookup through
framework calls. It does not establish absence of a service dependency.

## Result and remaining target

This pass finds no new static ordering edge. In the already documented path,
`AppleMobileADBE0::start_hardware` requests display gate-array index 0 (J81
ID 112), whose PMGR record conditionally dispatches dependency ID 28; G4G's
probe requests its own provider index 0 (GFX ID 124). Their separate provider
matches and the independent `AGXFirmwareKextG4G` registration/start path do
not prove which service starts first. The fresh REA body only confirms that
the firmware kext's `start` override delegates to generic IOKit start and
registers its service.

The exact unanswered target is the kernel's IOKit matching/publication path
for these personalities, or an iOS boot-time service-start trace. Static
inspection here cannot establish runtime scheduling, successful PMGR
transition, or whether ID 112 reached dependency ID 28 before the GFX ID-124
request. Keep the existing conclusion: there is no demonstrated
`disp0`-before-AGX requirement; actual boot order remains unknown.

## Method and limits

REA pseudocode and reference graphs are decompiler/provider observations, not
original source. The function dossier's indirect calls are unresolved, and
the string search's negative scope is limited as stated above. The display
provider split was not available in this pass; its prior Ghidra calls are
summarized in `2026-11-07-j81-disp0-rea-followup.md`. The `rea-agents` CLI was
used because the REA MCP restart was unavailable. No analysis database or
Evidence bundle was retained; complete inline Evidence IDs above are the
references for the returned results.
