# iPadOS 15 cross-check: `IOAccelSysMemory`

The private iPadOS 15 kernel artifact contains multiple `IOAccelSysMemory`
class strings and constructors, confirming that the same accelerator memory
family continued into the newer driver generation.  However, the available
iOS 15 extraction does not preserve a resolvable cross-reference from the
J81-style selector path to a descriptor `+0xa8` implementation: the relevant
vtable entries are stripped/relocated and the AGX decompilations do not expose
the older `0x90007` call chain.

This is useful corroboration of the class family, not a recovered address
policy.  The J81 result remains fail-closed: the descriptor-specific address
method and DART ownership are still unresolved.
