/*
 * One-shot, guarded replay of ApplePMGR's clock-word update for the J81 observer experiment.
 * Stock 19H394 method 0xfffffff006c8872c does, for PMGR region 0 +0x1008 and +0x4008:
 *     new = (old & 0x3fffffff) | 0x40000000;  store new
 * (bits 31:30 become 01, the low 30 bits are kept). iPadOS reads 0x40480348 / 0x48480348 before the
 * GPC request, Linux holds 0x80480348 / 0x88480348.
 *
 * Built twice from this file (-DADDR -DOLD -DNEW -DPAGE_BASE, see boot/build_pmgr_pll_set.sh):
 *   page 1: ADDR 0x20e001008, only if old == 0x80480348, store 0x40480348
 *   page 4: ADDR 0x20e004008, only if old == 0x88480348, store 0x48480348
 * Reads the word through /dev/mem, announces old=, waits for "WRITE\n" (the host controls the moment),
 * stores NEW only if the pre-value is exactly OLD, dsb sy, reads back, and requires readback == NEW.
 * Exactly one 32-bit store, no other address. Freestanding (raw syscalls), no libc.
 */
typedef unsigned long u64; typedef unsigned int u32;
#define SYS_openat 56
#define SYS_read 63
#define SYS_write 64
#define SYS_exit 93
#define SYS_mmap 222
#ifndef ADDR
#error "define ADDR OLD NEW TAG"
#endif
static long sc(long n, long a, long b, long c, long d, long e, long f)
{
	register long x8 __asm__("x8") = n, x0 __asm__("x0") = a, x1 __asm__("x1") = b,
		x2 __asm__("x2") = c, x3 __asm__("x3") = d, x4 __asm__("x4") = e, x5 __asm__("x5") = f;
	__asm__ volatile("svc 0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5) : "memory");
	return x0;
}
static void out(const char *s) { long n = 0; while (s[n]) n++; sc(SYS_write, 1, (long)s, n, 0, 0, 0); }
static void hex(const char *tag, u32 v)
{
	char b[48]; int n = 0; const char *p;
	for (p = tag; *p; p++) b[n++] = *p;
	b[n++] = '0'; b[n++] = 'x';
	for (int i = 28; i >= 0; i -= 4) b[n++] = "0123456789abcdef"[(v >> i) & 15];
	b[n++] = '\n'; b[n] = 0;
	out(b);
}
__attribute__((noreturn)) static void quit(int code) { sc(SYS_exit, code, 0, 0, 0, 0, 0); for (;;) ; }
void _start(void)
{
	long fd = sc(SYS_openat, -100, (long)"/dev/mem", 2 | 0x101000, 0, 0, 0);
	if (fd < 0) { out("stage=" TAG "-error open\n"); quit(1); }
	volatile u32 *page = (volatile u32 *)sc(SYS_mmap, 0, 0x1000, 3, 1, fd, (long)(ADDR & ~0xfffUL));
	if ((long)page < 0 && (long)page > -4096) { out("stage=" TAG "-error mmap\n"); quit(1); }
	volatile u32 *word = page + ((ADDR & 0xfff) >> 2);
	u32 old = *word;
	out("stage=before-" TAG "-write address=" ADDR_STR "\n");
	hex("old=", old);
	char reply[8]; long n = sc(SYS_read, 0, (long)reply, 6, 0, 0, 0);
	if (n != 6 || reply[0] != 'W' || reply[1] != 'R' || reply[2] != 'I' || reply[3] != 'T' || reply[4] != 'E' || reply[5] != '\n') {
		out("stage=" TAG "-aborted no-go\n"); quit(1);
	}
	if (old != OLD) { out("stage=" TAG "-skipped pre-value-not-expected\n"); quit(3); }
	if (((old & 0x3fffffffU) | 0x40000000U) != NEW) { out("stage=" TAG "-skipped transform-mismatch\n"); quit(3); }
	*word = NEW;
	__asm__ volatile("dsb sy" ::: "memory");
	u32 now = *word;
	hex("new=", now);
	out("stage=after-" TAG "-write\n");
	quit(now == NEW ? 0 : 4);
}
