# J81 bridge readback test: ready for operator-present hardware run

The next bounded test is a supervised, read-only readback of `0x201f00018` after the PMGR transition. It also rechecks GPC state zero and the PMGR word. It has a one-shot guard, strict stage ACKs, and a 20-second watchdog.

Verified payload hashes:

- `gpu-bridge-peek`: `52cd0d9d7e79a52f57d1b65137533a4b95a8928f1c1beb3b9b2fafeec005e0de`
- `gpu-watchdog-supervisor`: `5729f6daf64dcdac4206ae0f75b15c6bba471043a164cdb9ebf1eb184ca0bcfd`
- `gpu-bridge-peek-run`: `1e807ad156199dba1d7f739be8515e65bfa88b311efa0cb8afa7dbbad9023285`

The existing capture tool is `boot/gpu_bridge_peek_capture.py`; its wrapper requires the verified PMGR module, kernel notes, runtime-active state, rootfs-only mounts, and the exact payload hashes. A successful result must report PMGR `0x000003ff`, GPC state `0`, a single bridge readback value, `rc=0`, and watchdog disarm. Any timeout or unexpected value is a stop condition; do not retry in the same boot.

The source comment notes that bridge reads may have undocumented effects. This is therefore the next operator-present test, not an unattended or firmware test.
