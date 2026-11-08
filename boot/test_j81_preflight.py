#!/usr/bin/env python3
"""Run j81_preflight.sh against saved transcripts; no device access."""
import os
import subprocess
import tempfile
from pathlib import Path

script = Path(__file__).with_name("j81_preflight.sh")
GPU = "82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014"


def run(test, facts, complete=True):
    body = "/ # junk\nPF_BEGIN\n" + "".join(f"{k}={v}\n" for k, v in facts.items())
    if complete:
        body += "PF_END\n/ # "
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(body)
    try:
        env = dict(os.environ, PREFLIGHT_TRANSCRIPT=f.name)
        r = subprocess.run(["bash", str(script), test], env=env, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return r.returncode, r.stdout


base = dict(NOTES=GPU, DT_GUARD="yes", MOD_PMGR_ONCE="no", PMGR_ONCE_DEV="no",
            DEVMEM="yes", MODULES="", UPTIME="12.0", TMP="")
rc, out = run("gpu-pmgr-once", base)
assert rc == 0 and "GO: gpu-pmgr-once" in out, out
# Today's case: GPU kernel but the MCC payload's device tree.
rc, out = run("gpu-pmgr-once", dict(base, DT_GUARD="no", MODULES="mcc_read_once,"))
assert rc == 1 and "FAIL dt-guard" in out and "NO-GO" in out, out
rc, out = run("gpu-pmgr-once", dict(base, NOTES="0" * 64))
assert rc == 1 and "FAIL kernel" in out, out
rc, out = run("gpu-pmgr-once", dict(base, MOD_PMGR_ONCE="yes"))
assert rc == 1 and "FAIL module-loaded" in out, out
rc, out = run("perf-peek", dict(base, DT_GUARD="no"))
assert rc == 0 and "GO: perf-peek" in out, out
rc, out = run("perf-peek", dict(base, DEVMEM="no"))
assert rc == 1, out
rc, out = run("gpu-pmgr-once", base, complete=False)
assert rc == 1 and "no complete answer" in out, out
assert subprocess.run(["bash", str(script), "bogus"], capture_output=True).returncode == 2
print("PASS: preflight go/no-go decisions")
