# J81 GPC state-1 candidate staged (not executed)

The bounded GPC candidate was copied to the currently running RAM boot and
verified by hash:

```
/tmp/gpu-gpc-init      8a67ba955fca1aa2fe2b043e4512919aefa49c475542af1581d32b388f988282
/tmp/gpu-gpc-init-run  de1ec4dfdd741c85d948779e4642e50b7aa6232a890be9745982e6a67cfac17f
```

The one-shot guard is clear and the existing PMGR consumer is still active.
Staging did not load the binary or access GPC registers. The candidate remains
operator-present execution only; a fresh boot is required before running it.
