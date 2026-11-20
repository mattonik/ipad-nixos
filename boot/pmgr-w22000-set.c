/*
 * One-shot, guarded store of 0x80000000 to PMGR region 0 +0x22000 (physical 0x20e022000) for the J81
 * observer experiment. iPadOS reads this word as 0x80000000 before the GPC request and after it; Linux
 * (checkm8 -> Pongo -> m1n1) reads 0x00000000. The bootloaders (iBoot, LLB) clear bit 31 of this word
 * and the stock kernel setter was not located, so this is a replay of the observed end state, not of
 * a traced instruction sequence.
 *
 * Reads the word through /dev/mem, announces old=, waits for "WRITE\n" (the host controls the moment),
 * stores 0x80000000 only if the pre-value is exactly 0, dsb sy, reads back, requires readback ==
 * 0x80000000. Exactly one 32-bit store, no other address. Freestanding (raw syscalls), no libc.
 */
typedef unsigned long u64; typedef unsigned int u32;
#define SYS_openat 56
#define SYS_read 63
#define SYS_write 64
#define SYS_exit 93
#define SYS_mmap 222
#define ADDR 0x20e022000UL
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
	if (fd < 0) { out("stage=w22000-error open\n"); quit(1); }
	volatile u32 *page = (volatile u32 *)sc(SYS_mmap, 0, 0x1000, 3, 1, fd, (long)ADDR);
	if ((long)page < 0 && (long)page > -4096) { out("stage=w22000-error mmap\n"); quit(1); }
	u32 old = page[0];
	out("stage=before-w22000-write address=0x20e022000\n");
	hex("old=", old);
	char reply[8]; long n = sc(SYS_read, 0, (long)reply, 6, 0, 0, 0);
	if (n != 6 || reply[0] != 'W' || reply[1] != 'R' || reply[2] != 'I' || reply[3] != 'T' || reply[4] != 'E' || reply[5] != '\n') {
		out("stage=w22000-aborted no-go\n"); quit(1);
	}
	if (old != 0) { out("stage=w22000-skipped pre-value-not-zero\n"); quit(3); }
	page[0] = 0x80000000U;
	__asm__ volatile("dsb sy" ::: "memory");
	u32 now = page[0];
	hex("new=", now);
	out("stage=after-w22000-write\n");
	quit(now == 0x80000000U ? 0 : 4);
}
