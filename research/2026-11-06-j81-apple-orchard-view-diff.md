# J81 Apple/Orchard synthetic view diff

The new offline comparator uses identical packed offsets and synthetic bases,
then varies only the provenance attributes:

| attribute | Apple-side placeholder | Orchard-side placeholder |
|---|---|---|
| ownership | `physical_io` | `orchard_fw_object` |
| cache mode | `unknown` | `uncached` |

It reports eight differences (ownership and cache mode for four views) and
rejects compatibility while keeping `execution_allowed=false`. This is the
intended fail-closed result: matching arithmetic must not erase unresolved
ownership or cache semantics.
