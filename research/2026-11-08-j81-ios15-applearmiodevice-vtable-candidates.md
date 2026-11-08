# J81 iOS 15 AppleARMIODevice vtable candidates

Date: 2026-11-08. Bounded offline inspection of the local iPadOS 15.8.8
kernelcache (`artifacts/live/private/gpu-offline/ios15-kernel`). No device,
build, or MMIO access.

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
and power gate arrays, confirming that the slot wrappers use a retained
backing/controller object. The local iOS15 prelink inventory declares
`arm-io,t7001` as `AppleT7001IO`, so that class is the expected J81 controller
given the device-tree parent relationship. This pass did not trace the exact
call that supplies the `+0x88` argument or read that field from a live object;
the receiver's runtime vptr and terminal `+0x568/+0x570` targets remain
unresolved.

Likewise, the AGX G4G personality declares `IOProviderClass=AppleARMIODevice`,
which is a provider-class constraint, not proof of an exact dynamic class.
The recovered instance table is the base AppleARMIODevice implementation. A
runtime subclass could override these slots; the local static evidence here
does not establish the live `sgx` provider's dynamic class or rule out such an
override. No device/runtime inspection was performed. The earlier 68-entry
and 22-entry pointer arrays at `0xfffffff006d0d3a8` and
`0xfffffff006d0d618` remain unattributed and are not used as evidence.
