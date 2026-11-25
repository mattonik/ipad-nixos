# Research request 9 result: GFX PS bit 28 (AUTO_PM_EN) on J81, and the rest of Apple's GFX-on (19H394)

Offline analysis of the same stock iPadOS 15.8.5 (19H394) J81 kernelcache as requests 6–8 (sha256 `c3507666…a0008`). It covers ApplePMGR, AppleT7001PMGR/AppleT7000PMGR and the AGXG4G results from earlier requests. I also read the captured J81 ADT `pmgr` node and the mainline Linux `drivers/pmdomain/apple/pmgr-pwrstate.c` (kernel.org, current master). The pinned Hoolock tree was not checked, so treating it as the same file is inferred.

Addresses drop the `0xfffffff0` prefix. Tags:
- **code**: read from the disassembly;
- **adt**: the captured J81 ADT;
- **source**: Linux source;
- **capture**: the run log or the runner source in `context/`;
- **inferred**.

No device was used. There is no Apple binary content beyond addresses, offsets, short mnemonics and field names.

## Correction to request 8 first

Request 8 said "Linux leaves `PM_GFX_PS` at `0x3ff` with bit 28 clear", and it read that as a difference in the code. **That was wrong** (source):
- Mainline `apple_pmgr_ps_set()` already does Apple's two-store sequence on every genpd power-on. It stores the target with bit 28 and bits 8–9 written 0, polls the actual state, then makes a second store with `APPLE_PMGR_AUTO_ENABLE` (bit 28) set.
- Probe also sets bit 28 on any domain that is already on.
- The driver's own comment on that store: "Not all devices implement this; this is a no-op where not implemented."

So the runner's `activate` step has already made the bit-28 store, and the `0x3ff` read afterwards is the hardware's answer. Runs 27, 27b and 27c repeated the store by hand and got the same answer. There is no auto-PM code difference between Apple and Linux for GFX. The AUTO_PM_EN lead is dropped.

## Findings

**Q1, located (code). It is the same register and the same plain store. Nothing in the code shows the bit is readable.**
- **Register (t1 rows 4, 11, 15):** `_setPSLevel` (`0x6bc6ed8`, named by its panic string at `0x6bc7500`) computes the register as regmap `ps-regs[group].regmap` at `ps-regs[group].offset + index * 8` (`0x6bc6f64`–`0x6bc6f70`).
- **Value for GFX:** the ADT `ps-regs` group 3 = (regmap 0, `0x20300`, valid mask `0x1f`). GFX is index 4, so the register is `+0x20320`, exactly the one the runner uses (code; adt). The runner's stores changing bits 8–9 confirm it is the live PS register (capture).
- **Store path:**
  - The bit-28 store goes through vtable `+0x988` = `writeReg32` (`0x6bd04f0`), a plain `str w, [VA + offset]` after bounds checks.
  - The read goes through `+0x980` = `readReg32` (`0x6bd0478`), a plain load.
  - There is no lock, no unlock sequence and no second register.
- **No subclass override:** all four PMGR vtables (two in ApplePMGR, two in AppleT7001PMGR) have the same base functions at `+0x980`/`+0x988`/`+0x990`/`+0x998`. AppleT7000PMGR/AppleT7001PMGR's own methods are CPU-energy, perf-state, CCC and video/ISP-clock functions (their strings). A scan of their `+0x980`/`+0x988` calls found only regmap 8 and regmap 0 `+0x2c084` with constant offsets (t2, last row). No PS-layout change was found; the scan does not prove that none exists.
- **No separate auto register:**
  - The auto minimum level lives in the same PS register, bits 19:16 (`_setPSAutoMinLevel`, `0x6bc6da0`: PS & `0xfff0fcff`, then the level into bits 19:16). For GFX the level is 0, and PS already reads 0 there.
  - `PWR_x_CFG0 SLEEP_DEPTH` (`0x6bd1bb0`) is written only for devices whose ADT entry names a power-gate record (byte `0xe`, read at `0x6bd1b7c`). GFX has byte `0xe = 0`, so it has none.
- **Readability can't be settled from code:** Apple never reads bit 28 back to check it. Its only reads are the "no change" test (`0x6bc7168`) and a log line. Three captures plus Linux's own store say it reads 0 on GFX. Treat bit 28 as not implemented for the GFX domain on this part (capture, strong). Whether it is implemented on any other T7001 domain is open; Q5 gives a read-only check.

A side result on bits 8–9 (code; capture):
- They behave as write-1-to-clear "was gated" history flags. Linux calls them `WAS_PWRGATED`/`WAS_CLKGATED`.
- Apple writes 1s there only when lowering a domain to level ≤ `0xe` (`0x6bc7228`), and 0 at level `0xf`.
- Run 27b wrote 1s and cleared them, as expected. That is harmless.

**Q2, located (code). There are no hidden preconditions.** t1 lists every check and access in `_setPSLevel`.

Checks before the first store (software only):
- group, index, valid-mask bit, device-map entry and die number;
- a "no change" test (target == level, bit 28 == auto, bit 30 == 0, bit 10 == 0);
- if bit 28 already reads 1, Apple first clears it and waits for actual `0xf`. That branch is never taken on J81.

Stores:
- the target store with bits 8–9 written 0, then a poll on bits 7:4 (`0x6bd0564`, a repeated `readReg32` against `mach_absolute_time`, timeout `0x2ee00` ticks);
- then the bit-28 store (`0x6bc733c`–`0x6bc735c`);
- then, only if set, one more store each to clear bit 30 (`0x6bc7364`) and bit 10 (`0x6bc738c`). Both read 0 in the runner.

Nothing else is involved: no other PMGR register, no interrupt mask, no parent state check. The callers' wrapper (`0x6bd9628`) does only software work, most likely locking (inferred). The "force no access" and "no wakeup" paths are not on this route.

**Q3, located (code; adt). Apple's GFX-on is the min-level write, the PS sequence, then two bridge configurations** (t2). Both device-on paths do the same thing:
- the RunMax loop at start (`0x6bcd47c`–`0x6bcd4cc`);
- the device-state path (`0x6bd8734`–`0x6bd8860`).

The steps:
1. `_setPSAutoMinLevel(3, 4, 0)`, only for auto devices (ADT byte 0 bit 2 clear; GFX flags `0x00`). Linux does this only with `apple,min-state`, but the register state ends up the same: bits 19:16 = 0.
2. `_setPSLevel(3, 4, 0xf, auto 1)`. Linux genpd does the same writes (source).
3. **`_configureBridge` for every bridge in the device's ADT bridge list** (`0x6bd90a8`, after `_setPSLevel` at `0x6bcd4cc` and `0x6bd881c`).
   - The "two extra indices" from request 8 are this list: byte `0x18` is the count (2) and bytes `0x1c`… are the bridge numbers `0x09` and `0x0a`. The asserts "device->bridgeCount <= kDeviceBridgesMaxCount" and "device->bridges[j] < _bridgeCount" use the same fields.
   - Bridge N is PMGR ADT `reg[bridge-reg-index (2) + N]`, so bridge 9 = `0x201f00000` and bridge 10 = `0x201f80000`, each `0x81000` long (map loop `0x6bc0620`–`0x6bc0800`).
   - The ADT has no `bridge-settings-version`, so the version is 0. That selects the path that stores every (offset, value) pair of `bridge-settings-9` and `bridge-settings-10` in order. Each property has 33 pairs and the two lists are identical: first offset `0x18`, then `0x40000`–`0x4007c` (parser `0x6bc09a8`–`0x6bc0a3c`).
   - The stores go through vtable `+0x998` = `0x6bd3d38`, a plain 32-bit store.
4. Not done for GFX on J81:
   - bridge byte counters (`0x6bd4d94`): no `bridge-counters` property;
   - power-gate `CFG0`: ADT byte `0xe = 0`;
   - cluster power-up: ADT byte `0x19 = 0`.

   One conditional call was not traced: `0x6bd9798`, which needs another device entry with byte 1 bit 4.

Who does what:
- Linux's PMGR driver does not configure bridges.
- The runner does: the 66 bridge stores in `batch` are this step, to the same two windows (capture, runner source).
- But the runner does it **only once**. Its `h3p` power cycle (run 24) does `pm_runtime_put_sync`/`get_sync` and never re-applies the bridge stores. Apple re-applies them on every GFX power-on.
- I couldn't check the runner's plan header (`gfx-bridge-plan.h`) against the ADT order and values, because it isn't in `context/`.

What I could not decide: whether bridges 9 and 10 lose their settings when GFX powers off. That Apple re-applies them on every power-on suggests they do (inferred, moderate).

**Q4, partly located. A short ranked list remains, and none of it is strong** (t3):
1. **The runner's direct RGX accesses before the stream**, present in every hanging run (capture). W1 rewrites `META_BOOT`, W2a sets and clears `SOFT_RESET`, and `batch` does a 0→1 with RGX identity reads. Apple's Fender path makes no host RGX access before the stream; the stream's own `SOFT_RESET` entry is the first RGX write (`0x6690c04`–`0x6690c20`, request 7). This is the one ordering difference never tested: request 7's fallback (drop W1/W2a) was skipped when run 26 was chosen.
2. **Bridges not re-applied after the power cycle.** This makes run 24 a less faithful copy of Apple's power cycle than intended. It cannot explain runs 12–19, which had no power cycle and had the bridge stores applied.
3. **Time in state 0 with `+0` bit 30 set** (run 25b). Run 25b is confounded by two extra Fender reads, and its control has not been run.
4. **The runner's own PMGR stores in its `pmgr` step** (PLL1/PLL4 `+8`, MCC bank, MiscACG, SoC TVM). They are present in every run, and Apple's GFX-on makes none of them at this point. I did not evaluate what Apple or iBoot leaves in those registers.
5. **Remaining items with no register reach before the store:** the override load-back, `+0x10` cleared twice, the AIC unmask, and the Fender "powered" flag (requests 6/7).

Dropped as explanations:
- AUTO_PM_EN;
- the auto minimum level;
- `PWR_x_CFG0`, cluster power and bridge counters (none are used for GFX);
- the T7000/T7001 subclasses (no PS override).

What actually stops the walk is still not visible from host code.

## Q5: next experiments (one variable per boot, nothing new on the GPU before the first)

**Boot 28 (read only, no GPU steps): a PS survey that answers Q1 for the whole PMGR.**
- From the shell, before `precheck`, read each PS register whose ADT valid-mask bit is set:
  - group 1 `0x20e020100 + i*8` (all 32);
  - group 2 `0x20e020200 + i*8` (mask `0x7ffebfdf`);
  - group 3 `0x20e020300`–`0x20e020320`;
  - group 4 `0x20e020400`;
  - group 5 `0x20e021000`–`0x20e021010`.
- Record bits 3:0, 7:4, 8–9, 10, 19:16, 28 and 30.
- Linux has already stored bit 28 on every domain that is on.
- What it tells you:
  - If any powered domain reads bit 28 = 1, the bit is implemented per domain and GFX lacks it.
  - If none does, bit 28 is not readable on T7001 at all.
- Either result closes the AUTO_PM question without another GPU boot.
- These reads are safe: Apple polls PS itself (`0x6bd0564`) and Linux genpd reads it. Group 3's neighbours (VENC `+0x20300`, PCIE `+0x20308`, PCIE_AUX `+0x20310`, ANS `+0x20318`) are the closest comparison.
- Do not write any PS register in this boot.

**Boot 29: run 11's sequence with the h7d one-entry list (`0x3808 ← 0`) and without W1 and W2a.** No direct RGX access before the stream, as on Apple's path. Keep everything else as in run 11, including the spacing. Pass/fail is "the `+0x20000 = 0` store returns or not". If it passes, repeat with h7c (`0x3808 ← 1`) for a visible replay.

**Boot 30, only if boot 29 hangs: a faithful Apple power cycle.** That is run 24 (h3p + h7d), but with the 66 bridge stores re-applied right after `pm_runtime_get_sync` and before the second state-0 request.

**Control, any time:** run 25b without its two Fender reads (empty list, extra 100 ms only). This shows whether elapsed time in state 0 alone breaks the empty-list store.

**Do not do:**
- read `+0x20000` before it is written (run 25);
- read PMGR `+0x5004` after `+0` is written (runs 20–23);
- read RGX in state 0;
- add Fender reads between `+0` and the store;
- read the bridge windows (Apple only writes them on this path; reads are unproven);
- store PS bit 28 again (it adds nothing).

## Not resolved

- Whether PS bit 28 exists on any T7001 domain (boot 28 answers this).
- Whether bridges 9 and 10 lose their settings across a GFX power-off.
- Whether the runner's bridge plan matches the ADT pairs and order (the plan header is not in `context/`).
- What `0x6bd9798` does on the device-state path. It is conditional on another device entry and not traced.
- What the Fender walk needs in state 0, and why the empty-list store becomes time-sensitive (run 25b).

## Files

- `t1-setps-sequence.tsv`: Q1/Q2, every check and access in `_setPSLevel` and `_setPSAutoMinLevel`, plus the shared accessors.
- `t2-gfx-on.tsv`: Q3, Apple's GFX-on next to Linux genpd and the runner, with the ADT fields and bridge windows.
- `t3-differences.tsv`: Q4, the remaining differences ranked, plus the dropped leads.
- `SHA256SUMS`.
