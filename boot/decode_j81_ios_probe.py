#!/usr/bin/env python3
"""Decode the J81_BOOT rows of an iPadOS state-probe boot with the field meaning of its variant.

usage: decode_j81_ios_probe.py <archive.logarchive|rows.ndjson> <variant>
variant = the module suffix, for example page14, fender, fender-pmgrx-cpu48, fender-cpu194.
Only the newest boot that has a P1 record is decoded. Field meanings follow
boot/make_j81_ios_state_probes.py.
"""
import json
import re
import subprocess
import sys

BASE = {"P0": {"S": "gfx_ps_0x20320", "F": "page5_+4", "P": "perf_0x1c200", "V0": "pmgr_0x23000", "V1": "pmgr_0x2300c"},
        "P1": {"P": "perf_0x1c200", "V0": "pmgr_0x23000", "V1": "pmgr_0x2300c", "G": "log_buffer_scratch"}}


def meaning(variant: str) -> dict:
    m = {k: dict(v) for k, v in BASE.items()}
    tokens = variant.split("-")
    if "page14" in tokens:
        m["P0"].update(F="pmgr_0x1008", P="pmgr_0x4008")
        m["P1"]["F"] = "pmgr_0x1008/pmgr_0x4008/page5_+4"
    if "pmgrx" in tokens:
        for k in ("P0", "P1"):
            m[k].update(P="pmgr_0x2d100_soc_tvm_status", V0="pmgr_0x23004_vm_sram", V1="pmgr_0x22000")
    if "p22" in tokens:
        m["P0"].update(F="pmgr_0x22004", P="pmgr_0x22008", V0="pmgr_0x2200c", V1="pmgr_0x22010")
        m["P1"].update(F="pmgr_0x22004/pmgr_0x22008/page5_+4", P="pmgr_0x2200c", V0="pmgr_0x22010", V1="pmgr_0x22014")
    if "fender" in tokens:
        m["P1"]["G"] = "fender_0x201e00000_+0"
    cpu = [t for t in tokens if re.fullmatch(r"cpu[0-9a-f]+", t)]
    core = f"cpu_cluster_0x202220000_+0x{cpu[0][3:]}" if cpu else "gpu_core_id_0x201000020"
    return {"fields": m, "core": core}


def rows_from(path: str) -> list:
    if path.endswith(".ndjson"):
        raw = open(path, errors="replace").read().splitlines()
    else:
        raw = subprocess.run(["/usr/bin/log", "show", "--archive", path, "--style", "ndjson", "--info", "--debug",
                              "--predicate", 'eventMessage CONTAINS "J81_BOOT"'], capture_output=True, text=True).stdout.splitlines()
    rows = []
    for line in raw:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if "eventMessage" in d and "J81_BOOT" in d["eventMessage"]:
            rows.append((d["timestamp"], d.get("bootUUID", "?"), d["eventMessage"].split("features: ")[-1]))
    return sorted(rows)


def decode(rows: list, variant: str) -> list:
    boots = [b for _, b, t in rows if t.startswith("J81_BOOT P1 ")]
    if not boots:
        return ["no J81_BOOT P1 record in the archive (probe did not reach the post-GPC record)"]
    boot, mean, out = boots[-1], meaning(variant), []
    out.append(f"boot {boot} variant {variant}")
    for ts, b, text in rows:
        if b != boot:
            continue
        body = text.replace("J81_BOOT ", "", 1)
        head = body.split()[0]
        if head in ("P0", "P1"):
            for item in body.split()[1:]:
                key, _, value = item.partition("=")
                label = mean["fields"][head].get(key, key)
                out.append(f"  {ts[11:26]} {head} {key:<2} = {value}   [{label}]")
        elif body.startswith("CORE="):
            out.append(f"  {ts[11:26]} CORE = {body[5:]}   [{mean['core']}]")
        else:
            out.append(f"  {ts[11:26]} {body}")
    values = {}
    for ts, b, text in rows:
        if b == boot:
            for item in text.split():
                if "=" in item and not item.startswith("J81"):
                    k, _, v = item.partition("=")
                    values.setdefault(k, v)
    g = re.search(r"G=([0-9a-f]{8})", " ".join(t for _, b, t in rows if b == boot and " P1 " in t))
    if "fender" in variant.split("-") and g:
        bit29 = (int(g[1], 16) >> 29) & 1
        out.append(f"  derived: Fender +0 = 0x{g[1]} bit29 = {bit29} bit30 = {(int(g[1], 16) >> 30) & 1}")
    core = [t for _, b, t in rows if b == boot and t.startswith("J81_BOOT CORE=")]
    if core and any(re.fullmatch(r"cpu[0-9a-f]+", t) for t in variant.split("-")):
        word = int(core[-1].split("=")[1], 16)
        name = [t for t in variant.split("-") if t.startswith("cpu")][0]
        out.append(f"  derived: {name} word 0x{word:08x} bit0 = {word & 1} bit3 = {(word >> 3) & 1}")
    return out


if __name__ == "__main__":
    print("\n".join(decode(rows_from(sys.argv[1]), sys.argv[2])))
