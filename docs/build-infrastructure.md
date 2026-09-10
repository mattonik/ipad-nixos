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

## Why this needed its own writeup, 2026-09-10

This VM was originally started with a long ad-hoc `nix run --impure --expr
...` one-liner, never committed anywhere, and its resource settings only
existed as a single prose line in `docs/project-status.md` ("4 CPUs, 8 GB
RAM, 40 GB disk"). When the VM got killed and someone tried to bring it back
with the obvious-looking `nix run nixpkgs#darwin.linux-builder-vz`, that
command silently created a **different, fresh, 1-CPU/3 GB-RAM/20 GB-disk VM**
in the wrong directory instead of reattaching the real one -- `vzvm`'s
resource settings and disk location are baked into the derivation and its
runtime working directory, not something a bare `nix run` rediscovers. The
symptom was a confusing "No space left on device" failure while just copying
kernel source, which took real diagnostic work to trace back to "wrong VM
entirely" rather than "not enough space." This doc exists so that never has
to be re-derived.

## Where the persistent state lives

`vzvm` (the actual VM runner nixpkgs' `linux-builder-vz` wraps) keeps its
disk images next to wherever it's *run from*: `${VZVM_STATE_DIR:-$PWD}`.
It creates `store-<hash>.img` (read-only Nix store image, rebuilt from
scratch each time the package's closure changes) and `nixos.qcow2` (the
writable data disk -- this is where all the actual persistent state lives)
in that directory, plus a regenerated `vzvm.json` on every run.

**The real, persistent 40 GB disk lives in `/Users/martinp/`** (`nixos.qcow2`,
`store-*.img`, `vzvm.json`, `keys/`) -- none of that is in this repo (VM
images, keys and generated build outputs are deliberately not committed, see
`docs/project-status.md`'s "Repository hygiene"). **You must run
`create-builder` from that exact directory** (or with
`VZVM_STATE_DIR=/Users/martinp`), or it will create a fresh, empty disk
somewhere else instead of reattaching this one.

## Resource sizing, and why

- **4 CPUs** -- matches the Nix machine spec (`ssh-ng://builder@linux-builder
  ... 4 1 ...`) already registered in `/etc/nix/machines`, so parallel build
  jobs the daemon schedules actually get cores.
- **8 GB RAM, not 12 GB** -- a stray note once suggested bumping to 12 GB, but
  the live, working `vzvm.json` has only ever said 8192 MiB, and there is no
  evidence 8 GB is insufficient: every real failure seen so far has been
  disk-space exhaustion (`cp: ... No space left on device` while copying
  kernel source), which looks nothing like an OOM (`cc1: out of memory`,
  process killed by signal 9). On a 16 GB host already running Colima's own
  VM, 12 GB would leave only ~4 GB for macOS itself -- risky for host
  stability for a problem that hasn't actually been observed. Revisit only if
  a real OOM shows up during compilation, not preemptively.
- **40 GB disk** -- the default (`virtualisation.darwin-builder.diskSize`) is
  only 20 GB, which is not enough headroom for a from-scratch Hoolock kernel
  source checkout (source copy + build objects + module tree); 40 GB is the
  size that was actually validated as sufficient.

## Building and running it

The exact configuration is a flake output (`flake.nix`'s
`packages.aarch64-darwin.linux-builder`), pinned against its own,
separately-tracked `nixpkgsBuilder` flake input -- the project's main
`nixpkgs` input predates `darwin.linux-builder-vz`'s addition to nixpkgs, so
this needed a newer, independent pin that can't disturb the kernel/initramfs
build pins.

```bash
nix build .#packages.aarch64-darwin.linux-builder -o result-linux-builder
cd /Users/martinp && /path/to/result-linux-builder/bin/create-builder
```

Leave that running in its own terminal tab (or background it with
`nohup ... &`); it prints `[vzvm] guest started` once up. Verify it's
actually the right one before relying on it:

```bash
sudo ssh builder@linux-builder df -h
```

should show the real disk with tens of GB free, not a ~1.5 GB tmpfs root.

**Do not** use a bare `nix run nixpkgs#darwin.linux-builder-vz` -- it uses
whatever `nixpkgs` the flake registry resolves to that day, defaults to
1 CPU / 3 GB RAM / 20 GB disk, and creates its state wherever the shell
happens to be `cd`'d, silently diverging from the real setup above.

## Cleaning up a wrong VM's leftover files

If a wrong invocation created stray `nixos.qcow2` / `store-*.img` /
`vzvm.json` / `keys/` files in some other directory, they're safe to delete
outright -- they hold no state worth keeping, just an empty/fresh Nix store
for a VM that was never the real builder. Only ever delete the *wrong*
location's files; never touch `/Users/martinp/nixos.qcow2`.
