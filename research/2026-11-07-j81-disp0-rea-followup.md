# J81 DISP0 startup and AGX pre-ID: REA follow-up

Date: 2026-11-07. Static only; no hardware or MMIO was accessed.

## Target and tool

REA CLI 6.8.0 ran Ghidra 12.1.4 against the already carved iOS 8.1
`AppleH7GADBE0` Mach-O at `/tmp/AppleH7GADBE0-12B410.raw` (arm64,
SHA-256 `05bdac3bd7404ecffa00a2f66e8d94def97fe3a0c1bcd9c2628102a187f395fb`).
The per-command environment used `GHIDRA_INSTALL_DIR=/opt/homebrew/Cellar/ghidra/12.1.4/libexec`
and Java 21 at `/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home`.
REA reported its Ghidra provider available. The first probe used the nested
`.../libexec/Ghidra` path and reported `executable_missing`; correcting the
root path fixed it. Each CLI call imported an ephemeral Ghidra project, so the
existing `.gpr` project was not reused. The original Mach-O remained
unchanged.

## Startup call boundary corrected

REA decompilation of `FUN_ffffff80032d5c3c` (Evidence
`ev_a278d18c591f3b98931ad5f8d1fae8b53aff2fd918a6e5385eee89911a0827d3`)
shows the normal, non-FPGA branch performs these actions after allocating the
driver object:

1. Driver vtable `+0x910` with state 1.
2. Provider vtable `+0x560(1, 0)` and `+0x568(1, 0, 0)`.
3. `FUN_ffffff80032d6340`, then normal helper `FUN_ffffff80032d6540`.

The helper decompilation (Evidence
`ev_6dc7cac7d0a636fb3bdeea3d6166d951b9974526dcba393de4cd62675f3206bd`)
shows `FUN_ffffff80032d6540` calls `FUN_ffffff80032d45b8`, the parent
`start_hardware` path, then continues display setup. It does not repeat the
provider `+0x560` / `+0x568` calls.

The FPGA/bring-up alternate helper `FUN_ffffff80032d6050` (Evidence
`ev_72275a218db54f80fc85a2a1a786e128de9345613b5d69fc6300e5c18c77ced8`)
does perform driver `+0x910(1)`, provider `+0x560(1,0)`, and
`+0x568(1,0,0)` before calling `FUN_ffffff80032d45b8`.

This refines `2026-11-07-j81-disp0-record-consumer-trace.md`: its statement
that both normal and FPGA helpers make the requests was too broad. In the
normal path, the requests are in `start_hardware` itself immediately before
its helper; the alternate path makes them inside the FPGA helper. Both paths
request the provider clock/power before the parent start call. On the matching
J81 `disp0` configuration, provider clock index 0 selects gate ID 112. The
subsequent ID112 → dependency ID28 dispatch remains conditional on the PMGR
transition/reference edge; this static evidence does not prove that edge ran
on a particular boot.

## AGX early probe cross-check

REA decompilation of `FUN_ffffff80032935a0` from the original iOS 8.1
`AGX.raw` Mach-O (SHA-256
`d73035be6b81f15a179c55d10733efb5ec26b0d77973ca4017f87587659da29`)
returned Evidence `ev_5998a162ce3dca19ec479f3a0a52d7c31e3c1c8be0673edb840c338c9a500598`.
It independently confirms this order in the G4G probe: map RGX resource;
call the accelerator's property hook `+0x790`; request provider `+0x560(1,0)`
and `+0x568(1,&local,0)`; map GPC and write its control/state setup; delay;
call accelerator `+0x800` identity method. The identity method is therefore
reached after G4G's own provider clock/power and GPC steps. The AGX function
contains no direct display ID 112 or ID 28 request: its provider calls use
gate-array index 0, and the AGX node's matched gate ID is GFX ID 124. This
matches the previous object/vtable trace, and does not establish any runtime
ordering between the separate display service and AGX service starts.

## Evidence limits

These are decompiler observations from shipped iOS 8.1 code plus the previously
recorded device-tree mapping. They establish branch-local call ordering, not
boot-time service scheduling, successful PMGR transition, or `+0x980` runtime
state. The existing test4 Linux capture cannot observe the Apple service
callbacks. REA's decompiler output is reconstructed pseudocode; all three
analysis calls used ephemeral imports rather than the prior on-disk Ghidra
project. The CLI result itself did not persist a portable Evidence bundle.
