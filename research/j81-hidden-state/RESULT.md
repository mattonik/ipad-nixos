# J81 GPU rail and clock state at the successful early hook

**T1 — what preceded the successful load.** [Observed in capture] The November 14 stock 19H394 boot DCE69446 returned revision 0x00070500 at 20:57:12.168088. The DWI driver logged its startup banner 21.434 ms later and the D2207 PMIC driver logged its banner 72.306 ms later. [Code] The PMIC driver's identifiable external writes to registers 0x444 and 0x11 follow that banner. Those writes in this invocation cannot have enabled the earlier read. The DWI driver's five register writes precede its banner, so the same timing argument cannot place them after the load. This leaves a specific ordering question for DWI. Source: ios-logarchive-j81-pmgr-bisect-03/boot.logarchive, mach timestamps below; 19H394 VA suffixes 6ce7290, 6ce771c..7788 and 6c9a490..5a8. See [driver details](rail.md).

**T2 — power-domain ancestry.** [Board data] GFX ID 124 has zero parents; none of the other 97 PMGR records lists 124 as a parent. All 180 nodes of the 19H394 tree were checked for clock-gates and power-gates declarations of ID 124. Only /arm-io/sgx names it, in both properties. The pinned Linux ps_gfx provider likewise has no parent power-domains property. DWI and the I2C host have independent power states. A physical rail or fabric condition can exist outside this graph. Source: J81 pmgr/devices, ps-regs; Hoolock Linux 6831bc701a6ce059e71e5aaa9488c9195bea6927 arch/arm64/boot/dts/apple/t7001-pmgr.dtsi, ps_gfx at line 607.

**T3 — setup before the hook versus during the observer.** [Code] PMGR enables the voltage manager and seeds CPU and SRAM before returning. The identified T7001 method makes no direct GFX VID or PMIC write. [Observed] GFX VID was zero when the observer began, reached 0x164 after its manual GPC request, and stayed compatible with a responding core. Native AGX clock/power calls occur later. An earlier charger sleep-preventer log on this same boot concerns a different service and establishes no GPU rail transaction. No pre-hook GFX-specific PMIC, SMC, SEP, SPI or SPMI command could be positively attributed. The CLPC feedback selector dispatches a gated performance event; the restore table names SOC and CPU perf domains. See [DVFM and CLPC sites](dvfm.md).

**T4 — what Linux inherits.** [Code/observed] Loader code has potential writers for the bank, PLL and perf controls. Pongo has been observed with voltage-manager control 0xf01, while m1n1 has a literal write of 1. XNU reaches 1 by masking the old word. Linux's 0x164 internal request can be accompanied by external PMIC bytes 64/64: this was verified on a historical Linux boot with DWI active and page 5 low. New Linux runs reached page 5 high and retained all 66 bridge words across GPC. They lack a paired external PMIC measurement. None of these captures identifies the physical voltage at the GPU. See [loader and Linux attribution](boot-stages.md).

**T5 — next discriminating observation.** [Inference] First look for the same four quantities on a single page-5-high Linux no-core boot: DWI power state, PMGR GFX VID, page 5, and the previously sampled D2207 bytes 0x0128 and 0x012a. Capture before and after GPC. A request with unchanged external bytes would separate that boot from the earlier DWI-on result. Matching bytes would weaken a missing digital request as the explanation; they do not measure power-good, voltage ramp or interconnect isolation. There is no evidence-backed regulator command or setpoint to send. See [runner and research-agent handoff](HANDOFF.md).

## Same-boot ordering

| Event on boot DCE69446-4DFB-405B-BDAD-79790E1714EB | machTimestamp | Evidence |
|---|---:|---|
| Charger added to sleep preventers | 984880038 | Different service, no rail identifier |
| Observer P0 | 994228592 | PS=300, page 5=0, perf=80000000, VM control=1, GFX VID=0 |
| Observer P1 | 994246296 | page 5=40000000 three times, perf=80110100, GFX VID=164 |
| Before core; revision returned | 994246926; 994247261 | CORE=00070500 |
| AppleS5L8940XDWI::start message | 994761679 | version 1, buck mask=0 |
| AppleD2207PMU::start message | 995982621 | I2C provider diagnostic |

[Code] XNU DWI startup calls the provider clock and power slots at 6c9a4a8/4c4. On the mapped DWI base (ADT PA 0x20e200000), stores at 6c9a4d4..4f0 go to offsets +0, +0x50, +4, +0x14 and +0x10, in order. Given J81 properties nclk-div=1, polarity-config=1, str-delay=8000, lockout-us=5, the computed words are 1, 192000, 60, 0 and 0x41. These are requested values inferred from the instructions and tree. They have no established per-register GPU rail function. The subsequent three-property loop uses voltages-buck%x and sets a software presence mask printed at 6c9a5a8. A zero mask describes the discovered lists, not a voltage reading. The distinct D2207 dwi-buck-control property is absent from the stock tree.

| Domain | ADT ID and physical PS | Declared immediate parent | Relevance |
|---|---|---|---|
| GFX | 124, 0x20e020320 | none | SGX gate-array index 0 |
| DWI | 54, 0x20e020120 | none | Separate device; historical Linux PS 0x200 before, 0xff after enabling |
| I2C0 | 70, 0x20e020160 | SIO_P | Host of pmu,d2207 at bus address 0x3c |
| SIO_P | 4, 0x20e0201f8 | none | Ancestor of the PMIC diagnostic bus, separate from GFX |

[Code] The PMGR clock list names AF, LIO, MCU_FIXED, ISP_SENSOR0_REF, ISP_SENSOR1_REF and VENC; its separate power-domains list names SEP, ACS and AMC. Neither is an extra GFX parent. These are static declarations. The states of every unrelated PS at the successful hook are unknown. On the working boot neither DWI PS nor external buck bytes were among the observer's fields.

## Ranked remaining questions

| Priority | Evidence and minimal observation |
|---|---|
| 1. Downstream GFX rail delivery | Digital correlation demonstrated on Linux; physical rail identity uncertain. Use paired PMGR/PMIC snapshots on a page-5-high no-core boot. On iPadOS prefer an existing bus-owner diagnostic or retained trace. I2C register numbers are not offsets usable with the MMIO-only observer. |
| 2. DWI startup versus inherited configuration | DWI stores precede its post-ID banner. Seek an earlier timestamp for the first provider call or register write on the same UUID. The Linux control can sample known config +0/+4 with DWI already active. Those two words alone cannot date when they were written. |
| 3. Core mapping and transaction completion | Fender and bridges respond through distinct apertures. Compare actual physical translation, leaf memory type, CPU and privilege at the core VA using supported diagnostics. Existing Linux and predicted iPadOS MAIR bytes agree. If an exception was recorded, retain its valid syndrome/address. |
| 4. Fabric/MCC or isolation | The endpoint-specific symptom fits; no particular missing control is demonstrated. Intersect existing before-hook fabric/bridge traces by physical address and source. Linux now has 66/66 readback twice. Compare an existing known-readable selector-9 +0x18 at matching iPadOS phase first. |
| 5. Core clock source or reset history | GFX state, perf word and page 5 agree; these do not measure clock pulses at the core. Compare existing clock consumer, page-5 and reset status at the same phase; require a named clock or reset and a source-backed observation before suggesting an intervention. |

A whole-kernel static inventory cannot establish the scheduling or bus transactions of every driver on the measured boot. The positive pre-hook path, negative findings, executable branches and unknowns above have different evidentiary weight. No independently verified ADC channel, external power-good signal, pre-hook GPU PMIC transaction or phase-matched physical rail measurement was recovered.
