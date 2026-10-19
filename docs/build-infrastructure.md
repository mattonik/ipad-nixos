# macOS Linux-builder VM

> **RUNBOOK: the Linux builder VM** (any agent: read this instead of guessing; details further down)
> - **Status / start / stop:** `tools/builder.sh status`, `tools/builder.sh start`, `tools/builder.sh stop` (run from anywhere; the script works from inside the repo, which is where the VM's disk lives).
> - **Start by hand:** `cd` into the repo root, `nix build .#packages.aarch64-darwin.linux-builder -o result-linux-builder` once, then `./result-linux-builder/bin/create-builder` (background it; ready when `ssh -i keys/builder_ed25519 -p 31022 builder@localhost true` works, about 1 minute).
> - **Stop:** no build running; `ssh -i keys/builder_ed25519 -p 31022 builder@localhost sync`; `kill -TERM <pid of vzvm>` (clean guest shutdown in 30-90 s). Never SIGKILL while builds run (corrupted the disk once). The guest's `sudo` needs a password, so do not try an in-guest poweroff.
> - **BEFORE ANY NEW LINUX BUILD (decision tree for an agent):** run `tools/builder.sh status`. (1) `vzvm: running` and `login as builder: ok` -> build. (2) `vzvm: not running` and `disk: ... GB used` -> `tools/builder.sh start`, build, and when the session's builds are done offer to `stop` it. (3) `disk: none in ... (archived?)` -> the VM was parked on the NAS (latest archive: `/Volumes/martin/Projects/Archive/ipad-nixos/latest` names the folder): check the NAS is mounted (`ls /Volumes/martin/Projects/Archive`), `tools/builder.sh restore -n` for the plan, `tools/builder.sh restore` (needs about 21 GB free locally; a non-root Nix prints one `sudo nix ... copy --from file://... --no-check-sigs <paths>` command for the owner to run, then re-run the restore), then `tools/builder.sh start`. Do NOT start the VM while the disk is missing: the launcher silently creates a fresh EMPTY VM (hours of cold rebuilds, no cached outputs). After the work, tell the owner and offer `tools/builder.sh stop` and `tools/builder.sh archive --delete-local` to free the local disk again (the old archive can then be removed by the owner).
> - **Cold storage on the NAS:** `tools/builder.sh archive [-n] [--delete-local [--yes]]` copies the VM to `/Volumes/martin/Projects/Archive/ipad-nixos/linux-builder-<timestamp>/` (zstd disk ~16 GB used, keys, `vzvm.json`, a self-contained Nix file cache of the launcher and guest system so a restore does not depend on cache.nixos.org, checksums verified by reading everything back), and `tools/builder.sh restore [-n] [--from DIR] [--to LOCAL_DIR] [--force]` brings it back to a **local** directory (refuses network storage), verifies it, rebuilds the disk and imports missing store paths (a non-root Nix may need one printed `sudo nix copy ...` command), then start with `BUILDER_DIR=<dir> tools/builder.sh start`. The VM is never run from the NAS. The VM is stopped for both. Override locations with `BUILDER_ARCHIVE` / `BUILDER_DIR`.
> - **Never** run a bare `nix run nixpkgs#darwin.linux-builder-vz` (creates a different, empty VM in the current directory).
> - **Offline = Linux builds fail** with a connection error to `ssh-ng://builder@linux-builder` (listed in `/etc/nix/machines`). It is not a launchd service, so nothing restarts it. Current state is whatever `tools/builder.sh status` says; as of 2026-10-19 it was stopped on purpose by the project owner, so do not start it unless the task needs a Linux build, and say so when you do.


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
`~/nixos.qcow2` (dated 2026-09-01, `vzvm.json` showing 4
CPUs/8 GB/40 GB, matching project-status.md's prose exactly) -- reasonable,
but wrong. Bumped to 80 GB when even 40 GB wasn't enough for a fully *cold*
from-scratch build (no cache at all on that disk), then hit three
consecutive segfaults on the fresh 80 GB disk (`nix-daemon --stdio` itself,
then the kernel build process twice, increasingly fast/reproducible).

**Second correction:** the actual disk that was "working just fine
yesterday" (2026-09-09) was never `~/`'s -- it was
`ipad-nixos/nixos.qcow2` right here in the repo, already holding 31 GB of
*warm* store data from real prior work, with its own `vzvm.json` showing
**12 GB RAM** (matching a note found in terminal history that had been
wrongly dismissed as stale, because the wrong file had been checked).
Reattaching that warm, gitignored, in-repo disk -- even kept at 8 GB RAM,
by explicit choice, not 12 -- immediately fixed the segfaults. **The
`~/` copy is superseded and likely safe to remove eventually**;
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

## Disk exhaustion from many builds in one session, 2026-09-25

Five full kernel builds back-to-back in one overnight session (PCIe
Stages 1-4a, then the charging Stage 2 test) filled the VM's 40 GB disk:
the 5th build (`m1n1-hoolock-charging-writable-test`) failed mid-`rsync`
with `No space left on device`, not a code or patch error -- `nix build`
still printed `[exited with code 0]` in its own wrapper output because
that's the exit code of the `tee` pipeline, not of the underlying build;
always check the log body for `error:`, not just the reported exit code,
when a build result looks suspiciously fast or thin. This is **not** the
previously-documented `CONFIG_DEBUG_INFO` cause (confirmed already
disabled in `patchedHoolockConfig`, `flake.nix:171-173`) -- just ordinary
accumulated store paths from several real builds never garbage-collected
in between.

**Recovery needs the operator's own credentials and hasn't been run
yet.** `nix store gc`/`nix-collect-garbage` on the builder needs either
`sudo ssh builder@linux-builder '...'` (interactive password) or `nix
store gc --store ssh-ng://builder@linux-builder` (which, tried directly,
still fails with `Load key "/etc/nix/builder_ed25519": Permission
denied` -- that key is root-owned; regular `nix build` invocations work
because the nix-daemon, running as root, makes the delegated-builder SSH
connection on the caller's behalf, but a direct client-side `nix store
gc --store ssh-ng://...` does not go through that same daemon-mediated
path and tries to read the key with the calling user's own
permissions). An autonomous session without interactive sudo access
cannot self-recover from this -- flag it and wait for the operator
rather than attempting to work around the credential boundary.

## GC-vs-build race can corrupt a store path on both ends, 2026-09-25

Running `nix-collect-garbage` on the builder VM *while* a `nix build` is
in flight can delete an intermediate derivation's output file(s) after
Nix has already registered that path as valid but before a downstream
derivation reads it back -- a real gap in Nix's temp-root protection
during that handoff, not something specific to this project's kernel
builds. Symptom: a build fails with a file genuinely missing from a
store path (e.g. `gzip: .../Image: No such file or directory`), and
retrying just reproduces the same failure -- Nix trusts its database
that the path is valid and never re-verifies file-by-file, so it either
skips rebuilding entirely or (worse) copies the same incomplete bits
from wherever else it exists.

The corruption can exist on **both** the local (invoking) machine and
the remote builder simultaneously, since build outputs get copied back
to the local store as they complete. Fixing only one side causes the
other to re-corrupt it on the next attempt (the still-broken side gets
copied to the just-fixed side). The reliable fix, needing the
operator's `sudo` on both ends:

```bash
# remote builder first
sudo ssh builder@linux-builder 'nix-store --delete <bad-path> <bad-path>-dev'
# then local
sudo nix-store --delete <bad-path> <bad-path>-dev
```

Order matters -- fixing local first just lets a subsequent retry
re-fetch the still-broken bits from the remote. `nix-store --delete`
will name any other referencing output (e.g. a `-modules` split) it
refuses to delete alongside; add those to the command. Confirm success
from the printed output (`N store paths deleted, ... freed`), not just
the absence of an error -- and don't trust a `--repair` shortcut here,
since that flag requires `trusted-users` membership neither the
operator's shell account nor an autonomous session has by default on
this setup.

## Stopping and parking the builder (2026-10-19)
The builder is not a launchd service; it is whatever shell started `create-builder`. To park it: run `sync` in the guest (`ssh -i keys/builder_ed25519 -p 31022 builder@localhost sync`; the guest's `sudo` needs a password, so an in-guest `poweroff` is not available without it), make sure no `nix build` is running, then `kill -TERM` the `vzvm` process: the Virtualization framework's stop request shuts the guest down cleanly in about 30 seconds and the launcher exits with it. The port 31022 listener disappears. While it is stopped, builds of Linux derivations fail to reach `ssh-ng://builder@linux-builder` (it is listed in `/etc/nix/machines`); darwin builds are unaffected. Start it again with the procedure above, from inside this directory. Do not SIGKILL it while builds are running (that corrupted the disk once).

## Lessons from the first NAS archive (2026-10-19)
- `nix copy --to file://<dir on an SMB share>` fails with `filesystem error: in rename: File exists`: it writes NAR files in parallel and several store paths share identical contents, and SMB refuses the rename onto an existing file. The archive command therefore builds the Nix file cache on the local disk and `rsync`s it to the NAS; keep it that way.
- The VM disk compresses very well (17 GB used -> 3.8 GB with `zstd -3`); the NAS copy over Tailscale-reached SMB took roughly ten minutes for the disk.
- A wrapper such as `cmd | tee log` hides the script's exit status behind `tee`'s: read the script's own `script_exit` or the log, not the background task's "exit code 0".
- The archive never touches the local files until the read-back verification passes; a failed run removes only its own half-written NAS directory.
- Never run the VM from the NAS (SMB latency and link drops risk corrupting the qcow2); restore to a local directory.

