# J81 bare-PongoOS RGX revision-read result

## Result

The operator photo `IMG_4997.HEIC` records the guarded PongoOS discriminator
run. It completed the same known PMGR, 66 bridge-store, and GPC sequence as
the earlier no-core control. The visible tail confirms:

```text
20e005004 = 00000000   # three direct samples
20e01c200 = 80110100
20e02300c = 00000000
201e00000 = 40000000
pongoOS> peek 201000020
```

There is no result line and no following `pongoOS>` prompt after the final
revision read. The target remained on that command until it was recovered by a
forced restart. Thus the first RGX revision read at `0x201000020` did not
receive a response under bare PongoOS.

## What this changes

The same first core access now stalls after the recovered preamble both in
Linux and in PongoOS. That makes a Linux-only userspace, `/dev/mem`, or normal
Linux handoff error an insufficient explanation for the observed non-response.
It does **not** prove that both environments use identical mapping attributes,
nor does it prove the core address is wrong. It does show that replaying the
currently known PMGR/bridge/GPC state is insufficient before the core can
answer.

Page-5 `+0x4` was still zero immediately before the stalled read, despite GPC
control retaining `0x40000000`. This remains an observation, not permission to
write bit 30.

## Next work

Stop direct core-read repetitions and stop varying the three known GPC stores.
The evidence now favors an earlier iPadOS-only prerequisite: a PMGR device
dependency, reset/isolation release, clock/tuner action, or firmware-owned
setup that is not represented by the recovered sequence. The next productive
work is offline attribution of iPadOS's exact pre-identity initialization path,
then one bounded replay of an evidenced missing operation—not further blind
register writes.

Inputs: [PongoOS discriminator decision](2026-11-16-j81-pongo-core-read-discriminator.md),
[PongoOS no-core control](2026-11-16-j81-pongo-gpc-page5-result.md), and
[Linux core-read boundary](2026-11-07-j81-core-revision-after-clock-test4.md).
