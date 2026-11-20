# Review: agent result "startup outside PMGR region 0" (2026-11-20)

Source: from-builder/2026-11-20-j81-startup-outside-pmgr0-result (checksums verified OK).

Takeaways (code-derived unless noted):
- CPU block 0x202220000 = PMGR reg[1] child 0x2220000 (+0x200000000) = A8 cluster cpufreq controller (Linux dtsi agrees).
  Stock startup (0x6bccefc..0x6c8a238) issues TVM (+0x48), DPE (+0x1b0/1a0/150/190, calibration-conditional) and a late
  +0x20 update, all before the end-of-start hook. DPE is conditional, so our +0x1b0/+0x1a0 "positive control" was weak.
- Agent's best read-only control: +0x68 low word (LLB writes low 0x00080000; kernel 0x6c887cc/0x6c887e4 preserve it),
  then +0x40 (0x1088) or +0x58 (0x3a). Probe fender-cpu68 is ready; cpu78 too. Note width: stock ops are 64-bit, ours 32-bit.
- No loader (iBoot/LLB 12B410/15.8.8) store resolves to 0x201000000..0x201fffffff (indirect stores can escape the static reports).
- Between power and ID the stock path (0x6683918..0x66839e4) calls provider slots +0x568, +0x570 (inferred clock/power),
  then Fender +0x10000=0xffff0000, +0=0x40000000 (if guard clear), +0x1000=0x11, poll bit4 clear, 10 us delay, ID read.
  We already replay the Fender part; the +0x568/+0x570 provider side effects are unmodelled.
- SPR: no specific HID/IMPDEF write shown to govern the read; Linux MAIR byte for the core page matches the static prediction.
- Open: indirect loader stores, CPU register retention, executed order of unrelated service starts.

Plan: run fender-cpu68 next (cheap). If +0x68 is nonzero the block works and the earlier zeros are real (writes conditional/absent);
if zero, the CPU block is unreadable at the hook and gives no evidence either way. Also worth: Linux timing record (poll-to-read gap).
