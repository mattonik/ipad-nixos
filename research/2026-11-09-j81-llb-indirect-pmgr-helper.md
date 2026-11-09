# J81 15.8.8 LLB: PMGR address helper callers

Offline analysis, 2026-11-09. The private 19H422 J81 LLB was loaded as
AArch64 at `0x180380000` in the existing Ghidra project. No iPad access.

## Method and scope

The routine at `0x1803917fc` inserts `0xe01` in `x8[31:16]` and `0x2`
in `x8[47:32]`, preserving the low 16 bits, then returns. Ghidra's normal
reference inventory did not propagate the modified `x8` through this call.
An instruction walk of the analysed image found four direct branches to this
helper. The nearby instructions at each branch were checked manually. This
is a bounded search: code not analysed as instructions, indirect calls, and
other address helpers were not covered. The original image, Ghidra project,
and instruction listing remain private in `artifacts/live/private/`.

| Call site | Constructed address | Observed operation |
|---|---|---|
| `0x1803907f8` | `0x20e01c200` | Set bit 31 by read/modify/write, immediately after the page-5 sequence. |
| `0x180390f48` | `0x20e01c200` | Store zero in a separate shutdown-like routine. |
| `0x180391330` | `0x20e01a000` | Write 2 or 3 depending on an argument and poll until its upper 16 bits are zero. |
| `0x180391644` | `0x20e01c300` | Store `0x40000001`. |

The `0x20e01a000` block also appears in the original direct-reference
inventory; the helper reveals this additional access, but its role and
connection to GFX are not established. The function containing the
`0x1c300` store also writes CPU-cluster-related and PMGR locations. The
`0x1c200` zero store occurs in a different routine from the bit-31 set;
no ordering between those two routines can be inferred merely from their
addresses. See [bootloader scan](2026-11-09-j81-iboot-15.8.8-first-scan.md).

## Implication for test4

The bootloader code can set bit 31 at `0x20e01c200` and write
`0x40000001` at `0x20e01c300`, matching values observed in a later Linux
boot. The capture was not made at test4's stalled identity read, and the
static listing does not prove which LLB path ran during that boot. There is
no source-backed reason here to replay a write or to read the newly found
`0x20e01a000` access on the live device. The post-power performance
capture and test4 sequence are described in the
[perf read](2026-11-08-j81-gfx-perf-state-live-read.md) and
[pre-ID audit](2026-11-09-j81-pre-id-readiness-sequence-audit.md).

## CPU performance-state connection

A follow-up trace resolves a CPU connection without naming the `0x1a000`
block itself. The enclosing routine `0x1803912e0` reads
`0x202220050 & 0x38`; unless that equals `0x10`, it calls
`0x1803911f0(2)`. That helper writes `((2 & 7) << 22) | 0x02000000`
to `0x202220020`. The upstream
[T7000 device tree](https://github.com/torvalds/linux/blob/master/arch/arm64/boot/dts/apple/t7000.dtsi)
identifies `0x202220000` as the CPU cluster performance controller, and
the [Linux CPU-frequency driver](https://github.com/torvalds/linux/blob/master/drivers/cpufreq/apple-soc-cpufreq.c)
describes `+0x50` bits `[5:3]` as current CPU p-state and `+0x20` as
its command register. Thus this routine checks for CPU p-state 2 and, if
needed, requests it before the conditional `0x1a000` operation. The code
does not show an intervening wait for the CPU transition to complete.

A separate 8.1 `AppleT7000PerformanceController` function at
`0xffffff80031e82f4` conditionally reads PMGR `+0x1a000`, uses its low
nibble as an index into the table at `+0x1a018`, and writes the resulting
word to PMGR `+0x23004`. This establishes a second software connection to
power/performance control, not the field's electrical meaning or a GPU
connection. Its own flag conditions and call context still need resolving.

The three direct calls found to the 15.8.8 routine are at `0x180381c90`
(argument 3), `0x18038e4e4` (argument 0), and `0x18038f7ec` (argument 3
or 4). Argument 0 does not enter the `0x1a000` write branch. These are
static code paths; actual execution and register values during Linux or iOS
boot are unobserved. Together the CPU connection makes this a lower-priority
GPU-specific probe candidate, but does not exclude a shared dependency.

## Short address-builder inventory

A follow-up Ghidra instruction walk inspected analysed functions of at most
six instructions containing both `movk` and `ret`, in the 15.8.8 LLB and
iBoot images. This finds small helpers like `0x1803917fc` that the direct
reference scan can miss. It is not a whole-program symbolic execution:
longer helpers, indirect control flow, unanalysed instructions, and other
ways to construct an address are outside scope.

The walk found 77 matching LLB functions and 126 iBoot functions. Of those,
16 LLB and six iBoot functions insert `0x2` at bit 32, consistent with the
SoC peripheral aperture. Their fixed address fragments correspond to
PMGR, pin control, or other ranges, not the `0x201000000..0x201ffffff`
GPU aperture. The LLB `0x1803917fc` helper is the one resolving the GFX
perf-control writes above; the other short helpers include the
`0x20e4xxxxx` family and reads at `0x20e029000` and `0x20e02a000`.
No additional GPU-aperture access was identified in this narrowly defined
helper inventory. This does not prove the bootloaders never access the GPU:
a GPU address could be formed by another instruction pattern or path.

The list is a candidate inventory, not a proof that each instruction
executes or that its target is reachable. The analysed private Ghidra
projects and complete listings are under `artifacts/live/private/ghidra-iboot/`.
No new live read was warranted by this result.
