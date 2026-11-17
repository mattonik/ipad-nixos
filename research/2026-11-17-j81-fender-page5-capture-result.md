# J81 post-GPC Fender / page-5 read-only capture, 2026-11-17

One supervised run on a fresh cycle-payload RAM boot (boot id
fdf26388-9c7f-45cf-87c9-e6a7dc62d451, kernel notes 82ff70e8...). Sequence:
stage, PMGR cycle, bridge, then the Fender probe (known GPC setup followed by
one read-only snapshot). Logs are private under
`artifacts/live/private/j81-fender-status-run-20261117-2029`.

Artifacts (all SHA-256 verified before and after staging):
- probe `gpu-gpc-fender-status` 690a2d5774ed302c76a0104767990faee1e72a1d5f5041ab349c8c3140186eff
- supervisor 076bee589ff168b952bb48ad2c233b608372f6e70a0806ffbadec60d2a2d2fa9
- runner 648d81347352f02d434a803384884fbc5ca10058e717f3b07eca47a85a425123
- page-5 module ca16576e6d574ff3587d631cd3fb82e3ae0ce83f49cdd5c4d3156f9306099e4c
- rebuilt gpu-pmgr-cycle.ko c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23
  (identical to the original; build-id note hash 8e4e9917...)

Result line:

    stage=after-gpc-fender control=0x40000000 settle=0x00000000 state=0x00000001 hold=0x00000000 page5=0x00000000

Observation only: Fender control has bit 30 set and bit 29 clear after the GPC
poll, so bit 29 is still not seen on Linux at this point. Page-5 +0x4 reads 0.
No interpretation beyond that is recorded here.
