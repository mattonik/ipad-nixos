# J81 PS86 saved-state cross-check

Offline review of saved PMGR observations and workspace artifacts. No device
read or other hardware access was performed.

## PS86 evidence

The only saved raw DISP0 PMGR word found is the Oct. 11 `uartpeek pmgr` sample
at index `0x56`: `0x1f0002ff`, captured during the Linux payload P4 session
(see `2026-10-11-uart3-register-capture.md`). The corrected J81 iOS 8.1 table
maps that power-state index to DISP0 record ID 28; the old “UART6” label was
wrong. Using the pinned Linux PMGR field definitions, the sample decodes to
target 15, actual 15, auto-enable 1, reset 0. This proves PS86 was in its
active state at that instant on that earlier Linux boot. It does not prove
the iOS provider's runtime `+0x980` mode, DISP0 clock-ID-112 edge ordering,
or that this state held during the Nov. 7 test4 attempt.

The Nov. 7 connected-Linux notes report a PMGR device `runtime_status=active`
and usage 1, but do not name a PS86 child. In the detailed Nov. 7 control
snapshot, the PS86-shaped node (`power-controller@202b0`) is bound to
`apple-pmgr-pwrstate` but reports Linux runtime-PM `unsupported`, usage 0,
like the other per-state nodes. This is software bookkeeping, not raw PMGR
readback. No Nov. 7 saved file contains a sample from physical
`0x20e0202b0`; the test4 GFX-only captures read `0x20e020320`.

Therefore the earlier active PS86 sample is consistent with an active display
power state and keeps the display/MCC hypothesis plausible as a path that can
be enabled. It neither establishes nor rules out that Apple's conditional
display/cache callback ran before the GFX event. In particular, an active
hardware state does not entail `+0x980 != 0`, successful `+0x98c` setup, a
successful asynchronous display callback, or an MCC mode apply.

## Workspace search

Searched the project and sibling workspace trees under
`/Users/martinp/Work/Sandbox` for saved iOS/IORegistry/sysdiagnose/kernelcache/
pmap filenames and for the distinctive runtime strings and PS86 address.
Beyond the known iOS 8.1 kernelcache and static DT in
`ipad-nixos/artifacts/live/private/gpu-offline/`, this found no additional
iOS 8.1 runtime dump or boot capture. The three sibling `ipadlinux-*` trees
contain copies of older UART research; their copied pre-correction text is
not an independent capture and must not be treated as separate evidence.

The Nov. 7 Linux control snapshot has useful *Linux* memory and display
inventory (System RAM map, simple-framebuffer/simpledrm, FDT and sysfs), but
no AP RAM image, pmap dump, iOS service logs, or PS86 word. The workspace
search does not rule out files outside the Sandbox workspace; none was
consulted.
