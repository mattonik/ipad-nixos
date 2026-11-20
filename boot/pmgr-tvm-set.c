/*
 * One-shot, guarded SoC TVM (soc-tvm) enable for the J81 observer experiment.
 * Reads PMGR region 0 +0x2d000 (physical 0x20e02d000) through /dev/mem. Only if the word reads
 * exactly 0 it stores 1 (the stock soc-tvm request is old|1 at this address (group 3, rail 1, no enable poll)), then reads it
 * back. Any other pre-value: nothing is written. Waits for "WRITE\n" on stdin after announcing
 * the pre-value, so the harness controls the moment. No other address, no GPU/GPC/bridge access.
 * Freestanding (raw syscalls) so it builds with a plain AArch64 clang + lld and no libc.
 */
typedef unsigned long u64; typedef unsigned int u32;
#define SYS_openat 56
#define SYS_read 63
#define SYS_write 64
#define SYS_exit 93
#define SYS_mmap 222
static long sc(long n, long a, long b, long c, long d, long e, long f)
{
	register long x8 __asm__("x8") = n, x0 __asm__("x0") = a, x1 __asm__("x1") = b,
		x2 __asm__("x2") = c, x3 __asm__("x3") = d, x4 __asm__("x4") = e, x5 __asm__("x5") = f;
	__asm__ volatile("svc 0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5) : "memory");
	return x0;
}
static void out(const char *s)
{
	long n = 0; while (s[n]) n++;
	sc(SYS_write, 1, (long)s, n, 0, 0, 0);
}
static void hex(const char *tag, u32 v)
{
	char b[48]; int n = 0; const char *p;
	for (p = tag; *p; p++) b[n++] = *p;
	b[n++] = '0'; b[n++] = 'x';
	for (int i = 28; i >= 0; i -= 4) b[n++] = "0123456789abcdef"[(v >> i) & 15];
	b[n++] = '\n'; b[n] = 0;
	out(b);
}
__attribute__((noreturn)) static void quit(int code)
{
	sc(SYS_exit, code, 0, 0, 0, 0, 0);
	for (;;) ;
}
void _start(void)
{
	/* O_RDWR=2, O_SYNC=0x101000 (aarch64 generic) */
	long fd = sc(SYS_openat, -100, (long)"/dev/mem", 2 | 0x101000, 0, 0, 0);
	if (fd < 0) { out("stage=tvm-error open\n"); quit(1); }
	/* PROT_READ|PROT_WRITE=3, MAP_SHARED=1 */
	volatile u32 *page = (volatile u32 *)sc(SYS_mmap, 0, 0x1000, 3, 1, fd, 0x20e02d000L);
	if ((long)page < 0 && (long)page > -4096) { out("stage=tvm-error mmap\n"); quit(1); }
	u32 old = page[0];
	out("stage=before-tvm-write address=0x20e02d000\n");
	hex("old=", old);
	char reply[8]; long n = sc(SYS_read, 0, (long)reply, 6, 0, 0, 0);
	if (n != 6 || reply[0] != 'W' || reply[1] != 'R' || reply[2] != 'I' || reply[3] != 'T' || reply[4] != 'E' || reply[5] != '\n') {
		out("stage=tvm-aborted no-go\n"); quit(1);
	}
	if (old != 0) { out("stage=tvm-skipped pre-value-not-zero\n"); quit(3); }
	page[0] = 1;
	__asm__ volatile("dsb sy" ::: "memory");
	u32 now = page[0];
	hex("new=", now);
	out("stage=after-tvm-write\n");
	quit(now == 1 ? 0 : 4);
}
