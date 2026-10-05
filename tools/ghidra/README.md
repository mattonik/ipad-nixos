# Ghidra helpers for the iOS 8.1 kernelcache work

Headless recipe (project and flat import live in the scratch directory, never in git):

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless PROJECT_DIR prelinktext \
  -process PRELINK_TEXT.raw -noanalysis -scriptPath /ABSOLUTE/path/to/tools/ghidra \
  -postScript DecompTo.java /tmp/out.c ffffff8002beb264
```

`-scriptPath` must be absolute. `PRELINK_TEXT.raw` is the kernelcache's `__PRELINK_TEXT` imported
as raw AArch64 at base `0xffffff8002593000` (iPad5,3 12B410).

| Script | Use |
| --- | --- |
| `FindXrefs.java ADDR...` | Ghidra reference manager hits for addresses |
| `FindImm.java START END LO HI` | instructions with a scalar operand in a range (e.g. struct offsets) |
| `DecompTo.java OUT ADDR...` | decompile the functions containing the addresses to a file |
| `DecompRangeTo.java OUT START END` | decompile every defined function in a range |
| `MakeFuncDecomp.java OUT ADDR...` | disassemble, create a function at each address, decompile (for code Ghidra never made a function of) |
| `find_adr_refs.py RAW BASE TARGET...` | brute-force ADR references to strings (catches what xrefs miss) |
