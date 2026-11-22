# j81-gpu step 3b: META coremem reads, result (2026-11-22, run 1)

Plan: `2026-11-22-j81-gpu-coremem-read-plan.md`. Module sha256 b9a6fdae.... Logs (private): `artifacts/live/private/j81-gpu-coremem-20261122-run1`. (An earlier launch failed on argument splitting before any device action; this is the first real run.) Identity as before; all 18 META reads returned, no hang, MSLVCTRL1 0x07000040 throughout.

First 8 words of the code window (0x80000000) and of the data window (0x82000000) are IDENTICAL, and not zero:
0x52eab189 0x02080040 0x1e6c2294 0x010a4492 0x65021463 0x01a01941 0x9f33c4fc 0x01004342.
MMCU_SEG0_BASE / LIMIT again 0x08000f02 / 0x17fff000.

Reading (not conclusive):
- the two windows return the same words: either code and data windows alias the same coremem, or the slave port ignores the upper address bits for global addresses.
- the words look high-entropy (no zero or ones fill, no obvious instruction pattern): consistent with uninitialised SRAM contents rather than firmware, but this is a guess; META instruction encoding was not checked.
- Open: whether the contents are the same on another boot (leftover from an earlier owner would persist; power-up garbage typically varies). Next cheap check: repeat on the next boot and compare; read at other offsets (e.g. 0x80000100.. is out of the allow-list; extend if needed).
Mailbox packets 5 and 7 remain open.
