# macOS Linux-builder VM

Host: Apple Silicon Mac, aarch64-darwin, **16 GB total RAM**, running Colima's
own Docker VM concurrently. aarch64-darwin cannot build `x86_64-linux` or
`aarch64-linux` derivations directly, so every kernel/initramfs/payload build
in this flake (`nix build .#packages.x86_64-linux....`) is delegated to a
Linux VM running on the same Mac via Apple's Virtualization.framework
(`darwin.linux-builder-vz`), reached over SSH at `builder@linux-builder`
(`127.0.0.1:31022`, configured in `/etc/nix/machines` and
`/etc/ssh/ssh_config.d/100-linux-builder.conf` -- both outside this repo,
set up by Determinate Nix).

## The canonical setup, as of 2026-09-10

**Run it from inside this repo's own directory.** The persistent VM state
(`nixos.qcow2`, `store-*.img`, `vzvm.json`, `keys/`) lives right here in
`ipad-nixos/` -- already covered by `.gitignore` (`*.qcow2`, `*.img`,
`vzvm.json`, `keys/`), so this is the deliberate, intended location, not an
accident.

```bash
nix build .#packages.aarch64-darwin.linux-builder -o result-linux-builder
cd /path/to/ipad-nixos && /path/to/result-linux-builder/bin/create-builder
```

Leave that running in its own terminal tab (or background it with
`nohup ... &`); it prints `[vzvm] guest started` once up. Settings: **4 CPUs,
8 GB RAM, 40 GB disk** (`flake.nix`'s `packages.aarch64-darwin.linux-builder`,
pinned against a dedicated `nixpkgsBuilder` flake input -- the project's main
`nixpkgs` predates `darwin.linux-builder-vz`'s addition to nixpkgs, so this
needed its own newer pin that can't disturb the kernel/initramfs build pins).

Sanity-check before relying on it:

```bash
sudo ssh builder@linux-builder 'nix-daemon --stdio < /dev/null; echo exit=$?; free -h'
```

`exit=1` with `error: unexpected end-of-file` is the *normal*, benign
response (no real client on the other end) -- that is not a crash. A
`Segmentation fault` (`exit=139`) is a real problem; see "The segfault
round" below.

## Why this needed its own writeup, and two follow-up corrections

**2026-09-10, original problem:** this VM had only ever been started with a
long ad-hoc `nix run --impure --expr ...` one-liner, never committed
anywhere, its resource settings recorded as a single prose line in
`docs/project-status.md`. When it was killed and restarted with the
obvious-looking `nix run nixpkgs#darwin.linux-builder-vz`, that silently
created a **different, fresh, 1-CPU/3 GB-RAM/20 GB-disk VM** in the wrong
directory (`vzvm`'s disk location is keyed on `${VZVM_STATE_DIR:-$PWD}` at
runtime, not baked into the package) -- surfacing as a confusing "No space
left on device" failure while just copying kernel source.

**First correction:** the "real" disk was assumed to be
`/Users/martinp/nixos.qcow2` (dated 2026-09-01, `vzvm.json` showing 4
CPUs/8 GB/40 GB, matching project-status.md's prose exactly) -- reasonable,
but wrong. Bumped to 80 GB when even 40 GB wasn't enough for a fully *cold*
from-scratch build (no cache at all on that disk), then hit three
consecutive segfaults on the fresh 80 GB disk (`nix-daemon --stdio` itself,
then the kernel build process twice, increasingly fast/reproducible).

**Second correction:** the actual disk that was "working just fine
yesterday" (2026-09-09) was never `/Users/martinp/`'s -- it was
`ipad-nixos/nixos.qcow2` right here in the repo, already holding 31 GB of
*warm* store data from real prior work, with its own `vzvm.json` showing
**12 GB RAM** (matching a note found in terminal history that had been
wrongly dismissed as stale, because the wrong file had been checked).
Reattaching that warm, gitignored, in-repo disk -- even kept at 8 GB RAM,
by explicit choice, not 12 -- immediately fixed the segfaults. **The
`/Users/martinp/` copy is superseded and likely safe to remove eventually**;
`ipad-nixos/` is the real one going forward.

Net effect: it's genuinely unclear whether the segfaults were caused by too
little RAM, or by something about a completely fresh/empty disk under a
heavy cold build, since both variables changed together when the fix
landed. If a segfault (not disk space, not the benign EOF above) shows up
again on the warm disk, that would isolate it -- until then, don't assume
it's memory pressure.

## Resource sizing, and why

- **4 CPUs** -- matches the Nix machine spec (`ssh-ng://builder@linux-builder
  ... 4 1 ...`) already registered in `/etc/nix/machines`, so parallel build
  jobs the daemon schedules actually get cores.
- **8 GB RAM** -- kept deliberately below the 12 GB that yesterday's disk was
  actually built with, because the host only has 16 GB total and Colima's
  own VM runs concurrently; 12 GB would leave ~4 GB for everything else. Not
  yet proven necessary to go higher -- see the segfault history above for
  why that's a real "not yet proven", not a confident "8 GB is enough".
- **40 GB disk** -- the default (`virtualisation.darwin-builder.diskSize`) is
  only 20 GB, not enough headroom for a from-scratch Hoolock kernel build
  (source copy + build objects + module tree + the final vmlinux/kallsyms
  link step, which needs several full temporary copies of the kernel image
  at once). 40 GB is sparse-allocated (`dd ... seek=N`, no real blocks up
  front), so it costs nothing until actually written to.

## Do not

Use a bare `nix run nixpkgs#darwin.linux-builder-vz` -- it uses whatever
`nixpkgs` the flake registry resolves to that day, defaults to 1 CPU/3 GB
RAM/20 GB disk, and creates its state wherever the shell happens to be
`cd`'d, silently diverging from the real setup above. This was the original
2026-09-10 mistake, twice.

## Cleaning up a wrong VM's leftover files

If a wrong invocation created stray `nixos.qcow2` / `store-*.img` /
`vzvm.json` / `keys/` files in some other directory, they're safe to delete
outright -- they hold no state worth keeping, just an empty/fresh Nix store
for a VM that was never the real builder. Only ever delete the *wrong*
location's files; never touch the canonical `ipad-nixos/` copy without
first confirming (`ps aux | grep vzvm`, check which `vzvm.json` path it's
running) that nothing is actively using it.
