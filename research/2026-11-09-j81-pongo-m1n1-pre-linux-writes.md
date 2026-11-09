# What PongoOS and m1n1 write before Linux on J81 (2026-11-09)

Question: on our boot path (checkm8 → PongoOS `bootm` → m1n1 → Linux), does
anything between iBoot and Linux touch hardware that iOS's path would leave
alone, or skip something iOS does, before the GPU ID read?

Offline source audit, no device access except one read of the private ADT
text on the Mac. Labels: **E** read in source, **I** inference.

## Sources audited

- PongoOS: `boot/Pongo.bin` (sha256 `1e5543fd...`, from the pinned
  `hoolockDocs` input) prints `pongoOS 2.6.3-bb492b00`. Audited
  checkra1n/PongoOS at `bb492b0` ("Load m1n1 at top of kernel data"). This is
  the source the version string names, not a rebuild of the binary.
- m1n1: HoolockLinux/m1n1 `d5a10ac` (flake input `hoolockM1n1Src`). Our two
  local patches (`boot/m1n1/patches/`) change only `src/kboot.c` device-tree
  preparation, no MMIO.

## PongoOS (`main_task.c`, `entry.c`, `bootm` path)

| Step | T7001 effect | Source |
|---|---|---|
| `interrupt_init` | AIC config | E |
| `serial_init`, pinmux | UART | E |
| `pmgr_init` | parses PMGR ADT only, no writes | E |
| `mipi_init` | registers a shell command only | E |
| `tz_setup` | sets the TZ register pointer at `0x200000480` (MCC); no write | E |
| `wdt_disable` | WDT off | E |
| `recfg_soc_setup` / `recfg_soc_sync` | skipped on A7/A8/A8X (`recfg_supported()`) | E |
| `aes_init` | AES clock gated on/off around use | E |
| `sep_setup` | SEP mailbox interrupt enable; `sep_teardown` disables it | E |
| USB | Synopsys OTG clock gates | E |
| `bootm` → boot | `sep_teardown`, `serial_teardown`, `interrupt_teardown`, then `smc` to EL3 and jump to m1n1 | E |

Nothing in PongoOS touches PMGR power states, the GFX blocks, `sgx`, or MCC
cache/config. One real difference from an XNU boot: `tz_lockdown()` runs only
from the SEP/XNU path (`sep_auto`, `sep_boot_hook`), so on `bootm` **TZ0/TZ1
are left unlocked** (E). TZ0/TZ1 are DRAM carve-out protection in the MCC.
That should not affect an RGX register read (I).

## m1n1 (`main.c`, `payload.c`, `kboot_boot`)

| Step | T7001 effect | Source |
|---|---|---|
| `mcc_init` | J81 ADT `mcc` is `compatible = mcc,t7000`, which m1n1 does not support, so MCC is left alone; `mcc_enable_cache()` is a no-op | E (ADT checked) |
| `aic_init`, `wdt_disable` | AIC, WDT | E |
| `pmgr_init` | reads all PS words; powers on only parents of devices already active. GFX is off at handoff, so nothing for GFX | E |
| `display_init`/`fb_init` | framebuffer on `disp0` | E |
| `sep_init` | SEP mailbox | E |
| `tunables_apply_static` | no case for T7001 (only M1/M2 AGX and ANE). The J81 ADT has one `*tunable*` property in total, `apcie-config-tunables`, so there are no ADT GFX tunables to miss | E |
| `clk_init` | MCA muxes only (Apple Silicon audio) | E |
| `usb_init` | A7-A11 `usb-complex` path | E |
| `cpufreq_init` (called when booting a kernel) | sets the CPU cluster p-state to 2 at `0x202200000`, then writes **`PMGR + 0x23000 = 1`** (`PMGR_VOLTAGE_CTL_OFF_T7000`, i.e. `0x20e023000`) | E |
| `smp_start_secondaries` | CPU spin-table release | E |

## Result

Neither stage writes any GFX, `sgx`, GPU-bridge or MCC register, and neither
skips a GFX step that iOS's boot path would do before its kernel. Two writes
differ from a plain iBoot → XNU handoff and are worth knowing:

1. **`0x20e023000 = 1` (m1n1 cpufreq).** m1n1 calls this voltage control. It
   is a PMGR-wide register, and the GFX perf entries carry voltage indices,
   so whether it touches the GFX rail is open (I). iOS probably writes the
   same register during DVFS setup (I, not checked); the 12B410 kernelcache
   could confirm.
2. **TZ0/TZ1 unlocked** (PongoOS `bootm` path). DRAM protection only (I).

What this audit does **not** cover: the iPadOS 15.8.8 LLB/iBoot on flash.
Only the iOS 8.1 (12B410) bootloaders have been disassembled
([iBoot/LLB note](2026-11-08-j81-iboot-llb-gfx-perf-state.md)). Their GFX
perf-block values match what we read live on 2026-11-09, but other blocks
were not inventoried.

## Next (cheapest first)

1. Offline: search the 12B410 kernelcache for a write of `0x23000` in
   PMGR, to see whether iOS sets the same voltage control word.
2. Read-only, live: one PMGR read of `0x20e023000` (expect `1`).
3. Needs the iPad in DFU, no Linux: decrypt the 15.8.8 LLB/iBoot with the
   device GID through checkm8 and inventory every block they write.
