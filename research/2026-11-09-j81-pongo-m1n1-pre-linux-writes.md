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

## Follow-up, same day: `0x20e023000`

**Live read (read-only).** Same boot as the GFX power-up (uptime 9546 s,
GFX PS `0x3ff`), preflight `perf-peek` GO. A one-word probe
(`pmgr-volctl-peek`, static build sha256 `215f9468...`, maps
`0x20e023000` read-only) returned **`0x00000001`**, the value m1n1 wrote.
The device stayed up. m1n1 uses a plain `write32`, so whatever LLB/iBoot
left there is overwritten and unknown.

**iOS 8.1 (12B410) kernelcache.** A scan of the whole decrypted image for
the constant `0x23000` (`movz #0x2, lsl #16` + `movk #0x3000`, and
`add #0x23, lsl #12`) finds exactly one site, at `0xffffff80031e90d0` in
`AppleT7000PerformanceController` (E). Base `[this+0x6d0]` is the same
PMGR base the clock-gate code uses. The function (`0xffffff80031e8fac`):

1. reapplies a saved CPU p-state through a vtable call and waits on
   cluster status;
2. if flag `[this+0x9e8]` is set, clears bit 0 of PMGR `+0x2d000`;
3. waits until bit 1 of PMGR `+0x2d100` clears;
4. sets **`PMGR+0x23000 |= 0xf00`**.

It has two callers, both in `callPlatformFunction`, and both are shutdown
paths: `gIOPlatformHaltRestartActionKey` (`0x...e92d8`) and
`gIOPlatformQuiesceActionKey` (`0x...e94a0`, right after the loop that
turns off clock gates left on). The keys were resolved from the kext's GOT
slots against the kernel symbol table (E).

So iOS writes this register when it shuts down or hands off, not on the
way up. No boot-time constant write was found. Boot-time accesses could
still go through the generic `read/write PMGR offset` helpers
(`0x...e9204`, `0x...e9210`) with offsets from tables, which this scan
cannot see. Our live value (bits 8-11 clear) is what a running OS would be
expected to have if `0xf00` is the hand-off setting (I). No evidence ties
this register to the GFX hang.

## Next

Needs the iPad in DFU, no Linux: decrypt the 15.8.8 LLB/iBoot with the
device GID through checkm8 and inventory every block they write.
