#!/usr/bin/env python3
"""MSI domain behaviour of pcie-apple-t7000.c, host-only (clean-driver series step 0057).

Compiles the REAL driver with the kernel-API stubs in kernel/pcie_trace/ and runs the harness
in `msi` mode: probe with the MSI properties declared, then the domain's alloc/compose/free
paths with failure injection. The trace is compared with a golden file and checked against
explicit invariants (design: research/2026-10-05-t7000-msi-domain-design.md, matrix A1-A5).

Usage: python3 kernel/test_pcie_msi_domain.py --source PATH/pcie-apple-t7000.c [--update-golden]
"""
import argparse
import importlib.util
from pathlib import Path
import re
import sys

HERE = Path(__file__).parent
GOLDEN = HERE / "pcie_trace" / "golden-msi.trace"
spec = importlib.util.spec_from_file_location("seq", HERE / "test_pcie_write_sequence.py")
seq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seq)


def scenarios(trace):
    parts = re.split(r"^== scenario ", trace, flags=re.M)[1:]
    return {p.splitlines()[0]: p for p in parts}


def check(trace):
    sc = scenarios(trace)
    assert set(sc) == {"msi/board", "msi/no-aic-defers", "msi/wrong-vector-count", "msi/no-doorbell",
                       "msi/not-declared"}, sorted(sc)
    board = sc["msi/board"]
    lines = board.splitlines()

    # A5: REG_ON first, then the MSI domain, then the host init, then the unchanged PCIe sequence.
    names = [l.split()[0] for l in lines[1:]]
    assert names[:2] == ["PMU_W", "MSLEEP"]
    assert names.index("MSI_DOMAIN") < names.index("HOST_INIT"), "domain must exist before host init"
    assert names.index("FIND_PARENT") < names.index("MSI_DOMAIN")
    assert "== probe returned 0" in board

    # The domain: 32 slots, parent AIC, one-vector flags only (no multi-MSI, no MSI-X).
    create = next(l for l in lines if l.startswith("MSI_DOMAIN create"))
    assert "size=32" in create and "parent=aic" in create and "token=2" in create
    supported = int(re.search(r"supported=(0x[0-9a-f]+)", create).group(1), 16)
    assert supported == 0x0f, "only the generic flags: no MSI_FLAG_MULTI_PCI_MSI, no MSI-X"
    assert "FIND_PARENT token=1 line=224" in board, "parent line of vector 0 is AIC 224, wired domain"

    # A1/A2: nine allocations take slots 8..15 in order, the ninth is refused.
    allocs = re.findall(r"ALLOC virq=(\d+) -> (-?\d+)", board.split("COMPOSE")[0])
    assert [int(r) for _, r in allocs] == [0] * 8 + [-28], allocs
    slots = [int(x) for x in re.findall(r"SET_HWIRQ virq=\d+ slot=(\d+)", board.split("COMPOSE")[0])]
    assert slots == list(range(8, 16)), slots
    parent = [int(x) for x in re.findall(r"PARENT_ALLOC virq=\d+ type=0 line=(\d+) flags=1", board.split("COMPOSE")[0])]
    assert parent == [224 + s for s in slots], "AIC line = 224 + slot"
    assert "ALLOC virq=108 -> -28" in board

    # Compose: address = the doorbell, data = the global slot.
    assert "COMPOSE virq=103 hi=0x00000000 lo=0xbffff000 data=11" in board

    # Free returns the lowest slot; two-vector is refused; a parent failure returns its slot.
    assert "SET_HWIRQ virq=120 slot=11" in board and "REALLOC virq=120 -> 0" in board
    assert "ALLOC two-vector -> -22" in board
    assert "PARENT_ALLOC virq=122 line=" in board and "-> fail" in board
    assert "ALLOC with parent failure -> -5" in board
    assert re.search(r"ALLOC after failure -> 0", board)
    after = board.split("ALLOC with parent failure")[1]
    freed_slot = 8  # slot of virq 100, freed just before the injected failure
    assert f"SET_HWIRQ virq=123 slot={freed_slot} " in after, "the failed allocation must give its slot back"
    assert board.rstrip().endswith("DOMAIN_REMOVE msi") or "DOMAIN_REMOVE msi" in board

    # Failure paths fail the probe cleanly and create no domain.
    for name, code in (("msi/no-aic-defers", -517), ("msi/wrong-vector-count", -22), ("msi/no-doorbell", -22)):
        assert f"== probe returned {code}" in sc[name], name
        assert "MSI_DOMAIN create" not in sc[name] and "HOST_INIT" not in sc[name], name
    # Not declared: no domain, host init proceeds as before.
    nd = sc["msi/not-declared"]
    assert "MSI_DOMAIN" not in nd and "HOST_INIT" in nd and "== probe returned 0" in nd

    # A3/A4: the controller sequence after HOST_INIT equals the hardware-proven one, so the MSI
    # code adds no controller write, read or delay.
    event = re.compile(r"(R\d+|W\d+|UDELAY|MSLEEP|GPIO_OUT)\b")
    tail = "\n".join(l for l in lines[lines.index("HOST_INIT") + 1:] if event.match(l))
    golden = scenarios(seq.GOLDEN.read_text())["j81-reg-on/zeros"]
    g_lines = golden.splitlines()
    g_tail = "\n".join(l for l in g_lines[3:] if event.match(l))
    assert seq.normalize(tail) == seq.normalize(g_tail), "MSI enablement changed the PCIe register sequence"
    assert not re.search(r"W\d+ +win3\+0x0016[89a-f]", board), "the doorbell register +0x168 must never be written"
    assert not re.search(r"W\d+ +win3\+0x0010[04] .*", board.split("HOST_INIT")[0]), "no port interrupt register write before init"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--update-golden", action="store_true")
    args = parser.parse_args()
    trace = seq.run_trace(args.source, "msi")
    check(trace)
    if args.update_golden:
        GOLDEN.write_text(trace)
        print(f"golden updated: {GOLDEN} ({len(trace.splitlines())} lines)")
        return 0
    if seq.normalize(trace) != seq.normalize(GOLDEN.read_text()):
        import difflib
        sys.stdout.writelines(difflib.unified_diff(GOLDEN.read_text().splitlines(True), trace.splitlines(True), "golden-msi", "candidate", n=2))
        print("FAIL: MSI trace differs from the golden")
        return 1
    print(f"PASS: MSI domain invariants and golden ({len(trace.splitlines())} trace lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
