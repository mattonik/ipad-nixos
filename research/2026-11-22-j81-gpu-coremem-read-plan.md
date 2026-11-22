# j81-gpu step 3b: META coremem reads (plan, 2026-11-22)

After `...-meta-read-result.md` (META MTP219, idle, slave port ready). Module sha256 b9a6fdae... adds word reads of the coremem code window 0x80000000 and data window 0x82000000 (first 64 words each; word aligned; read-only; same bounded slave-port sequence). Run: first 8 words of each window plus the segment regs again.
Purpose: see whether iBoot/iPadOS left firmware or bootloader code or data in META coremem, and the memory's reset pattern (zeros, ones, or code).
Prediction: unknown. Zeros or a reset pattern is the likely case. A timeout on the first read is reported as an error. A hang would mean global-window slave-port reads stall; watchdog reset, fresh DFU.
Mailbox: packet 7 `2026-11-22-j81-research-meta-mtp219-boot` (firmware image, stock start sequence, GPU address space, firmware interface version, first safe write plan) refines packet 5; both open.
