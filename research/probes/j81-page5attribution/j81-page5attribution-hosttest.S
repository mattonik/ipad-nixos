#define J81_PAGE5_OFFSET 4
.text
.p2align 2
.globl _j81_page5attribution_start, _j81_page5attribution_end, _j81_page5attribution_power, _j81_page5attribution_control, _j81_page5attribution_control_resume, _j81_page5attribution_store, _j81_page5attribution_store_resume, _j81_page5attribution_readsite, _j81_page5attribution_readsite_resume, _j81_page5attribution_bridge, _j81_page5attribution_bridge_resume, _j81_page5attribution_clock, _j81_page5attribution_write, _j81_page5attribution_buffer, _j81_page5attribution_reader, _j81_page5attribution_format, _j81_page5attribution_logger, _j81_page5attribution_decision, _j81_page5attribution_decision_resume, _j81_page5attribution_aggregate, _j81_page5attribution_aggregate_resume, _j81_page5attribution_count, _j81_page5attribution_count_resume, _j81_page5attribution_choice, _j81_page5attribution_choice_resume, _j81_page5attribution_pm_poll, _j81_page5attribution_pm_resume, _j81_page5attribution_gpc_poll, _j81_page5attribution_gpc_loop, _j81_page5attribution_gpc_resume, _j81_page5attribution_identity, _j81_page5attribution_identity_resume
_j81_page5attribution_start:
_j81_page5attribution_clock:
 stp x29, x30, [sp, #-16]!
 adrp x16, _test_buffer@PAGE
 add x16, x16, _test_buffer@PAGEOFF
 add x17, x16, #12
Lclaim:
 ldaxr w9, [x17]
 cbnz w9, Lalready
 mov w10, #1
 stlxr w11, w10, [x17]
 cbnz w11, Lclaim
 adrp x9, _test_thread@PAGE
 ldr x9, [x9, _test_thread@PAGEOFF]
 str x9, [x16, #3616]
 stlr w10, [x16]
 blr x8
 sub sp, sp, #0x400
 stp x0, x1, [sp, #0x100]
 stp x2, x3, [sp, #0x110]
 stp x4, x5, [sp, #0x120]
 stp x6, x7, [sp, #0x130]
 stp x8, x9, [sp, #0x140]
 stp x10, x11, [sp, #0x150]
 stp x12, x13, [sp, #0x160]
 stp x14, x15, [sp, #0x170]
 stp x16, x17, [sp, #0x180]
 stp x18, x19, [sp, #0x190]
 stp x20, x21, [sp, #0x1a0]
 stp x22, x23, [sp, #0x1b0]
 stp x24, x25, [sp, #0x1c0]
 stp x26, x27, [sp, #0x1d0]
 stp x28, x29, [sp, #0x1e0]
 str x30, [sp, #0x1f0]
 mrs x8, nzcv
 str x8, [sp, #0x1f8]
 mrs x8, fpcr
 str w8, [sp, #0xf0]
 mrs x8, fpsr
 str w8, [sp, #0xf4]
 stp q0, q1, [sp, #0x200]
 stp q2, q3, [sp, #0x220]
 stp q4, q5, [sp, #0x240]
 stp q6, q7, [sp, #0x260]
 stp q8, q9, [sp, #0x280]
 stp q10, q11, [sp, #0x2a0]
 stp q12, q13, [sp, #0x2c0]
 stp q14, q15, [sp, #0x2e0]
 stp q16, q17, [sp, #0x300]
 stp q18, q19, [sp, #0x320]
 stp q20, q21, [sp, #0x340]
 stp q22, q23, [sp, #0x360]
 stp q24, q25, [sp, #0x380]
 stp q26, q27, [sp, #0x3a0]
 stp q28, q29, [sp, #0x3c0]
 stp q30, q31, [sp, #0x3e0]
 adrp x19, _test_buffer@PAGE
 add x19, x19, _test_buffer@PAGEOFF
 stlr wzr, [x19]
 mov x8, #0
 tst x8, #0x80
 b.ne Lclock_done
 ldr w20, [x19, #4]
 cmp w20, #128
 b.ls Lcount_ok
 mov w20, #128
Lcount_ok:
 mov w21, #0
 adr x22, Ldigits
Lbatch:
 add x23, sp, #0x10
 mov w9, #66
 strb w9, [x23], #1
 ldr w9, [x19, #8]
 add w9, w9, #48
 strb w9, [x23], #1
 mov w9, #32
 strb w9, [x23], #1
 mov w9, #68
 strb w9, [x23], #1
 add x9, x19, #16
 ldar w9, [x9]
 add w9, w9, #48
 strb w9, [x23], #1
 mov w9, #58
 strb w9, [x23], #1
 ldr w25, [x19, #20]
 bl Lhex8
 mov w9, #62
 strb w9, [x23], #1
 ldr w25, [x19, #24]
 bl Lhex8
 mov w9, #32
 strb w9, [x23], #1
 mov w9, #65
 strb w9, [x23], #1
 add x9, x19, #28
 ldar w9, [x9]
 add w9, w9, #48
 strb w9, [x23], #1
 mov w9, #58
 strb w9, [x23], #1
 ldr w25, [x19, #32]
 bl Lhex8
 mov w9, #62
 strb w9, [x23], #1
 ldr w25, [x19, #36]
 bl Lhex8
 mov w9, #32
 strb w9, [x23], #1
 mov w9, #78
 strb w9, [x23], #1
 add x9, x19, #40
 ldar w25, [x9]
 cmp w25, #0
 cset w9, ne
 add w9, w9, #48
 strb w9, [x23], #1
 mov w9, #58
 strb w9, [x23], #1
 cbz w25, Lcount_print
 sub w25, w25, #1
Lcount_print:
 bl Lhex8
 mov w9, #32
 strb w9, [x23], #1
 mov w9, #76
 strb w9, [x23], #1
 ldr w25, [x19, #3584]
 bl Lhex8
 mov w9, #32
 strb w9, [x23], #1
 mov w9, #88
 strb w9, [x23], #1
 ldr w9, [x19, #3600]
 add w9, w9, #48
 strb w9, [x23], #1
 mov w9, #58
 strb w9, [x23], #1
 ldr w25, [x19, #3588]
 bl Lhex8
 mov w9, #62
 strb w9, [x23], #1
 ldr w25, [x19, #3592]
 bl Lhex8
 mov w9, #32
 strb w9, [x23], #1
 mov w9, #77
 strb w9, [x23], #1
 ldr w25, [x19, #3596]
 bl Lhex8
 mov w9, #32
 strb w9, [x23], #1
 mov w9, #87
 strb w9, [x23], #1
 ldr w25, [x19, #3604]
 bl Lhex8
 mov w9, #32
 strb w9, [x23], #1
 mov w24, #0
Lrecord:
 cmp w21, w20
 b.hs Lemit
 add x9, x19, #48
 add x9, x9, w21, uxtw #4
 add x10, x9, #12
 ldar w10, [x10]
 cbz w10, Lnot_ready
 ldr w25, [x9]
 ldr w26, [x9, #4]
 ldr w27, [x9, #8]
 add x10, x19, #0xa00
 ldr w28, [x10, w21, uxtw #2]
 mov w15, #80
 strb w15, [x23], #1
 add x10, x19, #0xc00
 ldr w15, [x10, w21, uxtw #2]
 and w15, w15, #1
 add w15, w15, #48
 strb w15, [x23], #1
 mov w15, #84
 strb w15, [x23], #1
 ldr w15, [x10, w21, uxtw #2]
 lsr w15, w15, #1
 and w15, w15, #1
 add w15, w15, #48
 strb w15, [x23], #1
 mov w15, #58
 strb w15, [x23], #1
 bl Lhex8
 mov w15, #47
 strb w15, [x23], #1
 mov w25, w28
 bl Lhex8
 mov w15, #58
 strb w15, [x23], #1
 mov w25, w26
 bl Lhex8
 mov w15, #61
 strb w15, [x23], #1
 mov w25, w27
 bl Lhex8
 mov w15, #59
 strb w15, [x23], #1
 b Lrecord_end
Lnot_ready:
 mov w15, #63
 strb w15, [x23], #1
 mov w15, #59
 strb w15, [x23], #1
Lrecord_end:
 add w21, w21, #1
 add w24, w24, #1
 cmp w24, #2
 b.lo Lrecord
Lemit:
 strb wzr, [x23]
 add x8, sp, #0x10
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 cmp w21, w20
 b.lo Lbatch
 ldr w9, [x19, #3628]
 cbz w9, Lclock_done
 ldr x0, [x19, #3640]
 cbz x0, Lclock_done
 adr x8, Lpage5_early_before
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 ldr x0, [x19, #3640]
 ldr x8, [x0]
 cbz x8, Lclock_done
 ldr x8, [x8, #0x980]
 cbz x8, Lclock_done
 mov x1, #0
 mov w2, #0x5004
 mov x3, #0
 blr x8
 add x23, sp, #0x10
 mov w9, #81
 strb w9, [x23], #1
 mov w9, #61
 strb w9, [x23], #1
 mov w25, w0
 bl Lhex8
 strb wzr, [x23]
 add x8, sp, #0x10
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 b Lclock_done
Lpage5_early_before:
 .asciz "PAGE5-early-before"
.p2align 2
Lhex8:
 mov w14, #28
Lhexloop:
 lsr w15, w25, w14
 and w15, w15, #15
 ldrb w15, [x22, w15, uxtw]
 strb w15, [x23], #1
 subs w14, w14, #4
 b.ge Lhexloop
 ret
Lclock_done:
 ldp q0, q1, [sp, #0x200]
 ldp q2, q3, [sp, #0x220]
 ldp q4, q5, [sp, #0x240]
 ldp q6, q7, [sp, #0x260]
 ldp q8, q9, [sp, #0x280]
 ldp q10, q11, [sp, #0x2a0]
 ldp q12, q13, [sp, #0x2c0]
 ldp q14, q15, [sp, #0x2e0]
 ldp q16, q17, [sp, #0x300]
 ldp q18, q19, [sp, #0x320]
 ldp q20, q21, [sp, #0x340]
 ldp q22, q23, [sp, #0x360]
 ldp q24, q25, [sp, #0x380]
 ldp q26, q27, [sp, #0x3a0]
 ldp q28, q29, [sp, #0x3c0]
 ldp q30, q31, [sp, #0x3e0]
 ldr w8, [sp, #0xf0]
 msr fpcr, x8
 ldr w8, [sp, #0xf4]
 msr fpsr, x8
 ldr x8, [sp, #0x1f8]
 msr nzcv, x8
 ldr x30, [sp, #0x1f0]
 ldp x0, x1, [sp, #0x100]
 ldp x2, x3, [sp, #0x110]
 ldp x4, x5, [sp, #0x120]
 ldp x6, x7, [sp, #0x130]
 ldp x8, x9, [sp, #0x140]
 ldp x10, x11, [sp, #0x150]
 ldp x12, x13, [sp, #0x160]
 ldp x14, x15, [sp, #0x170]
 ldp x16, x17, [sp, #0x180]
 ldp x18, x19, [sp, #0x190]
 ldp x20, x21, [sp, #0x1a0]
 ldp x22, x23, [sp, #0x1b0]
 ldp x24, x25, [sp, #0x1c0]
 ldp x26, x27, [sp, #0x1d0]
 ldp x28, x29, [sp, #0x1e0]
 add sp, sp, #0x400
 ldp x29, x30, [sp], #16
 ret
Lalready:
 clrex
 ldp x29, x30, [sp], #16
 br x8
_j81_page5attribution_write:
 sub sp, sp, #0x60
 stp x9, x10, [sp]
 stp x11, x12, [sp, #0x10]
 stp x13, x14, [sp, #0x20]
 stp x15, x16, [sp, #0x30]
 stp x17, xzr, [sp, #0x40]
 mrs x9, nzcv
 str x9, [sp, #0x50]
 adrp x10, _test_buffer@PAGE
 add x10, x10, _test_buffer@PAGEOFF
 ldar w9, [x10]
 cbz w9, Lwrite_done
 ldr w9, [x10, #12]
 cbz w9, Lwriter_count_done
 add x11, x10, #3604
Lwriter_count_loop:
 ldxr w9, [x11]
 add w9, w9, #1
 stxr w12, w9, [x11]
 cbnz w12, Lwriter_count_loop
Lwriter_count_done:
 add x11, x10, #4
Lreserve:
 ldaxr w9, [x11]
 cmp w9, #128
 b.hs Loverflow
 add w12, w9, #1
 stlxr w13, w12, [x11]
 cbnz w13, Lreserve
 add x12, x10, #0xa00
 str w4, [x12, w9, uxtw #2]
 add x12, x10, #0xc00
 ldr w13, [x10, #12]
 ldr x14, [x10, #3616]
 cbz x14, Lthread_unknown
 adrp x15, _test_thread@PAGE
 ldr x15, [x15, _test_thread@PAGEOFF]
 cmp x15, x14
 cset w14, eq
 orr w13, w13, w14, lsl #1
Lthread_unknown:
 str w13, [x12, w9, uxtw #2]
 add x12, x10, #48
 add x12, x12, w9, uxtw #4
 stp w1, w2, [x12]
 str w3, [x12, #8]
 add x12, x12, #12
 mov w13, #1
 stlr w13, [x12]
 b Lwrite_done
Loverflow:
 clrex
 mov w13, #1
 str w13, [x10, #8]
Lwrite_done:
 ldr x9, [sp, #0x50]
 msr nzcv, x9
 ldp x17, xzr, [sp, #0x40]
 ldp x15, x16, [sp, #0x30]
 ldp x13, x14, [sp, #0x20]
 ldp x11, x12, [sp, #0x10]
 ldp x9, x10, [sp]
 add sp, sp, #0x60
 br x8
_j81_page5attribution_decision:
 sub sp, sp, #0x20
 stp x9, x10, [sp]
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 ldar w10, [x9]
 cbz w10, Ldecision_done
 ldr w10, [x9, #12]
 cbz w10, Ldecision_done
 and w10, w28, #0xffff
 cmp w10, #0x7c
 b.ne Ldecision_done
 str w24, [x9, #20]
 str w22, [x9, #24]
 add x9, x9, #16
 mov w10, #1
 stlr w10, [x9]
Ldecision_done:
 ldp x9, x10, [sp]
 add sp, sp, #0x20
 cmp w24, w22
_j81_page5attribution_decision_resume:
 ret
_j81_page5attribution_aggregate:
 sub sp, sp, #0x20
 stp x9, x10, [sp]
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 ldar w10, [x9]
 cbz w10, Laggregate_done
 ldr w10, [x9, #12]
 cbz w10, Laggregate_done
 cmp w20, #0x7c
 b.ne Laggregate_done
 str w25, [x9, #32]
 str w26, [x9, #36]
 add x9, x9, #28
 mov w10, #1
 stlr w10, [x9]
Laggregate_done:
 ldp x9, x10, [sp]
 add sp, sp, #0x20
 cmp w26, w25
_j81_page5attribution_aggregate_resume:
 ret
_j81_page5attribution_count:
 ldr w24, [sp, #0x3c]
 sub sp, sp, #0x20
 stp x9, x10, [sp]
 mrs x9, nzcv
 str x9, [sp, #16]
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 ldar w10, [x9]
 cbz w10, Lcount_done
 ldr w10, [x9, #12]
 cbz w10, Lcount_done
 and w10, w28, #0xffff
 cmp w10, #0x7c
 b.ne Lcount_done
 cbz w24, Lno_first_entry
 ldr w10, [sp, #0x70]
 str w10, [x9, #3584]
Lno_first_entry:
 add x9, x9, #40
 add w10, w24, #1
 stlr w10, [x9]
Lcount_done:
 ldr x9, [sp, #16]
 msr nzcv, x9
 ldp x9, x10, [sp]
 add sp, sp, #0x20
_j81_page5attribution_count_resume:
 ret
_j81_page5attribution_choice:
 sub sp, sp, #0x20
 stp x9, x10, [sp]
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 ldar w10, [x9]
 cbz w10, Lchoice_done
 ldr w10, [x9, #12]
 cbz w10, Lchoice_done
 cmp w24, #1
 b.ne Lchoice_done
 ldrh w10, [x27]
 cmp w10, #0x7c
 b.ne Lchoice_done
 str w25, [x9, #3588]
 str w21, [x9, #3592]
 ldr w10, [x19, #0x2684]
 str w10, [x9, #3596]
 add x9, x9, #3600
 mov w10, #1
 stlr w10, [x9]
Lchoice_done:
 ldp x9, x10, [sp]
 add sp, sp, #0x20
 cmp w25, w21
_j81_page5attribution_choice_resume:
 ret
Ldigits:
 .ascii "0123456789abcdef"
.p2align 3
_j81_page5attribution_reader:
 .quad 0
_j81_page5attribution_buffer:
 .quad 0
_j81_page5attribution_format:
 .quad 0
_j81_page5attribution_logger:
 .quad 0

_j81_page5attribution_pm_poll:
 sub sp, sp, #0x30
 stp x9, x10, [sp]
 stp x11, x12, [sp, #0x10]
 mrs x9, nzcv
 str x9, [sp, #0x20]
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 ldar w10, [x9]
 cbz w10, Lpm_done
 ldr x10, [x9, #3616]
 cbz x10, Lpm_done
 adrp x11, _test_thread@PAGE
 ldr x11, [x11, _test_thread@PAGEOFF]
 cmp x11, x10
 b.ne Lpm_done
 cbnz w19, Lpm_done
 mov w10, #0x320
 movk w10, #2, lsl #16
 cmp w20, w10
 b.ne Lpm_done
 cbnz w23, Lpm_done
 cmp w21, #0xf0
 b.ne Lpm_done
 cmp w22, #0xf0
 b.ne Lpm_done
 str x25, [x9, #3640]
 str w0, [x9, #3624]
 mov w10, #1
 str w10, [x9, #3628]
Lpm_done:
 ldr x9, [sp, #0x20]
 msr nzcv, x9
 ldp x11, x12, [sp, #0x10]
 ldp x9, x10, [sp]
 add sp, sp, #0x30
 and w8, w0, w21
_j81_page5attribution_pm_resume:
 ret
_j81_page5attribution_readsite:
 ldr w0, [x8, w19, uxtw]
 sub sp, sp, #0x30
 stp x9, x10, [sp]
 stp x11, x12, [sp, #0x10]
 mrs x9, nzcv
 str x9, [sp, #0x20]
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 ldr x10, [x9, #3640]
 cbz x10, Ltarget_done
 cmp x22, x10
 b.ne Ltarget_done
 cbnz w21, Ltarget_done
 cbnz w20, Ltarget_done
 mov w10, #0x5004
 cmp w19, w10
 b.ne Ltarget_done
 add x10, x8, w19, uxtw
 add x11, x9, #4000
 mov w12, #16
Ltarget_claim:
 ldaxr x9, [x11]
 cbnz x9, Ltarget_existing
 stlxr w9, x10, [x11]
 cbz w9, Ltarget_done
 subs w12, w12, #1
 b.ne Ltarget_claim
 b Ltarget_failed
Ltarget_existing:
 clrex
 cmp x9, x10
 b.eq Ltarget_done
Ltarget_failed:
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 add x9, x9, #4036
 mov w10, #1
 stlr w10, [x9]
Ltarget_done:
 ldr x9, [sp, #0x20]
 msr nzcv, x9
 ldp x11, x12, [sp, #0x10]
 ldp x9, x10, [sp]
 add sp, sp, #0x30
_j81_page5attribution_readsite_resume:
 ret
_j81_page5attribution_store:
 sub sp, sp, #0x60
 stp x9, x10, [sp]
 stp x11, x12, [sp, #0x10]
 stp x13, x14, [sp, #0x20]
 stp x15, x16, [sp, #0x30]
 mrs x9, nzcv
 str x9, [sp, #0x40]
 str wzr, [sp, #0x50]
 b Lstore_common
Lsynthetic_store:
 sub sp, sp, #0x60
 stp x9, x10, [sp]
 stp x11, x12, [sp, #0x10]
 stp x13, x14, [sp, #0x20]
 stp x15, x16, [sp, #0x30]
 mrs x9, nzcv
 str x9, [sp, #0x40]
 str x30, [sp, #0x48]
 mov w9, #1
 str w9, [sp, #0x50]
Lstore_common:
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 ldr w10, [sp, #0x50]
 cbnz w10, Lstore_seen_done
 add x10, x9, #3716
 mov w11, #1
 stlr w11, [x10]
Lstore_seen_done:
 mov x13, #0
 mov w14, #0
 add x10, x9, #4000
 ldar x10, [x10]
 cbz x10, Lstore_store
 add x11, x8, w19, uxtw
 cmp x10, x11
 b.ne Lstore_store
 add x11, x9, #4008
 mov w15, #16
Lstore_enter:
 ldaxr w12, [x11]
 cmn w12, #1
 b.eq Lstore_failed
 add w12, w12, #1
 stlxr w16, w12, [x11]
 cbz w16, Lstore_entered
 subs w15, w15, #1
 b.ne Lstore_enter
Lstore_failed:
 clrex
 add x10, x9, #4036
 mov w11, #1
 stlr w11, [x10]
 b Lstore_store
Lstore_entered:
 mov w14, #1
 add x11, x9, #3720
 mov w15, #16
Lstore_reserve:
 ldaxr w12, [x11]
 cmp w12, #16
 b.hs Lstore_overflow
 add w10, w12, #1
 stlxr w16, w10, [x11]
 cbz w16, Lstore_reserved
 subs w15, w15, #1
 b.ne Lstore_reserve
Lstore_overflow:
 clrex
 add x10, x9, #3724
 mov w11, #1
 stlr w11, [x10]
 b Lstore_store
Lstore_reserved:
 add x13, x9, #3744
 add x13, x13, w12, uxtw #4
 add x10, x9, #3712
 ldar w11, [x10]
 orr w11, w11, #0x100
 ldr w10, [sp, #0x50]
 cbz w10, Lstore_record_tagged
 orr w11, w11, #0x400
Lstore_record_tagged:
 str w11, [x13]
 str w21, [x13, #8]
Lstore_store:
 ldr w10, [sp, #0x50]
 cbnz w10, Lstore_after_store
 str w21, [x8, w19, uxtw]
Lstore_after_store:
 cbz x13, Lstore_retire
 add x10, x9, #3712
 ldar w11, [x10]
 orr w11, w11, #0x100
 ldr w10, [sp, #0x50]
 cbz w10, Lstore_completion_tagged
 orr w11, w11, #0x400
Lstore_completion_tagged:
 str w11, [x13, #4]
 add x10, x13, #12
 mov w11, #1
 stlr w11, [x10]
Lstore_retire:
 cbz w14, Lstore_done
 add x11, x9, #4008
 mov w15, #16
Lstore_leave:
 ldaxr w12, [x11]
 cbz w12, Lstore_leave_failed
 sub w12, w12, #1
 stlxr w16, w12, [x11]
 cbz w16, Lstore_done
 subs w15, w15, #1
 b.ne Lstore_leave
Lstore_leave_failed:
 clrex
 add x10, x9, #4036
 mov w11, #1
 stlr w11, [x10]
Lstore_done:
 ldr w9, [sp, #0x50]
 cbnz w9, Lsynthetic_done
 ldr x9, [sp, #0x40]
 msr nzcv, x9
 ldp x9, x10, [sp]
 ldp x11, x12, [sp, #0x10]
 ldp x13, x14, [sp, #0x20]
 ldp x15, x16, [sp, #0x30]
 add sp, sp, #0x60
_j81_page5attribution_store_resume:
 ret
Lsynthetic_done:
 ldr x30, [sp, #0x48]
 ldr x9, [sp, #0x40]
 msr nzcv, x9
 ldp x9, x10, [sp]
 ldp x11, x12, [sp, #0x10]
 ldp x13, x14, [sp, #0x20]
 ldp x15, x16, [sp, #0x30]
 add sp, sp, #0x60
 ret
_j81_page5attribution_bridge:
 sub sp, sp, #0x60
 stp x9, x10, [sp]
 stp x11, x12, [sp, #0x10]
 stp x13, x14, [sp, #0x20]
 stp x15, x16, [sp, #0x30]
 mrs x9, nzcv
 str x9, [sp, #0x40]
 str wzr, [sp, #0x50]
 b Lbridge_common
Lsynthetic_bridge:
 sub sp, sp, #0x60
 stp x9, x10, [sp]
 stp x11, x12, [sp, #0x10]
 stp x13, x14, [sp, #0x20]
 stp x15, x16, [sp, #0x30]
 mrs x9, nzcv
 str x9, [sp, #0x40]
 str x30, [sp, #0x48]
 mov w9, #1
 str w9, [sp, #0x50]
Lbridge_common:
 adrp x9, _test_buffer@PAGE
 add x9, x9, _test_buffer@PAGEOFF
 ldr w10, [sp, #0x50]
 cbnz w10, Lbridge_seen_done
 add x10, x9, #4016
 mov w11, #1
 stlr w11, [x10]
Lbridge_seen_done:
 mov x13, #0
 mov w14, #0
 add x10, x9, #4000
 ldar x10, [x10]
 cbz x10, Lbridge_store
 add x11, x8, w2, uxtw
 cmp x10, x11
 b.ne Lbridge_store
 add x11, x9, #4012
 mov w15, #16
Lbridge_enter:
 ldaxr w12, [x11]
 cmn w12, #1
 b.eq Lbridge_failed
 add w12, w12, #1
 stlxr w16, w12, [x11]
 cbz w16, Lbridge_entered
 subs w15, w15, #1
 b.ne Lbridge_enter
Lbridge_failed:
 clrex
 add x10, x9, #4036
 mov w11, #1
 stlr w11, [x10]
 b Lbridge_store
Lbridge_entered:
 mov w14, #1
 add x11, x9, #3720
 mov w15, #16
Lbridge_reserve:
 ldaxr w12, [x11]
 cmp w12, #16
 b.hs Lbridge_overflow
 add w10, w12, #1
 stlxr w16, w10, [x11]
 cbz w16, Lbridge_reserved
 subs w15, w15, #1
 b.ne Lbridge_reserve
Lbridge_overflow:
 clrex
 add x10, x9, #3724
 mov w11, #1
 stlr w11, [x10]
 b Lbridge_store
Lbridge_reserved:
 add x13, x9, #3744
 add x13, x13, w12, uxtw #4
 add x10, x9, #3712
 ldar w11, [x10]
 orr w11, w11, #0x200
 ldr w10, [sp, #0x50]
 cbz w10, Lbridge_record_tagged
 orr w11, w11, #0x400
Lbridge_record_tagged:
 str w11, [x13]
 str w3, [x13, #8]
Lbridge_store:
 ldr w10, [sp, #0x50]
 cbnz w10, Lbridge_after_store
 str w3, [x8, w2, uxtw]
Lbridge_after_store:
 cbz x13, Lbridge_retire
 add x10, x9, #3712
 ldar w11, [x10]
 orr w11, w11, #0x200
 ldr w10, [sp, #0x50]
 cbz w10, Lbridge_completion_tagged
 orr w11, w11, #0x400
Lbridge_completion_tagged:
 str w11, [x13, #4]
 add x10, x13, #12
 mov w11, #1
 stlr w11, [x10]
Lbridge_retire:
 cbz w14, Lbridge_done
 add x11, x9, #4012
 mov w15, #16
Lbridge_leave:
 ldaxr w12, [x11]
 cbz w12, Lbridge_leave_failed
 sub w12, w12, #1
 stlxr w16, w12, [x11]
 cbz w16, Lbridge_done
 subs w15, w15, #1
 b.ne Lbridge_leave
Lbridge_leave_failed:
 clrex
 add x10, x9, #4036
 mov w11, #1
 stlr w11, [x10]
Lbridge_done:
 ldr w9, [sp, #0x50]
 cbnz w9, Lsynthetic_bridge_done
 ldr x9, [sp, #0x40]
 msr nzcv, x9
 ldp x9, x10, [sp]
 ldp x11, x12, [sp, #0x10]
 ldp x13, x14, [sp, #0x20]
 ldp x15, x16, [sp, #0x30]
 add sp, sp, #0x60
_j81_page5attribution_bridge_resume:
 ret
Lsynthetic_bridge_done:
 ldr x30, [sp, #0x48]
 ldr x9, [sp, #0x40]
 msr nzcv, x9
 ldp x9, x10, [sp]
 ldp x11, x12, [sp, #0x10]
 ldp x13, x14, [sp, #0x20]
 ldp x15, x16, [sp, #0x30]
 add sp, sp, #0x60
 ret
_j81_page5attribution_control:
 sub sp, sp, #0x140
 stp x0, x1, [sp, #0x40]
 stp x2, x3, [sp, #0x50]
 stp x4, x5, [sp, #0x60]
 stp x6, x7, [sp, #0x70]
 stp x8, x9, [sp, #0x80]
 stp x10, x11, [sp, #0x90]
 stp x12, x13, [sp, #0xa0]
 stp x14, x15, [sp, #0xb0]
 stp x16, x17, [sp, #0xc0]
 stp x18, x19, [sp, #0xd0]
 stp x20, x21, [sp, #0xe0]
 stp x22, x23, [sp, #0xf0]
 stp x24, x25, [sp, #0x100]
 stp x26, x27, [sp, #0x110]
 stp x28, x29, [sp, #0x120]
 str x30, [sp, #0x130]
 mrs x8, nzcv
 str x8, [sp, #0x138]
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 ldr x10, [x12, #3616]
 cbz x10, Lcontrol_restore
 adrp x9, _test_thread@PAGE
 ldr x9, [x9, _test_thread@PAGEOFF]
 cmp x9, x10
 b.ne Lcontrol_restore
 mov x8, #0
 tst x8, #0x80
 b.ne Lcontrol_restore
 ldr w8, [x12, #3628]
 cbz w8, Lcontrol_restore
 ldr x0, [x12, #3640]
 cbz x0, Lcontrol_restore
 ldr x8, [x0]
 cbz x8, Lcontrol_restore
 ldr x8, [x8, #0x980]
 cbz x8, Lcontrol_restore
 adrp x9, _fake_read@PAGE
 add x9, x9, _fake_read@PAGEOFF
 cmp x8, x9
 b.ne Lcontrol_restore
 add x10, x12, #3688
Lcontrol_claim:
 ldaxr w9, [x10]
 cbnz w9, Lcontrol_claimed
 mov w9, #1
 stlxr w11, w9, [x10]
 cbnz w11, Lcontrol_claim
 mov x1, #0
 mov w2, #0x5004
 mov x3, #0
 add x9, x12, #4000
 ldar x10, [x9]
 cmp x10, #0
 cset w10, ne
 str w10, [x12, #4044]
 add x9, x12, #4008
 ldar w10, [x9]
 str w10, [x12, #4020]
 add x9, x12, #4012
 ldar w10, [x9]
 str w10, [x12, #4024]
 add x9, x12, #3712
 mov w10, #1
 stlr w10, [x9]
 blr x8
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 str w0, [x12, #3692]
 add x12, x12, #3696
 mov w9, #1
 stlr w9, [x12]
 b Lcontrol_restore
Lcontrol_claimed:
 clrex
Lcontrol_restore:
 ldr x8, [sp, #0x138]
 msr nzcv, x8
 ldr x30, [sp, #0x130]
 ldp x0, x1, [sp, #0x40]
 ldp x2, x3, [sp, #0x50]
 ldp x4, x5, [sp, #0x60]
 ldp x6, x7, [sp, #0x70]
 ldp x8, x9, [sp, #0x80]
 ldp x10, x11, [sp, #0x90]
 ldp x12, x13, [sp, #0xa0]
 ldp x14, x15, [sp, #0xb0]
 ldp x16, x17, [sp, #0xc0]
 ldp x18, x19, [sp, #0xd0]
 ldp x20, x21, [sp, #0xe0]
 ldp x22, x23, [sp, #0xf0]
 ldp x24, x25, [sp, #0x100]
 ldp x26, x27, [sp, #0x110]
 ldp x28, x29, [sp, #0x120]
 add sp, sp, #0x140
 mov w8, #0x11
_j81_page5attribution_control_resume:
 ret
_j81_page5attribution_power:
 stp x29, x30, [sp, #-16]!
 blr x8
 sub sp, sp, #0x140
 stp x0, x1, [sp, #0x40]
 stp x2, x3, [sp, #0x50]
 stp x4, x5, [sp, #0x60]
 stp x6, x7, [sp, #0x70]
 stp x8, x9, [sp, #0x80]
 stp x10, x11, [sp, #0x90]
 stp x12, x13, [sp, #0xa0]
 stp x14, x15, [sp, #0xb0]
 stp x16, x17, [sp, #0xc0]
 stp x18, x19, [sp, #0xd0]
 stp x20, x21, [sp, #0xe0]
 stp x22, x23, [sp, #0xf0]
 stp x24, x25, [sp, #0x100]
 stp x26, x27, [sp, #0x110]
 stp x28, x29, [sp, #0x120]
 str x30, [sp, #0x130]
 mrs x8, nzcv
 str x8, [sp, #0x138]
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 ldr x10, [x12, #3616]
 cbz x10, Lpower_restore
 adrp x9, _test_thread@PAGE
 ldr x9, [x9, _test_thread@PAGEOFF]
 cmp x9, x10
 b.ne Lpower_restore
 mov x8, #0
 tst x8, #0x80
 b.ne Lpower_restore
 ldr w8, [x12, #3628]
 cbz w8, Lpower_restore
 ldr x0, [x12, #3640]
 cbz x0, Lpower_restore
 ldr x8, [x0]
 cbz x8, Lpower_restore
 ldr x8, [x8, #0x980]
 cbz x8, Lpower_restore
 adrp x9, _fake_read@PAGE
 add x9, x9, _fake_read@PAGEOFF
 cmp x8, x9
 b.ne Lpower_restore
 add x10, x12, #3672
Lpower_claim:
 ldaxr w9, [x10]
 cbnz w9, Lpower_claimed
 mov w9, #1
 stlxr w11, w9, [x10]
 cbnz w11, Lpower_claim
 mov x1, #0
 mov w2, #0x5004
 mov x3, #0
 blr x8
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 str w0, [x12, #3676]
 add x12, x12, #3680
 mov w9, #1
 stlr w9, [x12]
 b Lpower_restore
Lpower_claimed:
 clrex
Lpower_restore:
 ldr x8, [sp, #0x138]
 msr nzcv, x8
 ldr x30, [sp, #0x130]
 ldp x0, x1, [sp, #0x40]
 ldp x2, x3, [sp, #0x50]
 ldp x4, x5, [sp, #0x60]
 ldp x6, x7, [sp, #0x70]
 ldp x8, x9, [sp, #0x80]
 ldp x10, x11, [sp, #0x90]
 ldp x12, x13, [sp, #0xa0]
 ldp x14, x15, [sp, #0xb0]
 ldp x16, x17, [sp, #0xc0]
 ldp x18, x19, [sp, #0xd0]
 ldp x20, x21, [sp, #0xe0]
 ldp x22, x23, [sp, #0xf0]
 ldp x24, x25, [sp, #0x100]
 ldp x26, x27, [sp, #0x110]
 ldp x28, x29, [sp, #0x120]
 add sp, sp, #0x140
 ldp x29, x30, [sp], #16
 ret
_j81_page5attribution_gpc_poll:
 tbnz w8, #4, Lmiddle_again
 sub sp, sp, #0x140
 stp x0, x1, [sp, #0x40]
 stp x2, x3, [sp, #0x50]
 stp x4, x5, [sp, #0x60]
 stp x6, x7, [sp, #0x70]
 stp x8, x9, [sp, #0x80]
 stp x10, x11, [sp, #0x90]
 stp x12, x13, [sp, #0xa0]
 stp x14, x15, [sp, #0xb0]
 stp x16, x17, [sp, #0xc0]
 stp x18, x19, [sp, #0xd0]
 stp x20, x21, [sp, #0xe0]
 stp x22, x23, [sp, #0xf0]
 stp x24, x25, [sp, #0x100]
 stp x26, x27, [sp, #0x110]
 stp x28, x29, [sp, #0x120]
 str x30, [sp, #0x130]
 mrs x8, nzcv
 str x8, [sp, #0x138]
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 ldr x10, [x12, #3616]
 cbz x10, Lmiddle_restore
 adrp x9, _test_thread@PAGE
 ldr x9, [x9, _test_thread@PAGEOFF]
 cmp x9, x10
 b.ne Lmiddle_restore
 ldr w8, [sp, #0x80]
 str w8, [x12, #3632]
 mov w9, #1
 str w9, [x12, #3636]
 mov x8, #0
 tst x8, #0x80
 b.ne Lmiddle_restore
 ldr w8, [x12, #3628]
 cbz w8, Lmiddle_restore
 ldr x0, [x12, #3640]
 cbz x0, Lmiddle_restore
 ldr x8, [x0]
 cbz x8, Lmiddle_restore
 ldr x8, [x8, #0x980]
 cbz x8, Lmiddle_restore
 adrp x9, _fake_read@PAGE
 add x9, x9, _fake_read@PAGEOFF
 cmp x8, x9
 b.ne Lmiddle_restore
 add x10, x12, #3656
Lmiddle_claim:
 ldaxr w9, [x10]
 cbnz w9, Lmiddle_claimed
 mov w9, #1
 stlxr w11, w9, [x10]
 cbnz w11, Lmiddle_claim
 mov x1, #0
 mov w2, #0x5004
 mov x3, #0
 blr x8
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 add x9, x12, #3712
 mov w10, #2
 stlr w10, [x9]
 add x9, x12, #4008
 ldar w10, [x9]
 str w10, [x12, #4028]
 add x9, x12, #4012
 ldar w10, [x9]
 str w10, [x12, #4032]
 str w0, [x12, #3660]
 add x12, x12, #3664
 mov w9, #1
 stlr w9, [x12]
 b Lmiddle_restore
Lmiddle_claimed:
 clrex
Lmiddle_restore:
 ldr x8, [sp, #0x138]
 msr nzcv, x8
 ldr x30, [sp, #0x130]
 ldp x0, x1, [sp, #0x40]
 ldp x2, x3, [sp, #0x50]
 ldp x4, x5, [sp, #0x60]
 ldp x6, x7, [sp, #0x70]
 ldp x8, x9, [sp, #0x80]
 ldp x10, x11, [sp, #0x90]
 ldp x12, x13, [sp, #0xa0]
 ldp x14, x15, [sp, #0xb0]
 ldp x16, x17, [sp, #0xc0]
 ldp x18, x19, [sp, #0xd0]
 ldp x20, x21, [sp, #0xe0]
 ldp x22, x23, [sp, #0xf0]
 ldp x24, x25, [sp, #0x100]
 ldp x26, x27, [sp, #0x110]
 ldp x28, x29, [sp, #0x120]
 add sp, sp, #0x140
_j81_page5attribution_gpc_resume:
 ret
Lmiddle_again:
_j81_page5attribution_gpc_loop:
 ret
_j81_page5attribution_identity:
 sub sp, sp, #0x340
 stp x0, x1, [sp, #0x40]
 stp x2, x3, [sp, #0x50]
 stp x4, x5, [sp, #0x60]
 stp x6, x7, [sp, #0x70]
 stp x8, x9, [sp, #0x80]
 stp x10, x11, [sp, #0x90]
 stp x12, x13, [sp, #0xa0]
 stp x14, x15, [sp, #0xb0]
 stp x16, x17, [sp, #0xc0]
 stp x18, x19, [sp, #0xd0]
 stp x20, x21, [sp, #0xe0]
 stp x22, x23, [sp, #0xf0]
 stp x24, x25, [sp, #0x100]
 stp x26, x27, [sp, #0x110]
 stp x28, x29, [sp, #0x120]
 str x30, [sp, #0x130]
 mrs x8, nzcv
 str x8, [sp, #0x138]
 mrs x8, fpcr
 str w8, [sp, #8]
 mrs x8, fpsr
 str w8, [sp, #12]
 stp q0, q1, [sp, #0x140]
 stp q2, q3, [sp, #0x160]
 stp q4, q5, [sp, #0x180]
 stp q6, q7, [sp, #0x1a0]
 stp q8, q9, [sp, #0x1c0]
 stp q10, q11, [sp, #0x1e0]
 stp q12, q13, [sp, #0x200]
 stp q14, q15, [sp, #0x220]
 stp q16, q17, [sp, #0x240]
 stp q18, q19, [sp, #0x260]
 stp q20, q21, [sp, #0x280]
 stp q22, q23, [sp, #0x2a0]
 stp q24, q25, [sp, #0x2c0]
 stp q26, q27, [sp, #0x2e0]
 stp q28, q29, [sp, #0x300]
 stp q30, q31, [sp, #0x320]
 mov x8, #0
 tst x8, #0x80
 b.ne Lid_skip
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 add x10, sp, #0x10
 adr x11, Lid_digits
 mov w14, #80
 strb w14, [x10], #1
 ldr w14, [x12, #3628]
 add w14, w14, #48
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 ldr w13, [x12, #3624]
 bl Lid_hex
 mov w14, #32
 strb w14, [x10], #1
 mov w14, #71
 strb w14, [x10], #1
 ldr w14, [x12, #3636]
 add w14, w14, #48
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 ldr w13, [x12, #3632]
 bl Lid_hex
 mov w14, #32
 strb w14, [x10], #1
 mov w14, #73
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 ldr w13, [sp, #0x88]
 bl Lid_hex
 strb wzr, [x10]
 add x8, sp, #0x10
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 adrp x19, _test_buffer@PAGE
 add x19, x19, _test_buffer@PAGEOFF
 add x9, x19, #4000
 ldar x8, [x9]
 cbz x8, Lsynthetic_skip
 add x9, x19, #4048
 mov w10, #16
Lsynthetic_claim:
 ldaxr w11, [x9]
 cbnz w11, Lsynthetic_claimed
 mov w11, #1
 stlxr w12, w11, [x9]
 cbz w12, Lsynthetic_run
 subs w10, w10, #1
 b.ne Lsynthetic_claim
 add x9, x19, #4036
 mov w10, #1
 stlr w10, [x9]
 b Lsynthetic_skip
Lsynthetic_claimed:
 clrex
 b Lsynthetic_skip
Lsynthetic_run:
 mov w19, #0
 mov w21, #0x5349
 movk w21, #0x5354, lsl #16
 bl Lsynthetic_store
 mov w2, #0
 mov w3, #0x5242
 movk w3, #0x5354, lsl #16
 bl Lsynthetic_bridge
Lsynthetic_skip:
 adrp x19, _test_buffer@PAGE
 add x19, x19, _test_buffer@PAGEOFF
 sub sp, sp, #0x80
 add x10, sp, #0x10
 adr x11, Lid_digits
 mov w14, #89
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 add x12, x19, #4000
 ldar x13, [x12]
 cmp x13, #0
 cset w13, ne
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4016
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4020
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4024
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4028
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4032
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4008
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4012
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4036
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #4044
 ldar w13, [x12]
 bl Lid_hex
 strb wzr, [x10]
 add x8, sp, #0x10
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 add sp, sp, #0x80
 adrp x19, _test_buffer@PAGE
 add x19, x19, _test_buffer@PAGEOFF
 add x10, sp, #0x10
 adr x11, Lid_digits
 mov w14, #90
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 add x12, x19, #3712
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #3716
 ldar w13, [x12]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #3720
 ldar w20, [x12]
 mov w13, w20
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 add x12, x19, #3724
 ldar w13, [x12]
 bl Lid_hex
 strb wzr, [x10]
 add x8, sp, #0x10
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 cmp w20, #16
 b.ls Ltrace_count_ok
 mov w20, #16
Ltrace_count_ok:
 mov w21, #0
Ltrace_log_loop:
 cmp w21, w20
 b.hs Ltrace_log_done
 add x22, x19, #3744
 add x22, x22, w21, uxtw #4
 add x12, x22, #12
 ldar w13, [x12]
 cbz w13, Ltrace_log_unready
 add x10, sp, #0x10
 adr x11, Lid_digits
 mov w14, #87
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 ldr w13, [x22]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 ldr w13, [x22, #4]
 bl Lid_hex
 mov w14, #58
 strb w14, [x10], #1
 ldr w13, [x22, #8]
 bl Lid_hex
 strb wzr, [x10]
 add x8, sp, #0x10
 str x8, [sp]
 b Ltrace_emit
Ltrace_log_unready:
 adr x8, Ltrace_unready
 str x8, [sp]
Ltrace_emit:
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 add w21, w21, #1
 b Ltrace_log_loop
Ltrace_log_done:
 b Ltrace_after_text
Ltrace_unready:
 .asciz "W=UNREADY"
.p2align 2
Ltrace_after_text:
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 add x10, x12, #3696
 ldar w13, [x10]
 cbz w13, Lcontrol_nolog
 add x10, sp, #0x10
 adr x11, Lid_digits
 mov w14, #67
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 ldr w13, [x12, #3692]
 bl Lid_hex
 strb wzr, [x10]
 add x8, sp, #0x10
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
Lcontrol_nolog:
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 add x10, x12, #3680
 ldar w13, [x10]
 cbz w13, Lpower_nolog
 add x10, sp, #0x10
 adr x11, Lid_digits
 mov w14, #84
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 ldr w13, [x12, #3676]
 bl Lid_hex
 strb wzr, [x10]
 add x8, sp, #0x10
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
Lpower_nolog:
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 add x10, x12, #3664
 ldar w13, [x10]
 cbz w13, Lmiddle_nolog
 add x10, sp, #0x10
 adr x11, Lid_digits
 mov w14, #77
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 ldr w13, [x12, #3660]
 bl Lid_hex
 strb wzr, [x10]
 add x8, sp, #0x10
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
Lmiddle_nolog:
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 ldr w13, [x12, #3628]
 cbz w13, Lid_skip
 ldr x0, [x12, #3640]
 cbz x0, Lid_skip
 add x10, x12, #3648
Lpage5_claim:
 ldaxr w13, [x10]
 cbnz w13, Lpage5_already
 mov w13, #1
 stlxr w14, w13, [x10]
 cbnz w14, Lpage5_claim
 adr x8, Lpage5_before
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 adrp x12, _test_buffer@PAGE
 add x12, x12, _test_buffer@PAGEOFF
 ldr x0, [x12, #3640]
 // shortcut: the singleton PMGR pointer is sampled during its GFX poll; upgrade if the platform lifecycle changes.
 ldr x8, [x0]
 cbz x8, Lid_skip
 ldr x8, [x8, #0x980]
 cbz x8, Lid_skip
 mov x1, #0
 mov w2, #0x5000
 add w2, w2, #J81_PAGE5_OFFSET
 mov x3, #0
 blr x8
 str w0, [sp, #0x10]
 add x10, sp, #0x14
 adr x11, Lid_digits
 mov w14, #81
 strb w14, [x10], #1
 mov w14, #61
 strb w14, [x10], #1
 ldr w13, [sp, #0x10]
 bl Lid_hex
 strb wzr, [x10]
 add x8, sp, #0x14
 str x8, [sp]
 adrp x0, _test_format@PAGE
 add x0, x0, _test_format@PAGEOFF
 adrp x16, _fake_logger@PAGE
 add x16, x16, _fake_logger@PAGEOFF
 blr x16
 b Lid_skip
Lpage5_already:
 clrex
Lid_skip:
 ldp q0, q1, [sp, #0x140]
 ldp q2, q3, [sp, #0x160]
 ldp q4, q5, [sp, #0x180]
 ldp q6, q7, [sp, #0x1a0]
 ldp q8, q9, [sp, #0x1c0]
 ldp q10, q11, [sp, #0x1e0]
 ldp q12, q13, [sp, #0x200]
 ldp q14, q15, [sp, #0x220]
 ldp q16, q17, [sp, #0x240]
 ldp q18, q19, [sp, #0x260]
 ldp q20, q21, [sp, #0x280]
 ldp q22, q23, [sp, #0x2a0]
 ldp q24, q25, [sp, #0x2c0]
 ldp q26, q27, [sp, #0x2e0]
 ldp q28, q29, [sp, #0x300]
 ldp q30, q31, [sp, #0x320]
 ldr w8, [sp, #8]
 msr fpcr, x8
 ldr w8, [sp, #12]
 msr fpsr, x8
 ldr x8, [sp, #0x138]
 msr nzcv, x8
 ldr x30, [sp, #0x130]
 ldp x0, x1, [sp, #0x40]
 ldp x2, x3, [sp, #0x50]
 ldp x4, x5, [sp, #0x60]
 ldp x6, x7, [sp, #0x70]
 ldp x8, x9, [sp, #0x80]
 ldp x10, x11, [sp, #0x90]
 ldp x12, x13, [sp, #0xa0]
 ldp x14, x15, [sp, #0xb0]
 ldp x16, x17, [sp, #0xc0]
 ldp x18, x19, [sp, #0xd0]
 ldp x20, x21, [sp, #0xe0]
 ldp x22, x23, [sp, #0xf0]
 ldp x24, x25, [sp, #0x100]
 ldp x26, x27, [sp, #0x110]
 ldp x28, x29, [sp, #0x120]
 add sp, sp, #0x340
 and w10, w9, #0xff0000
_j81_page5attribution_identity_resume:
 ret
Lid_hex:
 mov w14, #28
Lid_hex_loop:
 lsr w15, w13, w14
 and w15, w15, #0xf
 ldrb w15, [x11, w15, uxtw]
 strb w15, [x10], #1
 subs w14, w14, #4
 b.ge Lid_hex_loop
 ret
Lpage5_before:
 .asciz "PAGE5-before"
Lid_digits:
 .ascii "0123456789abcdef"
.p2align 3

_j81_page5attribution_end:

.globl _test_entry
_test_entry:
 stp x19, x30, [sp, #-16]!
 mov x19, x0
 movi v0.16b, #0x7e
 movi v31.16b, #0x5b
 adrp x8, _fake_provider@PAGE
 add x8, x8, _fake_provider@PAGEOFF
 bl _j81_page5attribution_clock
 str q0, [x19]
 str q31, [x19, #16]
 ldp x19, x30, [sp], #16
 ret
.globl _test_write
_test_write:
 stp x29, x30, [sp, #-16]!
 adrp x8, _fake_inner@PAGE
 add x8, x8, _fake_inner@PAGEOFF
 bl _j81_page5attribution_write
 ldp x29, x30, [sp], #16
 ret
.globl _test_decision
_test_decision:
 stp x28, x30, [sp, #-48]!
 stp x20, x22, [sp, #16]
 str x24, [sp, #32]
 mov x28, #0x7c
 mov x20, #0
 mov w24, w0
 mov w22, w1
 bl _j81_page5attribution_decision
 mrs x0, nzcv
 ldr x24, [sp, #32]
 ldp x20, x22, [sp, #16]
 ldp x28, x30, [sp], #48
 ret

.globl _test_aggregate
_test_aggregate:
 stp x20, x30, [sp, #-48]!
 stp x25, x26, [sp, #16]
 mov x20, #0x7c
 mov w25, w0
 mov w26, w1
 bl _j81_page5attribution_aggregate
 mrs x0, nzcv
 ldp x25, x26, [sp, #16]
 ldp x20, x30, [sp], #48
 ret
.globl _test_count
_test_count:
 sub sp, sp, #0x70
 stp x28, x30, [sp, #0x50]
 str x24, [sp, #0x40]
 str w0, [sp, #0x3c]
 mov w9, #0x7c
 str w9, [sp, #0x50]
 mov w9, #15
 strb w9, [sp, #0x52]
 mov x28, #0x7c
 mov x9, #0xa0000000
 msr nzcv, x9
 bl _j81_page5attribution_count
 mrs x0, nzcv
 ldr x24, [sp, #0x40]
 ldp x28, x30, [sp, #0x50]
 add sp, sp, #0x70
 ret

.globl _test_choice
_test_choice:
 sub sp, sp, #0x40
 stp x19, x21, [sp]
 stp x24, x25, [sp, #16]
 stp x27, x30, [sp, #32]
 mov x19, x0
 mov w25, w1
 mov w21, w2
 mov w24, #1
 add x27, sp, #0x38
 mov w9, #0x7c
 strh w9, [x27]
 bl _j81_page5attribution_choice
 mrs x0, nzcv
 ldp x27, x30, [sp, #32]
 ldp x24, x25, [sp, #16]
 ldp x19, x21, [sp]
 add sp, sp, #0x40
 ret

.globl _test_pm
_test_pm:
 sub sp, sp, #0x50
 stp x19,x20,[sp]
 stp x21,x22,[sp,#16]
 stp x23,x30,[sp,#32]
 str x25,[sp,#48]
 adrp x25, _test_pmgr@PAGE
 add x25, x25, _test_pmgr@PAGEOFF
 mov w19,w1
 mov w20,w2
 mov w23,w3
 mov w21,#0xf0
 mov w22,#0xf0
 bl _j81_page5attribution_pm_poll
 mrs x1,nzcv
 ldr x25,[sp,#48]
 ldp x23,x30,[sp,#32]
 ldp x21,x22,[sp,#16]
 ldp x19,x20,[sp]
 add sp,sp,#0x50
 ret
.globl _test_gpc
_test_gpc:
 stp x29,x30,[sp,#-16]!
 mov w8,w0
 mov x9,#0xa0000000
 msr nzcv,x9
 bl _j81_page5attribution_gpc_poll
 mrs x0,nzcv
 ldp x29,x30,[sp],#16
 ret
.globl _test_identity
_test_identity:
 stp x29,x30,[sp,#-16]!
 mov w9,w0
 mov w8,w1
 bl _j81_page5attribution_identity
 ldp x29,x30,[sp],#16
 ret

.globl _test_power
_test_power:
 stp x29,x30,[sp,#-16]!
 adrp x8, _fake_power@PAGE
 add x8, x8, _fake_power@PAGEOFF
 bl _j81_page5attribution_power
 ldp x29,x30,[sp],#16
 ret
.globl _test_control
_test_control:
 stp x29,x30,[sp,#-16]!
 bl _j81_page5attribution_control
 mov w0,w8
 ldp x29,x30,[sp],#16
 ret
.globl _test_store
_test_store:
 sub sp,sp,#0x40
 stp x19,x20,[sp]
 stp x21,x22,[sp,#16]
 stp x23,x30,[sp,#32]
 mov x8,x0
 mov x23,x1
 mov w22,w2
 mov w19,w3
 mov w20,w4
 mov w21,w5
 bl _j81_page5attribution_store
 ldp x23,x30,[sp,#32]
 ldp x21,x22,[sp,#16]
 ldp x19,x20,[sp]
 add sp,sp,#0x40
 ret

.globl _test_readsite
_test_readsite:
 sub sp, sp, #0x30
 stp x19, x20, [sp]
 stp x21, x22, [sp, #16]
 str x30, [sp, #32]
 mov x8, x0
 mov x22, x1
 mov w19, w2
 mov w21, w3
 mov w20, w4
 bl _j81_page5attribution_readsite
 ldr x30, [sp, #32]
 ldp x21, x22, [sp, #16]
 ldp x19, x20, [sp]
 add sp, sp, #0x30
 ret
.globl _test_bridge
_test_bridge:
 stp x29, x30, [sp, #-16]!
 mov x8, x0
 mov w2, w1
 bl _j81_page5attribution_bridge
 ldp x29, x30, [sp], #16
 ret
