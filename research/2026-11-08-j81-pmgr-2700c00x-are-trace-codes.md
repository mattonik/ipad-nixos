# J81 PMGR `0x2700c001`/`0x2700c002` are kdebug trace codes, not hardware actions

Date: 2026-11-08. Offline disassembly of the iPadOS 15.8.8 J81 kernelcache's
`com.apple.driver.ApplePMGR` `__TEXT_EXEC` (VA `0xfffffff006bb9000`, size
`0x34a4c`). It was cut from `ios15-kernel` and is byte-identical to the
existing `ios15-ApplePMGR.raw`. Disassembled with `objdump -b binary -m aarch64`.
No device access.

## Finding

Earlier notes describe the GFX busy-edge path as "sending PMGR action/event
`0x2700c001`" before the display/MCC callback and `0x2700c002` after it. See
`2026-11-07-j81-soc-busy-display-action-before-rgx.md` and
`2026-11-06-j81-ios15-clock-provider-reconstruction.md`. In iOS 15 these
constants appear only in small tracing helpers:

```
fffffff006bd124c: ldrb w8, [x0, #324]          ; per-object trace enable
                  cbz  w8, ret
                  adrp/ldr x8, GOT[0x...fcd950]; global word
                  ldr  w8, [x8]
                  tst  w8, #0xfffffff7          ; (flags & ~0x8) != 0
                  b.eq ret
                  mov  w0, #0xc001; movk w0, #0x2700, lsl #16
                  mov  w3, #-1; mov w4, #-1; mov x5, #0
                  b    0xfffffff006bed950       ; GOT stub to an external kernel function
```

`0x...bd128c` is the same helper with `0x2700c002`. `0x...bd1200` is the
generic version that takes the code as an argument, the same
`(this, code, a, b, -1, -1)` shape the 8.1 code calls through vtable
`+0x740`. The guard `global & ~0x8` matches XNU's inline `KDBG` check
(`kdebug_enable & ~KDEBUG_ENABLE_PPT`). The call goes out through a GOT stub
to the kernel, with arguments `(code, arg1, arg2, -1, -1, 0)`, which is
`kernel_debug`'s signature. These helpers contain no MMIO. With tracing off,
they return straight away.

In iOS 15 the only caller of the `c001` helper is `0x...bd7a1c`. It emits
`c001`, runs `0x...bd7ad0` through a command-gate `runAction`
(`[this+0x160]` vtable `+0xe8`), and then emits `c002`. `bd7ad0` is the PMGR
device power-state change and selects state 15 on enable. The codes are a
start/end trace pair around a state transition, so they have no
hardware effect of their own.

## Consequence

This removes one apparent "missing Apple step" from the test4 comparison. On
the GFX clock-enable path, the real side effects stay as already recorded:

- PMGR state 15 for power index 100. Test4 reached `0x3ff`.
- Selector 9 and 10 bridge writes. Test4 replayed all 66.
- On a busy 0→1 edge, the conditional display-idle callback and MCC selector.
  These run only when the framebuffer-caching setup is enabled.

The trace codes are not a hardware precondition, so Linux does not need to
emit or emulate them. The 8.1 `+0x740` slot was not resolved by vtable dump
here. Its call shape and constants match the iOS 15 trace helpers, but treat
that as strong inference, not proof.

This adds no reason for a new hardware test. The test4 RGX read stall is
still unexplained. The remaining difference worth chasing offline is the
conditional display/MCC busy callback, or state that Apple's
reference-counted clock path sets and test4 does not reproduce. Neither is
yet a specific, safe register read.
