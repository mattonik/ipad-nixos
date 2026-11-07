# J81 G4G simulator boundary

The repository can run the recovered sequence as a host-side, execution-free
model. `tools/gpu_g4g_contract.py` now exposes the reviewed sequence explicitly:
LDR review, META start, synthetic alive events, interrupt-disable review, META
handshake review, GPC control-list review, and boot-descriptor review. On the private J81 image, the current simulator reviewed 58 load records,
11 zero records, 27 config writes, three Apple-8.1 guarded zero skips, and one
thread record. It copied no firmware bytes and issued zero MMIO operations.
The alive-contract model reaches `APPLE_HOST_ACCEPTED` by injecting event 0
and modeling the wait routine's success-byte write. This is only an abstracted
Apple host path: the producer, callback dispatch, and interrupt delivery are
unknown, so the aggregate assessment keeps `firmware_handshake_ready=false`.

This is useful for parser/layout/ordering regressions, but it is not an iPad
GPU simulator: it has no A8X MMIO model, PMGR/clock model, META coprocessor,
interrupt delivery, or firmware execution environment. Therefore:

- no DFU is needed for this host simulation;
- DFU/PongoOS is required to run a payload on the real iPad;
- a real GPU firmware boot or render test cannot be validated by the current
  simulator and remains execution-disabled.

The safe next hardware boundary, once approved, is a boot-only diagnostic that
does not execute the unknown G4G firmware. A true render test still requires a
future A8X firmware/command-path implementation and a fresh controlled boot.
