"""Host test of the iPadOS probe decoder with synthetic rows."""
import decode_j81_ios_probe as d

B = "AAAAAAAA-0000-0000-0000-000000000000"
def row(ts, text, boot=B):
    return (f"2026-11-20 12:00:{ts}", boot, "J81_BOOT " + text)
rows = [row("01.000001", "P0 S=00000300 F=00000000 P=00000001 V0=00000170 V1=00000000"),
        row("01.000900", "GPC TICKS=0000391a"),
        row("01.000910", "P1 F=40000000/40000000/40000000 P=00000001 V0=00000170 V1=00000000 G=20000000"),
        row("01.000930", "BEFORE CORE READ"), row("01.000940", "CORE=00000001"),
        row("00.000001", "P0 S=00000300 F=0 P=0 V0=0 V1=0", boot="BBBBBBBB-0000-0000-0000-000000000000")]
out = "\n".join(d.decode(rows, "fender-pmgrx-cpu48"))
assert "boot " + B in out and "BBBBBBBB" not in out
assert "G  = 20000000   [fender_0x201e00000_+0]" in out and "bit29 = 1" in out
assert "P0 P  = 00000001   [pmgr_0x2d100_soc_tvm_status]" in out and "V0 = 00000170   [pmgr_0x23004_vm_sram]" in out
assert "CORE = 00000001   [cpu_cluster_0x202220000_+0x48]" in out and "cpu48 word 0x00000001 bit0 = 1" in out
assert "pmgr_0x1008/pmgr_0x4008/page5_+4" in "\n".join(d.decode(rows, "page14"))
assert "gpu_core_id_0x201000020" in "\n".join(d.decode(rows, "fender"))
assert "no J81_BOOT P1" in d.decode([], "page14")[0]
print("PASS: decoder labels fields per variant, picks the newest boot with a P1 record, derives the bits")
