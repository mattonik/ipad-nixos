#!/usr/bin/env python3
"""Patch 0092: extract apple_s5l_pick_baud() from the patch text, compile it on the host and check the divisor search against known-good values."""
import pathlib, re, subprocess, tempfile

D = pathlib.Path(__file__).parent / "patches"
CASES = [  # clk, baud, factor, div (written to UBRDIV as ((16-f)<<16)|div)
    (24000000, 115200, 16, 12),     # same result as the legacy path (measured working)
    (24000000, 1500000, 16, 0),
    (24000000, 3000000, 8, 0),      # 0x80000, the iOS value for the Bluetooth UART
    (24000000, 921600, 13, 1),
]


def main():
    text = (D / "0092-samsung-tty-apple-s5l-sampling-factor-baud.patch").read_text()
    m = re.search(r"^\+(static void apple_s5l_pick_baud\(.*?^\+\})", text, re.S | re.M)
    assert m, "function missing"
    func = "\n".join(l[1:] if l.startswith("+") else l for l in m.group(1).splitlines())
    main_c = '#include <stdio.h>\n#include <limits.h>\n' + func + '\nint main(void){\n'
    for clk, baud, _, _ in CASES:
        main_c += f'{{unsigned f,d; apple_s5l_pick_baud({clk}UL,{baud},&f,&d); printf("%u %u\\n",f,d);}}\n'
    main_c += "return 0;}\n"
    with tempfile.TemporaryDirectory() as t:
        src = pathlib.Path(t) / "t.c"
        src.write_text(main_c)
        subprocess.run(["cc", "-O1", "-Wall", "-o", f"{t}/t", str(src)], check=True)
        out = subprocess.run([f"{t}/t"], check=True, capture_output=True, text=True).stdout.split("\n")
    for (clk, baud, f, d), line in zip(CASES, out):
        assert line == f"{f} {d}", (baud, line)
    assert "apple,baud-factor-select" in (D / "0093-t7001-air2-serial3-baud-factor-select.patch").read_text()
    print("PASS: apple_s5l_pick_baud cases and serial3 opt-in")


main()
