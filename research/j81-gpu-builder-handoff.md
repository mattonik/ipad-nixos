# J81 GPU build-agent handoff

The next Linux probe records the GFX power-domain setter's own old word, request, successful poll and optional auto-enable request. Build it on the existing x86_64 Linux/Nix builder. In parallel, audit each retained working iPadOS archive for the corresponding transition. The first GPU milestone is a repeatable Linux identity result of `0x00070500`. This handoff ends with a kernel build and an evidence report. It requires no connected iPad.

## Get exactly the sender's revision

Use bash from a directory where you can create a fresh checkout. Set `GPU_REV` to the **full 40-character commit** provided in the handoff message. Keep the existing in-place checkout and private archives where they are.

```bash
set -eu
: "${GPU_REV:?export GPU_REV to the sender's commit first}"
umask 077
JOB=$(mktemp -d "${TMPDIR:-/tmp}/j81-gfx.XXXXXXXX")
git clone --single-branch --branch research/j81-next-gpu https://github.com/mattonik/ipad-nixos.git "$JOB/repo"
cd "$JOB/repo"
git checkout --detach "$GPU_REV"
test "$(git rev-parse HEAD)" = "$GPU_REV"
mkdir "$JOB/results"
printf 'Private job directory: %s\n' "$JOB"
```

If this computer is air-gapped, on a computer with GitHub access clone the branch above and run `git bundle create j81-gpu.bundle refs/heads/research/j81-next-gpu` inside the clone. Transfer that bundle using your normal file transfer. Substitute its absolute path for the HTTPS URL in the clone command. Use the same commit check. Keep the results directory until you have returned the report.

## Build and check on the host

Git and Python 3 run the recorder tests. The actual driver-function test also uses a C11 compiler and `patch`. Run these commands in the new checkout in the same shell.

```bash
python3 tools/test_audit_gpu_store_export.py
python3 tools/test_gpu_gfx_transition.py
python3 research/probes/j81-thread/test_sample_window.py
```

For the C test, set `PMGR_SRC` to the absolute path of the **unpatched** pinned file in your Hoolock source cache. If it is absent, on a connected host use the following to obtain it. This single file can travel alongside the Git bundle.

```bash
if [ -z "${PMGR_SRC:-}" ]; then
  PMGR_SRC="$JOB/pmgr-pwrstate.c"
  curl -fsSL https://raw.githubusercontent.com/HoolockLinux/linux/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/pmdomain/apple/pmgr-pwrstate.c -o "$PMGR_SRC"
fi
python3 - "$PMGR_SRC" <<'PY'
import hashlib, pathlib, sys
digest = hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()
if digest != "4b0adc3013e2fabe9ca1cb8228f8f6b7934af4b667f7f0f893b675102d8710df":
    sys.exit("unexpected Hoolock source digest: " + digest)
PY
python3 kernel/test_gpu_pmgr_failure_patch.py --source "$PMGR_SRC" --trace-gfx
```

Expect a PASS for each Python test and two PASS lines for the C test. It applies the existing error-handling patch and the new observer with zero fuzz, compiles the real setter and drives it with a simulated regmap. It checks `old=00000300 request=0000000f poll=000003ff auto=1 auto_word=100000ff rc=0`, the off case, error paths and filtering of an unrelated domain. The test also checks register access counts.

On the project's x86_64 Linux Nix builder with the pinned flake inputs available, build **only the observer kernel**. This uses the project's existing cycle kernel recipe. Save the output store path and image hash. The default recipe selects the original driver unless explicitly given `traceGfxRequests = true`. The Git bundle contains project sources. Air-gapped Nix builds also need the existing input and toolchain cache.

```bash
nix --extra-experimental-features 'nix-command flakes' build --impure --out-link "$JOB/results/kernel" --print-out-paths --expr '
  let repo = builtins.toPath (builtins.getEnv "PWD");
  in (import (repo + "/kernel/gpu-pmgr-cycle/build.nix") {
    inherit repo;
    traceGfxRequests = true;
  }).kernel' > "$JOB/results/kernel-path.txt"
GFX_KERNEL=$(cat "$JOB/results/kernel-path.txt")
test -s "$GFX_KERNEL/Image"
sha256sum "$GFX_KERNEL/Image" > "$JOB/results/kernel-image.sha256"
```

If the build fails, return the first relevant Nix or compiler error and the derivation path. Continue the archive work independently. A printed `gfx-request` row in a future Linux log describes a setter that reached its successful poll. `auto=0` means there was no automatic-management write, and `auto_word` is then a placeholder. When `auto=1`, `rc` is the status of the last write. Earlier failures return before logging. A missing row cannot identify a skipped setter, failed access or lost message. The PID is the task executing the setter. Use independent task attribution before marking a normalized event as same-thread. Logging can affect timing between setter calls. [Observer patch](probes/j81-linux-gfx-request.patch)

## Audit the three working-device archives

Use the November 17 local captures individually. The published candidates are 10:24 for the prefix, 10:45 for the clock tail and 12:01 for the combined clock/power tail. Verify each boot alias, board, OS build, producer binary SHA-256 and source revision from the private build records. Confirm the actual formatter is the sampled version before interpreting O as staged slots. Retain the export and binary privately. On a Mac, run the following once per archive after setting `ARCHIVE` to its absolute .logarchive path and `LABEL` to the matching alias (prefix, clock-tail, or combined-tail). A Linux builder can use the Mac's per-boot plain-text exports and run the last command directly.

```bash
: "${ARCHIVE:?set an archive path}" "${LABEL:?set its unique boot alias}"
/usr/bin/log show --style syslog --info --debug --archive "$ARCHIVE" \
  --predicate 'eventMessage CONTAINS " M"' > "$JOB/results/$LABEL.messages"
python3 tools/audit_gpu_store_export.py "$JOB/results/$LABEL.messages" > "$JOB/results/$LABEL.coverage.json"
```

Keep entire chronological header/payload lines, including batches with zero ordinary rows. Validate the export against its original messages and report any checker error. With a confirmed skip-32 producer, O=32 and 17 printed ordinary rows leave 15 staged slots unaccounted for. Report each boot separately. An ordinary row tagged `80000000` carries no measured instance or thread. If archives are unavailable, list the missing aliases or producer hashes and return the public test and kernel build results.

## Compare and report

If saved observations independently identify region 0, offset `0x20320` and instance 0, use one chronological JSONL file per boot. The schema and a synthetic input are in the [recorder instructions](2026-11-18-j81-gfx-transition-builder.md#host-recorder-and-local-comparison). Record unknowns explicitly. Only provide zero loss if the producer establishes coverage of all potential target events over the chosen window. The Linux setter observer alone cannot establish this. A single stock trace works without a Linux counterpart.

```bash
: "${STOCK_JSONL:?set a verified working-boot trace}"
if [ -n "${LINUX_JSONL:-}" ]; then
  python3 tools/gpu_gfx_transition.py "$STOCK_JSONL" "$LINUX_JSONL" > "$JOB/results/transition.json"
else
  python3 tools/gpu_gfx_transition.py "$STOCK_JSONL" > "$JOB/results/transition.json"
fi
```

Return a short text report to the sender. Include the repository SHA, host tests, kernel store path and Image SHA-256 or the build error. For each boot give the alias, producer SHA/revision, staged/printed/missing counts and any GFX word. For each attributable transition give its order, caller, thread, old/request/poll/auto words, result and loss/control status. Report the earliest difference and any coverage gap. Keep raw archives, device identifiers and binaries local.

* If the only difference is the post-poll ACTUAL nibble, record it and pursue the first differently ordered reset, clock or fabric dependency upstream of the identity read.
* If stock has a distinct target, auto-disable, or off/on edge, establish its caller, width and starting state. That transition becomes the candidate for a separate Linux experiment.
* If stock coverage is incomplete, name the earliest missing observation. A new kernel build, a matching endpoint, or the static words in the table cannot fill it. The next capture should target that observation.

[Exact-board register comparison](2026-11-18-j81-gfx-state-word-comparison.md) · [Previous working identity and Linux checkpoint](2026-11-10-j81-ios-linux-poll-result.md)
