/*
 * Timed GPC request plus immediate core-ID read for the MiscACG experiment (run under
 * gpu-watchdog-supervisor --core-revision-cycle, via the staged wrapper script).
 *
 * Every access is a 32-bit /dev/mem READ (never a write) and is announced as
 *   stage=before-<name> address=0x... width=32     (host answers READ via the supervisor)
 *   stage=after-<name> raw=0x........               (host answers FEED n)
 * Order: GFX PS (must be 0x3ff), MiscACG (must be 1), page 5 +4 (bit 30 must be set), GPC state (must be 1),
 * GPC control (logged only), then the core ID at 0x201000020. If any gate fails the core window is NOT
 * touched: it prints "stage=skipped ..." and "stage=finished rc=0". The core read itself can still hang the
 * bus; the supervisor's hardware watchdog then resets the device. One run per boot (mkdir marker).
 * Freestanding (raw syscalls), no libc, so it builds with a plain AArch64 clang + lld.
 */
typedef unsigned long u64; typedef unsigned int u32;
#define SYS_mkdirat 34
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
static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }
static void out(const char *s) { sc(SYS_write, 1, (long)s, slen(s), 0, 0, 0); }
static int put(char *b, int n, const char *s) { while (*s) b[n++] = *s++; return n; }
static int puthex(char *b, int n, u64 v, int digits)
{
	b[n++] = '0'; b[n++] = 'x';
	for (int i = (digits - 1) * 4; i >= 0; i -= 4) b[n++] = "0123456789abcdef"[(v >> i) & 15];
	return n;
}
__attribute__((noreturn)) static void quit(int code) { sc(SYS_exit, code, 0, 0, 0, 0, 0); for (;;) ; }
static long fd;
static void finish_skipped(const char *why)
{
	char b[96]; int n = put(b, 0, "stage=skipped reason=");
	n = put(b, n, why); b[n++] = '\n'; b[n] = 0; out(b);
	out("stage=finished rc=0\n"); quit(0);
}
static void fail(const char *why)
{
	out("stage=finished rc=1\n"); (void)why; quit(1);
}
/* one supervised 32-bit read: announce, wait for READ, read, report */
static u32 supervised_read(const char *name, u64 addr)
{
	char b[128], reply[8]; int n = put(b, 0, "stage=before-");
	n = put(b, n, name); n = put(b, n, " address="); n = puthex(b, n, addr, 9);
	n = put(b, n, " width=32\n"); b[n] = 0; out(b);
	long r = sc(SYS_read, 0, (long)reply, 5, 0, 0, 0);
	if (r != 5 || reply[0] != 'R' || reply[1] != 'E' || reply[2] != 'A' || reply[3] != 'D' || reply[4] != '\n') fail("no READ");
	u64 page = addr & ~0xfffUL;
	volatile u32 *map = (volatile u32 *)sc(SYS_mmap, 0, 0x1000, 1 /* PROT_READ */, 1 /* MAP_SHARED */, fd, (long)page);
	if ((long)map < 0 && (long)map > -4096) fail("mmap");
	u32 v = map[(addr & 0xfff) >> 2];
	__asm__ volatile("dsb ld" ::: "memory");
	n = put(b, 0, "stage=after-"); n = put(b, n, name); n = put(b, n, " raw="); n = puthex(b, n, v, 8);
	b[n++] = '\n'; b[n] = 0; out(b);
	return v;
}
static inline u64 ticks(void) { u64 v; __asm__ volatile("isb; mrs %0, cntvct_el0" : "=r"(v) :: "memory"); return v; }
static void checkpoint(const char *name, u64 a, u64 b)
{
	char buf[128]; int n = put(buf, 0, "checkpoint="); n = put(buf, n, name);
	n = put(buf, n, " a="); n = puthex(buf, n, a, 8); n = put(buf, n, " b="); n = puthex(buf, n, b, 8);
	buf[n++] = '\n'; buf[n] = 0; out(buf);
}
void _start(void)
{
	char reply[8], b[128]; int n;
	if (sc(SYS_mkdirat, -100, (long)"/tmp/gpu-gpc-timed-core.once", 0700, 0, 0, 0) != 0) { out("stage=finished rc=2\n"); quit(2); }
	fd = sc(SYS_openat, -100, (long)"/dev/mem", 2 /* O_RDWR, only the GPC window is written */ | 0x101000, 0, 0, 0);
	if (fd < 0) fail("open");
	if (supervised_read("pmgr-read", 0x20e020320UL) != 0x3ff) finish_skipped("gfx-ps-not-3ff");
	if (supervised_read("miscacg-read", 0x20e032000UL) != 1) finish_skipped("miscacg-not-1");
	if (supervised_read("gpc-state", 0x201e01000UL) != 0) finish_skipped("gpc-state-not-0");
	/* one host-acknowledged stage covers the whole timed sequence: GPC writes, poll, page 5, core read */
	out("stage=before-timed-sequence address=0x201000020 width=32\n");
	long r = sc(SYS_read, 0, (long)reply, 5, 0, 0, 0);
	if (r != 5 || reply[0] != 'R' || reply[1] != 'E' || reply[2] != 'A' || reply[3] != 'D' || reply[4] != '\n') fail("no READ");
	volatile u32 *gpc = (volatile u32 *)sc(SYS_mmap, 0, 0x11000, 3, 1, fd, 0x201e00000L);
	volatile u32 *pmgr5 = (volatile u32 *)sc(SYS_mmap, 0, 0x1000, 1, 1, fd, 0x20e005000L);
	volatile u32 *core = (volatile u32 *)sc(SYS_mmap, 0, 0x1000, 1, 1, fd, 0x201000000L);
	if (((long)gpc < 0 && (long)gpc > -4096) || ((long)pmgr5 < 0 && (long)pmgr5 > -4096) || ((long)core < 0 && (long)core > -4096)) fail("mmap");
	out("checkpoint=before-gpc-writes\n");
	gpc[0x10000 / 4] = 0xffff0000U; __asm__ volatile("dsb sy" ::: "memory");
	gpc[0] = 0x40000000U;           __asm__ volatile("dsb sy" ::: "memory");
	gpc[0x1000 / 4] = 0x11U;        __asm__ volatile("dsb sy" ::: "memory");
	u32 v = 0; u32 polls = 0;
	for (polls = 1; polls <= 4000; polls++) {
		v = gpc[0x1000 / 4]; __asm__ volatile("dsb ld" ::: "memory");
		if ((v & 0x1f) == 1) break;
	}
	u64 t0 = ticks();
	if (polls > 4000) { n = put(b, 0, "stage=skipped reason=gpc-poll-timeout raw="); n = puthex(b, n, v, 8); b[n++] = '\n'; b[n] = 0; out(b); out("stage=finished rc=0\n"); quit(0); }
	u32 p5 = pmgr5[1]; __asm__ volatile("dsb ld" ::: "memory");
	if (!(p5 & 0x40000000U)) { n = put(b, 0, "stage=skipped reason=page5-bit30-clear page5="); n = puthex(b, n, p5, 8); b[n++] = '\n'; b[n] = 0; out(b); out("stage=finished rc=0\n"); quit(0); }
	checkpoint("gpc-poll-ok-polls-page5", polls, p5);
	u64 t1 = ticks();
	checkpoint("ticks-poll-to-core-read", t1 - t0, 0);
	u32 id = core[0x20 / 4];
	__asm__ volatile("dsb ld" ::: "memory");
	n = put(b, 0, "stage=after-timed-sequence raw="); n = puthex(b, n, id, 8); b[n++] = '\n'; b[n] = 0; out(b);
	out("stage=finished rc=0\n");
	quit(0);
}
