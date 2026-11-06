# J81 two-address view plan

The synthetic four-view validator now models the contract recovered from the
8.1 initializer. A view is complete only when it has:

- a page-aligned mapped address;
- a distinct page-aligned backing address;
- explicit ownership and cache attributes;
- selector `0x80007`; and
- allocator flags ending in `0x22`.

The validator remains execution-disabled even for a complete synthetic plan.
It is a guard against accidentally collapsing Apple's backing and mapped
identities while preparing a future firmware adapter. The model is not yet a
hardware-test payload because the real addresses and ownership are runtime
Apple allocator results that Linux does not possess.

Checks: `tools/test_gpu_g4g_view_plan.py` and the full offline suite (82 passed,
7 expected skips).
