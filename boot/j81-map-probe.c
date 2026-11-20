/*
 * Mapping-only probe for the J81 core-ID hang. Freestanding (raw syscalls), no libc.
 *
 * Maps three physical pages through /dev/mem exactly as boot/gpu-core-id-gated.c does for its
 * reads (open O_RDONLY|O_SYNC, mmap length 0x1000 PROT_READ MAP_SHARED at the page): the page-5
 * page 0x20e005000 and the GPC state page 0x201e01000 (both read successfully before), and the
 * GPU core page 0x201000000. For each mapping it asks the j81-map-walk module (same process, so
 * current->mm is this process) how the virtual address is translated and prints one line.
 *
 * It NEVER dereferences a mapped address: no device read, no device write. The only file writes
 * are the virtual address into the module's sysfs `va` file.
 *   usage: j81-map-probe     (after insmod j81-map-walk.ko)
 */
typedef unsigned long u64; typedef unsigned int u32;
#define SYS_openat 56
#define SYS_close 57
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
static long slen(const char *s) { long n = 0; while (s[n]) n++; return n; }
static void out(const char *s) { sc(SYS_write, 1, (long)s, slen(s), 0, 0, 0); }
static int puthex(char *b, int n, u64 v)
{
	b[n++] = '0'; b[n++] = 'x';
	for (int i = 60; i >= 0; i -= 4) b[n++] = "0123456789abcdef"[(v >> i) & 15];
	return n;
}
static int puts_(char *b, int n, const char *s) { while (*s) b[n++] = *s++; return n; }
__attribute__((noreturn)) static void quit(int c) { sc(SYS_exit, c, 0, 0, 0, 0, 0); for (;;) ; }

static void walk(const char *name, u64 pa, long memfd)
{
	char b[160]; int n;
	volatile u32 *map = (volatile u32 *)sc(SYS_mmap, 0, 0x1000, 1 /* PROT_READ */, 1 /* MAP_SHARED */, memfd, (long)pa);
	if ((long)map < 0 && (long)map > -4096) { out("map name="); out(name); out(" result=mmap-failed\n"); return; }
	n = puts_(b, 0, "map name="); n = puts_(b, n, name); n = puts_(b, n, " pa="); n = puthex(b, n, pa);
	n = puts_(b, n, " va="); n = puthex(b, n, (u64)map); b[n++] = '\n'; b[n] = 0; out(b);
	/* hand the address to the module, then read its answer: both from this process */
	long vf = sc(SYS_openat, -100, (long)"/sys/devices/j81-map-walk/va", 1 /* O_WRONLY */, 0, 0, 0);
	if (vf < 0) { out("walk result=no-va-file\n"); return; }
	n = puthex(b, 0, (u64)map); b[n++] = '\n'; b[n] = 0;
	sc(SYS_write, vf, (long)b, n, 0, 0, 0); sc(SYS_close, vf, 0, 0, 0, 0, 0);
	long wf = sc(SYS_openat, -100, (long)"/sys/devices/j81-map-walk/walk", 0 /* O_RDONLY */, 0, 0, 0);
	if (wf < 0) { out("walk result=no-walk-file\n"); return; }
	static char res[2048];
	long r = sc(SYS_read, wf, (long)res, sizeof res - 1, 0, 0, 0);
	sc(SYS_close, wf, 0, 0, 0, 0, 0);
	if (r < 0) { out("walk result=read-failed\n"); return; }
	res[r] = 0;
	out("walk name="); out(name); out(" "); out(res);
}
void _start(void)
{
	long memfd = sc(SYS_openat, -100, (long)"/dev/mem", 0 /* O_RDONLY */ | 0x101000 /* O_SYNC */, 0, 0, 0);
	if (memfd < 0) { out("stage=finished rc=1 open-failed\n"); quit(1); }
	out("stage=before-map-walk\n");
	walk("page5", 0x20e005000UL, memfd);
	walk("gpc-state", 0x201e01000UL, memfd);
	walk("core", 0x201000000UL, memfd);
	out("stage=finished rc=0\n");
	quit(0);
}
