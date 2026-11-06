# J81 firmware-object resource initializer

The callback used at `0xffffff800329d558` is now resolved from the firmware
object vtable data:

```text
vptr data:       0xffffff80032b2df8 -> 0xffffff80032998d8
factory caller:  0xffffff800329d558
```

Before that callback, the factory creates five resource records from the
table at `0xffffff80032b32f0`; index 4 is intentionally skipped.  Each
active record is allocated with the alignment derived from the global page
shift, mapped through `0xffffff800329d6a4`, retained at object offsets
`0x578 + index * 8`, and given a translated view at `0x5a0 + index * 8`.

`0xffffff80032998d8` then performs the firmware-object resource initializer:

1. calls the object vtable at `+0x208`;
2. copies the resource count/stride state into object fields at `0x380` and
   `0x358`;
3. derives a bounded allocation size from the resource geometry;
4. obtains the backing resource and creates a `0x780000`-sized view;
5. allocates the matching descriptor storage and records the resulting
   handles.

This is a stronger boundary than the earlier generic “factory” label, but it
still contains no direct GPU MMIO write, DART programming sequence, or
firmware execution.  The model therefore records it as
`firmware-object-resource-init-review` and remains fail-closed.  The next
unresolved operation is the IOKit start/match implementation reached after
the publisher attaches and registers the firmware service; this cannot be
substituted with a guessed A8X firmware launch.
