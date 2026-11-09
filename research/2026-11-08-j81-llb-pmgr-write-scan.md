# J81 12B410 LLB: bounded PMGR write scan

Date: 2026-11-08. Offline disassembly of the local iPad5,3 12B410 LLB.
No device or MMIO access.

## Scope and method

Extracted `LLB.j81.RELEASE.im4p` from the local restore IPSW and decrypted its
payload with the public 12B410 IPSW key. Disassembled the payload as AArch64
at base `0x180000000`. The observed instructions below are in the same LLB
setup path as the documented GFX perf-state table writer at
`0x180012fbc`–`0x180012ff0`. Their direct caller and normal startup
reachability are traced below.

This is a bounded static scan of direct address constructions in the setup
path. It establishes the listed operations, not the meaning of undocumented
PMGR fields. It does not rule out other helpers, indirect writes, or setup in
other LLB paths.

## Additional observed PMGR operations

| Instruction site | Address/effect established by instructions | Limit |
|---|---|---|
| `0x180012ff4`–`0x18001301c` | Polls `0x20e005000` bit 25; clears bit 0 at `0x20e005004`; sets bit 24 at `0x20e005008`. | Same PLL-5 setup already noted with the GFX perf table; no register meaning inferred. |
| `0x180013020`–`0x180013034` | RMW sets bit 31 at `0x20e01c200`. | Matches the previously documented GFX perf-state control write. |
| `0x180013038`–`0x180013064`, helper `0x180013b2c` | Calls helper with `(1,4,0x85,0,0)` and `(3,1,0x32,0xb,0)`. The helper addresses `0x20e000000 + index*0x1000`, including writes and polls at offsets derived from its arguments. | These are direct PMGR-indexed operations; index meanings and any relation to GFX are unresolved. |
| `0x180013068`–`0x1800130a4` | Reads chip-ID/fuse word `0x20e02a020`; when `(word & 0x07000000) == 0x05000000`, RMW-writes `0x20e00300c`, replacing bits under mask `0x0e000000` with `0x0a000000`. | Conditional SoC write; no GFX attribution established. |
| `0x1800130a8`–`0x1800130bc`, helper `0x180013b2c` | Calls helper with `(4,1,0x32,0,1)`, again using the indexed PMGR block. | Index/field meaning and relation to GFX unresolved. |
| `0x1800130c4`–`0x1800130e4` | RMW sets bit 31 at `0x20e010000`, `0x20e011000`, `0x20e012000`, `0x20e013000`, and `0x20e014000`. | Five-slot block; function of the block is unknown. |
| `0x180013108`–`0x180013124` | Copies six words from an in-image table to `0x20e00f208`–`0x20e00f21c`, polling bit 30 after each store. | Table values are static; the block's meaning and relation to GFX are unknown. |
| `0x180013128`–`0x180013154` | Copies 47 words from an in-image table to `0x20e010000`–`0x20e0100b8` in 4-byte steps, polling bit 30 after each store. | This follows the five bit-31 RMWs above and overwrites only `0x20e010000`; the other four addresses are 0x1000 apart. Same unknown-block caveat. |
| `0x180013158`–`0x180013184` | RMW-clears selected bits at `0x20e020400`, then polls until bits 7:4 equal `0xf`. | The exact T7001 DT child at PMGR offset `0x20400` is `ps_sep` / `sep`; this is a SEP power-state operation, not a GFX register. The state-word interpretation is supported by the matching Linux PMGR driver. |

## Five-page and 47-word writes: xref and table check

The code and data xrefs in the decrypted LLB do not supply a device or
subsystem name for the `0x10000` region. In the routine at `0x180012c64`,
the five-page loop at `0x1800130c4` constructs `0x20e010000 + i*0x1000`
for `i = 0..4`, reads each page's offset 0, and sets bit 31. The 47-word
loop at `0x180013128` uses the in-image table at payload offset `0x245d8`
and writes its words to `0x20e010000 + i*4`, `i = 0..46`, polling bit 30
after each write. Thus only the first page's offset-0 word is subsequently
overwritten by this loop; the other four page writes are separate.

The table is static: its entries are constants in the `0x80100000` through
`0x89100000` range, and the loop has no fuse read or conditional input. The
later chip-ID/fuse test in the same routine writes `0x20e00300c`, not this
table or page block. The five-page and table operations are in the same
routine as, and follow, the GFX perf-state/PLL setup, but no xref names them
as GFX or CPU. Their proximity does not establish a functional link. Current
primary evidence therefore supports an unnamed PMGR region with static
clock/config-looking words; domain attribution and any CPU/GFX relationship
remain unresolved.

The helper `0x180013b2c` has a direct indexed address calculation: it forms
the base `0x20e000000`, adds `index << 12`, then accesses offsets `+0x10`,
`+0x8`, and an index-derived offset. This confirms the three call tuples
reach PMGR register space. It does not identify a device/domain name for
indexes 1, 3, or 4.

## Cross-check against iOS and Linux descriptions

An offline cross-check of the local decoded iOS 15.8.8 J81 kernelcache
(`com.apple.driver.AppleT7001PMGR`; private and not included in this repository,
with provenance summarized in
[`2026-11-08-j81-ios15-kernelcache-provenance.md`](2026-11-08-j81-ios15-kernelcache-provenance.md)) finds accesses to
PMGR-relative offsets `0x10050`, `0x10054`, and `0x10208`. In particular,
the driver writes offsets `0x10054` and `0x10208` and polls bit 30; another
path saves/restores `0x10050`/`0x10208` the same way. Its
`0x10208` write uses `0x81001000`. This independently confirms that the
iOS PMGR driver uses this general `0x10000` register region and that bit 30
is used in the driver's poll condition on those paths. It does not
identify the purpose of the LLB's `0x10000` table, its five `+0x1000` RMW
targets, or its indexed helper registers: the iOS accesses are not at the
same offsets as most of the LLB stores, and matching a poll bit is not a
register specification.

The iOS kernel's `0x10208` is distinct from the LLB's `0xf208` by `0x1000`.
Both are followed by a bit-30 poll in their respective code, but the available
evidence does not establish that they are aliases or have the same purpose.
Keep the LLB address as `0x20e00f208` and its meaning unresolved.

The public Linux T7001 device tree describes PMGR as a `0x24000`-byte region
at `0x20e000000`; its named `power-controller` children include `gfx` at
relative offset `0x20320`, `sep` at `0x20400`, and VENC children from
`0x21000` through `0x21010`. The LLB's absolute address `0x20e020400` is
exactly PMGR-relative `0x20400`, so its clear-and-poll sequence targets the
SEP power-state word described by that DT. The Linux driver defines bits
7:4 as the actual state and bit 31 as `RESET` for these DT-described words;
the LLB polling for state `0xf` is therefore consistent with waiting for
the SEP word's active state. This identification does not establish why LLB
does so or a runtime effect on this device.

The T7001 DT has no named child at relative offsets `0x10000` through
`0x14000`, nor at `0xf208`, and no names for helper indices 1, 3, or 4.
Linux's bit-31 `RESET` definition applies to the DT-described power-state
words and cannot be transferred to those unnamed LLB offsets. The indexed
helper establishes only that each index selects a page at
`0x20e000000 + (index << 12)`; the available ADT and published descriptions
do not map those index values to domains. These sources confirm PMGR
aperture membership and identify `0x20400` as SEP, but leave the other LLB
targets unresolved.

Sources: [Linux T7001 PMGR device-tree patch](https://lkml.iu.edu/hypermail/linux/kernel/2502.0/01346.html)
(PMGR aperture and named power-state children, including `ps_sep` at
`0x20400`); [Linux T7000 PMGR driver](https://github.com/torvalds/linux/blob/v7.3-rc1/drivers/pmdomain/apple/pmgr-pwrstate.c)
(state-word access and bit definitions). The Apple binary observation is from the local iOS 15.8.8 J81 kernelcache
slice named above. That private artifact is not available to public readers,
so this finding is not independently reproducible from this repository; its
provenance is summarized in
[`2026-11-08-j81-ios15-kernelcache-provenance.md`](2026-11-08-j81-ios15-kernelcache-provenance.md).

## RGX/GPC scope

The inspected setup path contains no direct construction of an address in
`0x201xxxxx` in the listed operations. This is not proof that LLB has no
indirect RGX/GPC/fabric access: a full trace of generic mapping helpers,
tables, and every caller was outside this bounded pass. The PMGR operations
above are candidates for handoff-state comparison only; the evidence does
not show that any one configures the GFX/RGX/GPC path or caused the later
identity-read stall.

## Evidence boundary

The decrypted payload and scratch disassembly were kept outside Git. Numeric
addresses and instruction behavior above are from the local payload; public
readers cannot independently reproduce this binary analysis from this
repository. There was no hardware validation. No Linux programming recipe or
new hardware experiment follows from this scan.

## Direct caller and boot reachability (offline follow-up)

The routine containing `0x180012fbc` starts at `0x180012c64`; its only direct
caller found by scanning aligned AArch64 `BL` instructions in the decrypted
LLB is the wrapper at `0x18000fd0c`, whose instruction at `0x18000fd14`
branches-and-links to `0x180012c64`. The wrapper returns immediately after
the setup routine. Within the setup routine the GFX table loop at
`0x180012fbc` calls `0x180013adc` for states 0–8, then states 9–15; the
following PMGR operations run in the same straight-line routine.

The wrapper is itself called at `0x1800006bc` in the LLB startup routine that
begins at `0x1800006a0`. That startup routine is the return target installed
at `0x180000044` after LLB's initial relocation check/copy at `0x180000000`.
The instructions from `0x1800006bc` onward call the wrapper and then continue
through other initialization calls; there is no conditional branch around
this call in that sequence. Thus the setup is reached on the normal startup
path once relocated LLB enters its startup routine; the static path shows no
boot-type condition guarding this call. This agrees with the separate iBoot
finding that Darwin boot does not quiesce these PMGR settings.

This establishes direct static call reachability, not runtime execution on a
particular boot: no hardware trace was made. The relocation/copy mechanism
and indirect targets elsewhere in LLB are outside this caller claim, and the
direct-call scan cannot rule out aliases or alternate setup paths.
