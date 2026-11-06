# J81 GPC state-1 test: operator-present artifact ready

The next hardware candidate is the existing execution-gated `gpu-gpc-init`
probe. Offline tests pass for its initial-state gate, ordered writes, durable
checkpoints, bounded polling, and completion/refusal paths.

Pinned artifacts:

* probe: `8a67ba955fca1aa2fe2b043e4512919aefa49c475542af1581d32b388f988282`
* host capture: `669ba1cc0ae15f416b41771684faaae5b7737d1223b84423cfe3dc8f51b83afc`
* source: `e20de1655ebf765125e2aaca234ca2ecceae3edaf50c4c363984bf1cff3395a5`

The candidate requires a fresh test boot, PMGR state `0x000003ff`, and GPC
state `0`. It then performs exactly these writes, each after a persisted host
checkpoint:

```
GPC +0x10000 <- 0xffff0000
GPC +0x00000 <- 0x40000000
GPC +0x01000 <- 0x00000011
```

It polls `GPC +0x1000` at most 64 times and accepts only low state `1` with
bit 4 clear. Any failed checkpoint, unexpected value, timeout, or disconnect
stops without retry. It has no GPU-core ID read, bridge replay, firmware,
META, or rendering path.

This is test-ready but not safety-proven: the writes can still wedge the
interconnect. Run only with physical recovery available and a fresh boot;
never append it to a prior bridge or GPC session.
