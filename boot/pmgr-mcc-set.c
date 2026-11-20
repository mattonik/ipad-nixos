/*
 * One-shot, guarded replay of the stock ApplePMGR MCC enable loop (19H394 J81 method 0x6c8a0c4, slot +0x688,
 * enable=1) for the five words that differ on Linux. The stock loop walks region-0 +0x22000..+0x22180 in steps
 * of 0x10 (skipping +0x22030..+0x22070 and +0x22120) and requests (old & 0x7fffffff) | 0x80000000 for each of
 * 19 words; on a fresh Linux boot 14 already have bit 31 set, five do not:
 *     +0x22000 00000000, +0x22090 09070300, +0x220a0 09040300, +0x220b0 09060300, +0x22130 09040300.
 * Maps PMGR region 0 +0x22000 through /dev/mem, announces every old value, waits for "WRITE\n" (the host
 * controls the moment), refuses (no store at all) unless ALL five old words equal the expected Linux values
 * exactly, then in stock order stores (old & 0x7fffffff) | 0x80000000 to each, dsb sy, reads back, and
 * requires readback == the stored word. One store instruction (in a loop, five executions), no other address.
 * Freestanding (raw syscalls), no libc.
 */
typedef unsigned long u64; typedef unsigned int u32;
#define SYS_openat 56
#define SYS_read 63
#define SYS_write 64
#define SYS_exit 93
#define SYS_mmap 222
#define BASE 0x20e022000UL
static const u32 OFFS[5] = { 0x000, 0x090, 0x0a0, 0x0b0, 0x130 };
static const u32 OLDS[5] = { 0x00000000U, 0x09070300U, 0x09040300U, 0x09060300U, 0x09040300U };
static long sc(long n, long a, long b, long c, long d, long e, long f)
{
	register long x8 __asm__("x8") = n, x0 __asm__("x0") = a, x1 __asm__("x1") = b,
		x2 __asm__("x2") = c, x3 __asm__("x3") = d, x4 __asm__("x4") = e, x5 __asm__("x5") = f;
	__asm__ volatile("svc 0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5) : "memory");
	return x0;
}
static void out(const char *s) { long n = 0; while (s[n]) n++; sc(SYS_write, 1, (long)s, n, 0, 0, 0); }
static void line(const char *tag, u32 off, u32 v)
{
	char b[64]; int n = 0; const char *p;
	for (p = tag; *p; p++) b[n++] = *p;
	b[n++] = ' '; b[n++] = '0'; b[n++] = 'x';
	for (int i = 20; i >= 0; i -= 4) b[n++] = "0123456789abcdef"[((0x22000 + off) >> i) & 15];
	b[n++] = ' '; b[n++] = '0'; b[n++] = 'x';
	for (int i = 28; i >= 0; i -= 4) b[n++] = "0123456789abcdef"[(v >> i) & 15];
	b[n++] = '\n'; b[n] = 0;
	out(b);
}
__attribute__((noreturn)) static void quit(int code) { sc(SYS_exit, code, 0, 0, 0, 0, 0); for (;;) ; }
void _start(void)
{
	long fd = sc(SYS_openat, -100, (long)"/dev/mem", 2 | 0x101000, 0, 0, 0);
	if (fd < 0) { out("stage=mcc-error open\n"); quit(1); }
	volatile u32 *page = (volatile u32 *)sc(SYS_mmap, 0, 0x1000, 3, 1, fd, (long)BASE);
	if ((long)page < 0 && (long)page > -4096) { out("stage=mcc-error mmap\n"); quit(1); }
	u32 old[5];
	out("stage=before-mcc-write base=0x20e022000 words=5\n");
	for (int i = 0; i < 5; i++) { old[i] = page[OFFS[i] >> 2]; line("old", OFFS[i], old[i]); }
	char reply[8]; long n = sc(SYS_read, 0, (long)reply, 6, 0, 0, 0);
	if (n != 6 || reply[0] != 'W' || reply[1] != 'R' || reply[2] != 'I' || reply[3] != 'T' || reply[4] != 'E' || reply[5] != '\n') {
		out("stage=mcc-aborted no-go\n"); quit(1);
	}
	for (int i = 0; i < 5; i++)
		if (old[i] != OLDS[i]) { out("stage=mcc-skipped pre-value-not-expected\n"); quit(3); }
	for (int i = 0; i < 5; i++) {
		u32 want = (old[i] & 0x7fffffffU) | 0x80000000U;
		page[OFFS[i] >> 2] = want;
		__asm__ volatile("dsb sy" ::: "memory");
		u32 now = page[OFFS[i] >> 2];
		line("new", OFFS[i], now);
		if (now != want) { out("stage=mcc-error readback-mismatch\n"); quit(4); }
	}
	out("stage=after-mcc-write\n");
	quit(0);
}
