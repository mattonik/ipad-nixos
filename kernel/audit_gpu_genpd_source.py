#!/usr/bin/env python3
"""Check the exact pinned kernel sources used by the GFX power prototype."""
import argparse
from hashlib import sha256
from pathlib import Path
import re

EXPECTED = {
    "drivers/pmdomain/core.c": "32e2f6b0988eba52a2f662fdc2d7132022fbe980f281b2a82babcf3d7f46e18a",
    "drivers/pmdomain/apple/pmgr-pwrstate.c": "4b0adc3013e2fabe9ca1cb8228f8f6b7934af4b667f7f0f893b675102d8710df",
    "drivers/base/power/runtime.c": "3ba6c4baf1adeaa90043f46db08dfc9df2809209b4e29386e9148d26da827a9a",
    "include/linux/pm_runtime.h": "1c1383101d72ce3028df6d9ad3640c2020a041f5c1820b1698d1657b648b04f6",
    "drivers/base/core.c": "52247f436f5328d0b174f3350cda7e6d3e9d929de3611b5acb546b502852de2c",
}


def function(source, name):
    match = re.search(r"\b" + re.escape(name) + r"\([^;]*?\)\s*\{", source, re.S)
    if not match:
        raise ValueError(f"missing function {name}")
    start = match.end() - 1
    depth = 0
    for pos in range(start, len(source)):
        depth += (source[pos] == "{") - (source[pos] == "}")
        if not depth:
            return source[start:pos + 1]
    raise ValueError(f"unclosed function {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="pinned kernel source tree")
    args = parser.parse_args()
    sources = {}
    for name, expected in EXPECTED.items():
        data = (args.source / name).read_bytes()
        if sha256(data).hexdigest() != expected:
            raise ValueError(f"source fingerprint mismatch: {name}")
        sources[name] = data.decode()
    core = sources["drivers/pmdomain/core.c"]
    provider = sources["drivers/pmdomain/apple/pmgr-pwrstate.c"]
    def require(condition, detail):
        if not condition:
            raise ValueError(detail)
    direct = function(core, "of_genpd_add_device")
    add = function(core, "genpd_add_device")
    require("genpd_add_device(genpd, dev, dev)" in direct and "genpd_power_on(" not in direct, "direct attach changed")
    require("genpd->attach_dev ? genpd->attach_dev" in add and "genpd_power_on(" not in add, "add-device path changed")
    require("genpd->get_hwmode_dev ? genpd->get_hwmode_dev" in add, "hardware-mode callback changed")
    for callback in ("attach_dev", "get_hwmode_dev", "start", "stop"):
        require(not re.search(r"(?:\.|->)" + callback + r"\s*=", provider), f"provider sets {callback}")
    require("ps->genpd.power_on = apple_pmgr_ps_power_on" in provider, "power-on callback changed")
    require("ps->genpd.power_off = apple_pmgr_ps_power_off" in provider, "power-off callback changed")
    require("of_genpd_add_provider_simple(node, &ps->genpd)" in provider, "provider registration changed")
    get = function(sources["include/linux/pm_runtime.h"], "pm_runtime_get_sync")
    resume = function(sources["drivers/base/power/runtime.c"], "__pm_runtime_resume")
    allowed = function(sources["drivers/base/power/runtime.c"], "rpm_check_suspend_allowed")
    require("__pm_runtime_resume(dev, RPM_GET_PUT)" in get, "runtime get semantics changed")
    require("atomic_inc(&dev->power.usage_count)" in resume and "atomic_dec" not in resume, "runtime reference handling changed")
    require("atomic_read(&dev->power.usage_count)" in allowed and "retval = -EAGAIN" in allowed, "runtime suspend gate changed")
    root = function(sources["drivers/base/core.c"], "__root_device_register")
    require("kzalloc_obj(struct root_device)" in root and "device_register(&root->dev)" in root, "root-device construction changed")
    for field in ("bus", "class", "type", "driver", "parent"):
        require(not re.search(r"root->dev\." + field + r"\s*=", root), f"root device sets {field}")
    print("PASS: pinned genpd attach, provider callbacks, root device and runtime-PM reference assumptions")


if __name__ == "__main__":
    main()
