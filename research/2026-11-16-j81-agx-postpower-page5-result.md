# J81 page-5 bit 30 remains clear after AGX power callback

## Result

The `j81-agx-postpower-panic` probe ran on the target iPadOS 15.8.5 build
`19H394` and produced its intended kernel data abort. The retained panic
report is `panic-full-2026-11-16-141932.000.ips`; it identifies the expected
kernel UUID `CC26BE6A-292B-3759-9ED0-290BCF18B090`, and its planned-fault
registers are:

```
x0  = 0x0000000000000000
far = 0x0000000000000000
pc  = 0xfffffff02012dbb8
```

`pc` is in the injected shellcode cave. The zero `x0`/`far` pair is therefore
the captured value of `PMGR + 0x5004`, not an unrelated fault address.

## Boundary established

The hook sits directly after AGX G4G's provider `CLOCK` and `POWER` calls and
before AGX maps GPC or issues these stock GPC operations:

1. `0xffff0000` to GPC `+0x10000`;
2. `0x40000000` to GPC `+0x0`;
3. `0x11` to GPC `+0x1000`, followed by its busy poll.

Consequently, PMGR page-5 bit 30 is **not** established by generic
ApplePMGR startup or the first AGX provider clock/power requests. This removes
the provider callbacks from the candidate set and places the remaining
transition inside the stock GPC sequence (or a later AGX action).

## Next discriminating capture

The narrowest next probe should replace the instruction immediately after the
stock GPC `0x40000000` store. It can reuse the same planned-panic transport,
with no injected GPC write, and answers whether that store itself makes page-5
bit 30 visible. If still zero, repeat after the stock `0x11` request and poll.
