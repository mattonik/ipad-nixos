# J81 bridge readback repeat

The guarded bridge-peek read was repeated from a fresh PongoOS/Linux handoff. It again returned `0x00000004` at `0x201f00018`, with PMGR `0x000003ff`, GPC state `0`, and normal watchdog disarm.

This matches the earlier readback baseline and strengthens the conclusion that the low word is stable across fresh boots. It still does not justify replaying the high control bits (`0x80010000`) or expanding the bridge table; those remain separate write experiments.
