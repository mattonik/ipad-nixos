# J81 provider callback return values do not gate the first core read

Offline static follow-up to the J81 first RGX-read hang. This isolates the
control-flow role of Apple's two provider callbacks immediately before GPC
setup; it is not a PMGR busy-path or Cascadia comparison. No device or MMIO
was accessed.

## Finding

In iOS 8.1 `FUN_ffffff80032935a0`, the first provider callback is the indirect
call at `0xffffff80032936c4` (`provider +0x560`, enable clock). Its return in
`x0` is overwritten by the second callback setup; there is no conditional
branch on it. The second call at `0xffffff80032936e0` (`provider +0x568`,
enable power) likewise has its return discarded. The local output word is
initialized to zero at `0xffffff80032936ac` and passed by address to this
second call.

After both calls, the code looks up and maps the GPC resource, writes the
three GPC values, and invokes the accelerator identity matcher. There is no
branch on either provider callback status between the callbacks and that
first identity read. Therefore a returned error code alone is not Apple's
pre-read gate. A missing or ineffective callback *side effect* remains a
possible difference, because the calls can still alter clocks, power state,
or controller bookkeeping despite their statuses being ignored.

The output word has a separate, post-read role. After the identity matcher
returns, the probe writes GPC state zero; only then does it test the saved
word. If nonzero, it calls provider power-off (`+0x568`) followed by clock-off
(`+0x560`). This is cleanup selection, not a precondition for entering the
identity matcher. The wrapper implementations' invalid-index error
(`0xe00002c7`) is also not evidence of a pre-read abort in this caller.

## Scope and limitation

This rules out one narrow hypothesis: “Apple checks a provider callback
failure and declines to read the core.” It does not show that the callbacks
succeeded in an actual boot, establish their stateful side effects, or prove
that Linux can safely reproduce them. The hung Linux transaction remains
unexplained; this result only prevents callback return status from being
treated as the missing control-flow condition.

Evidence: original 12B410 instructions in
`artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` at
`0xffffff80032936ac..0xffffff800329382c`; cross-checked against
`gpc-link.c`, `provider.c`, and the provider binding in
`2026-11-07-j81-gpc-provider-object-binding.md`. The disassembly provides
the control flow; it cannot reveal runtime callback return values or effects.
