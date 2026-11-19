#!/usr/bin/env python3
"""Regression checks for the input bits used by the J81 LLB rate calculation."""
from audit_j81_clock_pages import llb_rate


def check():
    # Captured pages 1 and 4 and the separate status-bit change observed on page 5.
    cases = ((0x80085040, 0x80480348, 798_000_000),
             (0x80032010, 0x88480348, 2_400_000_000),
             (0x00001010, 0x81480348, 0))
    for control, config, expected in cases:
        for config_pair in range(4):
            for status_pair in range(4):
                word = (config & 0x3fffffff) | (config_pair << 30)
                assert llb_rate(control, status_pair << 30, word) == expected
    # Change inputs that the two branches actually consume.
    assert llb_rate(0x80085040, 0, 0x88480348) == 1_596_000_000
    assert llb_rate(0x80032010, 0, 0x80480348) == 1_200_000_000
    assert llb_rate(0x1010, 0x40000001, 0x81480348) == 24_000_000
    assert llb_rate(0x80085000, 0, 0x80480348) == 0
    print("PASS: clock-page high pairs, rate-select bit, bypass and zero divisor")


if __name__ == "__main__":
    check()
