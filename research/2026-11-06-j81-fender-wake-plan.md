# J81 Fender wake plan after RGX read hang

The Orchard G5P transport patch supplies the missing sequencing contract for a
future J81 probe. The current `gpu-gpc-init` candidate is insufficient because
it starts from an already-on PMGR lease and writes the GPC request directly.

The next candidate must be one-shot and fail closed in this order:

1. Read and persist the PMGR baseline; require the known test-kernel identity
   and RAM-only root.
2. Perform one bounded PMGR GFX off/on generation before any Fender MMIO. The
   power-off path must leave the domain requested on and must not be retried.
3. On the Fender wrapper, write `+0x20000 <- 0`, poll `+0x1000` bit 4 clear,
   then write `+0x1000 <- 0x10` and poll the full GPC state to zero.
4. Write `+0x20000 <- 0x20`, confirm the hold bit, and require the GPC state to
   remain zero.
5. Perform the existing wake writes: `+0x10000 <- 0xffff0000`, `+0x0000 <-
   0x40000000`, `+0x1000 <- 0x11`; poll bit 4 clear and record the final state.
6. Only after every checkpoint succeeds may a separate read-only RGX identity
   step be considered. A failed checkpoint consumes the boot and forbids retry.

This plan is execution-disabled. It still needs a kernel-side PMGR off/on
consumer that matches the exact test kernel ABI; the current `gpu-pmgr-once`
module intentionally exposes only the single power-on request. No hardware
test is authorized until that module and the complete checkpoint collector are
built and host-tested.
