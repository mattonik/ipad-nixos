# J81 DWI-on + core read: result (2026-11-21, run 1) -- THE CORE READ NOW WORKS

Recipe: research/2026-11-21-j81-dwion-core-plan.md (crumbs-core module d9398f84, core read
enabled; PMGR writes in Apple's order; one guarded DWI-on store; one GFX activation;
compressed irq-off batch). Fresh observer boot, preflight GO, one shot.

## Result
- Core ID at 0x201000020 = **0x00070500** (iPadOS value). No bus hang, no watchdog reset.
  core_valid=1 bridge_ns=47875 bridge_to_gpc_ns=3916 poll_to_core_ns=4125 core_read_ns=500 crumb=on.
- GPC poll ok after 28 polls; page5 first sample 0x40000000.
- DWI PS 0x20120: 0x200 (S0,S5) -> 0xff after the guarded write, held to +10 s.
- GFX VID 0x2300c = 0x164 after activation.
- PMIC row 0x0128: 00 00 40 00 before the batch; 64 00 64 00 after the batch and after 10 s.
  Rows 0x0100, 0x0150, 0x01c8 unchanged.
- Framebuffer squares: not recorded by the host (batch survived; crumb=on).

## Reading
The only difference from every earlier hanging Linux run is the DWI power state on before
the GFX activation (with MiscACG etc. already in Apple's order). With it, the GFX rail
request reaches the PMIC (row 0x0128 follows to 64/64) and the core load completes.
Together with the no-core DWI run (batch returned, row followed) this isolates DWI as the
missing piece. Caveats: 64/64 is not by itself proof of voltage; one run only.

## Next
- Repeat once for reproducibility (fresh boot).
- Make DWI-on part of the real boot path: keep the dwi power domain on (Linux switches it off
  ~0.7 s into boot with 19 other domains) instead of a post-boot poke.
- Then the GPU driver bring-up proper.
Logs (private): artifacts/live/private/j81-linux-dwioncore-results-20261121-run1.
