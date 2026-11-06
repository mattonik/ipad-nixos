# J81 guarded bridge test: hardware-ready artifact

The stage-3 guarded test is ready for an operator-present run. It requires a fresh PongoOS/Linux handoff with USB networking at `172.16.42.1`; it does not upload firmware or start META.

## Verified payloads

| Payload | SHA-256 |
|---|---|
| `gpu-bridge-segment` | `af16f75da8a50e5672cba96b612a45098c05472c26c0bed04fd681c826c5e337` |
| `gpu-watchdog-supervisor` | `5729f6daf64dcdac4206ae0f75b15c6bba471043a164cdb9ebf1eb184ca0bcfd` |
| `gpu-bridge-segment-run` | `4a290390de54921bbfcafa52b362588ac835d893e2b5d4d4ec52bed8acaf9f70` |
| `gpu-pmgr-peek` | `78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd` |

The previously verified PMGR module and kernel-note hashes are:

`39d32b553830d57b1ae0657c265b931bed248de95d14935c6be818b6372b8f89` and `82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014`.

## Expected result

The guarded sequence must report PMGR `0x000003ff` (`target=15`, `actual=15`), GPC pre-state `0`, then exactly five bridge writes:

`0x201f00018=0x80010004`, `0x201f40000..08=0x007c7c01`, and `0x201f4000c=0x007c7901`.

The watchdog must disarm normally. Any missing stage, unexpected value, timeout, or nonzero child result is a stop condition; do not retry in the same boot.

This is the highest-confidence hardware test currently justified. GPU identity, firmware execution, META startup, and rendering remain separate experiments.
