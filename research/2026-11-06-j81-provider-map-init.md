# J81 provider-created map initializer

The map object allocated by provider vtable `+0x6c0` has vptr
`0xffffff80032ac880`; its `+0x70` initializer is:

```text
0xffffff80032ac8f0 -> 0xffffff8003281ab8
```

`0xffffff8003281ab8` receives `(provider, task, wrapper, selector)` and:

1. checks the provider's mapping predicate;
2. extracts selector bits 16–19 (`0x90007` becomes mapping class `9`);
3. stores either the provider's page-scale field or the fallback `0x4000`;
4. stores selector bit 20 (clear for `0x90007`);
5. returns success.

It does not calculate a device address, program a DART, access GPU MMIO, or
launch firmware.  The private selector is therefore metadata consumed by a
later map/address operation.  The remaining unresolved boundary is narrowed
to that later address materialization and DART ownership.
