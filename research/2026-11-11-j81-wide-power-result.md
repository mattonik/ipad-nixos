# J81 20-domain power comparison result

On 2026-11-11, fresh cycle-payload Linux boot
`00ef6863-e756-417e-a9b9-f27705b35d6b` completed the
[20-domain comparison](2026-11-11-j81-wide-power-test.md). All 20 individually
acknowledged power-state writes returned target/actual `15`; all 20 words read
active immediately before the GPC test, after it, and again at the later
snapshot. The three external parent states passed before the restore and
before GPC. This is checkpointed observation, not continuous monitoring.

The GPC state-1 poll succeeded on poll 11. Page-5 `+4` read
`0x00000000` less than 750 ns after the successful poll and again less than
102,083 ns afterward. The later PMGR snapshots also read zero. The supervisor
logged `stage=finished rc=0` and `stage=watchdog-disarmed`; the iPad answered
ping after all captures. No GPU-core read or page-5 write was made.

DWI was `0x200` before restore and `0xff` at the later checkpoints. PMGR
`0x2300c` was `0` before the GPC campaign and `0x164` after. The candidate
PMU row `0x0128` bytes 0/2 changed from `0x00`/`0x40` before GPC to
`0x64`/`0x64` after and remained there in the later snapshot. This reproduces
the [DWI-only result](2026-11-11-j81-dwi-gpu-comparison-result.md); the
snapshots are not simultaneous, and the row's rail and voltage meaning remain
unverified. No PMU value-write command or whole-PMU dump was performed; I2C
register selection and reads can have side effects.

The broad restoration of these 20 domains, in this order on this boot, was
**not sufficient** to make the observed page-5 bit match the working iPadOS
capture. It narrows the candidate set but does not establish that the domains
were held throughout the transition, that all power/clock/reset dependencies
were satisfied, or that page-5 bit 30 controls GPU-core accessibility. It does
not prove what would happen on a core read, which remains a known-stalling
operation. The direct writes bypassed genpd bookkeeping and were not restored;
the current RAM boot remains in that changed state.

Raw logs are private at `artifacts/live/gpu/wide-power-20261111-01/`.
