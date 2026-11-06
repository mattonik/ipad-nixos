# J81 synthetic Orchard view plan

Orchard defines the META firmware heap base as `ROGUE_FW_HEAP_BASE =
0xe1c0000000`. Feeding that base plus the recovered Apple packed offsets into
the execution-disabled view planner produces this **synthetic-only** set:

| view | synthetic base |
|---:|---:|
| 0 | `0xe1c0000000` |
| 1 | `0xe1c000f000` |
| 2 | `0xe1c0013000` |
| 3 | `0xe1c0014000` |

The planner marks the input complete for structural testing but keeps
`execution_allowed=false`. These addresses are Orchard heap arithmetic, not
evidence that Apple’s provider views use the same base. They must not be
uploaded or used for MMIO without an independently recovered ownership and
mapping contract.
