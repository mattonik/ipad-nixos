# J81 iOS 15 AppleARMIODevice vtable candidates

Date: 2026-11-08. Bounded offline inspection of the local iOS 15 kernelcache
(embedded `DTPlatformBuild=19H402`; its 19H422 source association is verified;
see [the provenance check](2026-11-08-j81-ios15-kernelcache-provenance.md)).
This verifies source provenance, not which binary was running on a device.
No device, build, or MMIO access.

## Mapped AppleARMPlatform ranges

The kernelcache prelink metadata gives AppleARMPlatform load address
`0xfffffff00548e100` and executable size `0xd1f0`. Its Mach-O load commands
place the executable `__TEXT_EXEC` at `0xfffffff005b22000` (size `0x33f70`)
and `__DATA_CONST` at `0xfffffff006d0cb80` (size `0x156b0`). These map into the
kernelcache's `__PLK_TEXT_EXEC` segment (VM base `0xfffffff005a9c000`, file
offset `16023552`) and `__PLK_DATA_CONST` segment (VM base
`0xfffffff006cf4000`, file offset `35258368`) respectively. The writable
`__DATA` begins at `0xfffffff00798e480`, within `__PRELINK_DATA` (VM base
`0xfffffff007988000`, file offset `38469632`). Thus the small prelink-text
executable slice does not contain the implementation code or vtable data.

The existing partial Ghidra project loads without whole-cache analysis, but
its string reference manager has no cached references for the queried names.
A direct AArch64 ADRP+ADD scan of the mapped AppleARMPlatform text finds three
instructions computing the exact AppleARMIODevice string pointer:

| Code address | Resolved string address |
|---|---|
| `0xfffffff005b29a2c` | `0xfffffff0054911ee` |
| `0xfffffff005b29afc` | `0xfffffff0054911ee` |
| `0xfffffff005b2a380` | `0xfffffff0054911ee` |

The string is `AppleARMIODevice`. The first site below is a class-registration
function; the other two references are not needed for the slot trace here.

## Verified instance slots

The class-registration function at `0xfffffff005b29a24` passes the
`AppleARMIODevice` name, its superclass metaclass, and size `0xd8` to the
OSMetaClass constructor, then installs `0xfffffff006d11720` on the returned
metaclass object. That is not the service instance vtable: its entries include
`OSMetaClass::release` at `+0x10`.

The instance constructor at `0xfffffff005b29a5c` instead calls its base
constructor and installs `0xfffffff006d11178` as `[this]`. In that table,
`+0x568` is `0xfffffff005b29d34` and `+0x570` is
`0xfffffff005b29de0`.

`0xfffffff005b29d34` bounds-checks an index against `this+0xa0`, reads the
corresponding ID from `this+0xa8`, and forwards to the object at `this+0x88`
through that object's own vtable `+0x568`, with `(ID, arg2)`. On the G4G
pre-ID call `+0x568(1,0)`, this means table index 0 and forwarded arguments
`(ID[0], 1)`. `0xfffffff005b29de0` similarly checks an index against
`this+0xb0`, reads its ID from `this+0xb8`, and forwards through the inner
object's `+0x570` slot with `(ID, state, output)`; the G4G call
`+0x570(1,&out,0)` selects table index 0 and forwards `(ID[0], 1, &out)`.
Both methods also make a conditional helper call with action codes
`0x05070000` and `0x05070004`, respectively, before delegation.

The `AppleARMIODevice` method at `0xfffffff005b2a108` stores its second
argument to `this+0x88` (`param_1[0x11] = param_2`) before reading the clock
and power gate arrays. This is the base-class path; the T7001 subclass below
has its own overrides at these two slots.

## AppleT7001IO subclass table and targets

The local iOS 15.8.8 prelink inventory declares `IOClass=AppleT7001IO`,
`IONameMatch=arm-io,t7001`, and `IOProviderClass=IOPlatformDevice`. The
embedded `AppleT7001` Mach-O header is at `0xfffffff005a76740` in
`__PRELINK_TEXT`; this metadata load address is not its code address. Parsing
that nested Mach-O gives `__TEXT_EXEC` at `0xfffffff006c7b000` (size `0xc38`)
and `__DATA_CONST` at `0xfffffff006fe3ac0` (size `0xfd8`). They map through the
outer kernelcache segments to file offsets `0x2127000` and `0x248fac0`.

The `AppleT7001IO` metaclass registration at `0xfffffff006c7ba2c` passes the
`AppleT7001IO` name (`0xfffffff005a76cf8`), superclass metaclass pointer
`0xfffffff006fe3ae0`, and instance size `0x120` to the OSMetaClass helper; the
returned metaclass receives vtable `0xfffffff006fe41a0`. The instance
constructor at `0xfffffff006c7b038` first calls the base constructor helper,
then writes `0xfffffff006fe3bb8` to `[this]`. Thus `0x006fe41a0` is the
metaclass table and `0x006fe3bb8` is the instance table. The superclass
metaclass pointer identifies the static subclass relationship to
`AppleARMIODevice`.

The `AppleT7001IO` instance table overrides the requested slots:

| Instance slot | Table entry / target | Behavior |
|---|---|---|
| `+0x568` | `0xfffffff006c7b90c` | If byte `this+0xec` is set, return `0xe00002c7`. Otherwise obtain/cache an object at `this+0xf0` through `this+0xd8`'s vtable `+0xe8`, then call the cached object's vtable `+0x80` with `(arg1,arg2,0)`. |
| `+0x570` | `0xfffffff006c7b998` | Same pattern using byte `this+0xed`, cache at `this+0xf8`, and call the cached object's vtable `+0x80` with `(arg1,arg2,arg3)`. |

The `start` implementation at `0xfffffff006c7b1f0` sets those two flag bytes
when `no-clock-gate` or `no-power-gate` is present. It resolves and registers
`function-clock_gate` only when `no-clock-gate` is absent, and similarly
resolves/registers `function-power_gate` only when `no-power-gate` is absent.
The wrapper functions above are recovered direct targets for the vtable
slots. Their final call target remains an indirect `+0x80` on the
retained/cached backing object; the static cache does not identify that
object's concrete runtime vtable. No live object was read.

The AGX G4G personality's `IOProviderClass=AppleARMIODevice` is a superclass
constraint, not runtime proof that the live `sgx` provider is exactly
`AppleT7001IO`. Static evidence establishes the T7001 subclass registration
and its overrides; it does not establish that this personality matched that
class on a device or which concrete object services its indirect `+0x80`
calls. No device/runtime inspection was performed. The earlier 68-entry and
22-entry pointer arrays at `0xfffffff006d0d3a8` and `0xfffffff006d0d618` remain
unattributed and are not used as evidence.
