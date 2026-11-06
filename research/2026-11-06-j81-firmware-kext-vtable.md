# J81 AGXFirmwareKextG4G vtable extraction

The kernelcache prelink metadata identifies `AGXFirmwareKextG4G` as a
separate kext at `0xffffff8002e38000` with a `0x25000` executable span. Its
prelink text was extracted into the ignored private artifact
`AGXFirmwareKextG4G.raw` and imported into a separate Ghidra project.

The kext constructors store vptr `0xffffff8002e50080`. The table entry at
`vptr + 0xc0` is `0xffffff80023aa078`, resolved by the preserved kernelcache
symbols as `IORegistryEntry::setProperty(const char *, OSObject *)`.

This explains why the main AGX kext's base vtable showed a pure-virtual slot:
the concrete firmware class lives in the separate firmware kext. It also
corrects the earlier assumption that the final J81 `+0xc0` call is necessarily
a firmware-start method. The exact runtime object/vptr at that call still
needs a cross-kext provenance proof; no firmware execution or hardware access
was performed.
