// SPDX-License-Identifier: GPL-2.0-only
/*
 * touchdemo: show what the J81 touchscreen reports, on the iPad's own screen.
 *
 * No GPU, no libdrm, no Wayland: it draws into a DRM dumb buffer on simpledrm
 * (/dev/dri/card0, flushed with DIRTYFB) or, failing that, into /dev/fb0. It
 * reads one multi-touch evdev device (protocol B, as apple_z2 reports) and the
 * gpio-keys Home button. Three screens, switched with the bottom buttons or
 * the Home button:
 *
 *   PAINT   a persistent trail per contact, coloured by tracking ID, with a
 *           marker sized from ABS_MT_TOUCH_MAJOR/MINOR and the ID next to it;
 *   GRID    calibration and edge coverage: 128 px cells light up where touched
 *           (the outer ring is outlined until it is covered), and eight
 *           targets record the mean reported offset of a touch on them;
 *   EVENTS  an evtest-style readout: axes, live slots, the latest raw events.
 *
 * The top panel shows report rate, kernel-to-app latency, axis ranges and the
 * live contacts. Zero axis ranges (the apple_z2 geometry-at-discovery case)
 * are reported and replaced by the range seen so far.
 *
 *   touchdemo [--mode paint|grid|events] [--device /dev/input/eventN]
 *             [--fb] [--text] [--no-display] [--duration SEC]
 *             [--swap-xy] [--flip-x] [--flip-y] [--size-scale F]
 *             [--wait SEC] [--keep-console] [--shot-dir DIR] [--font F.psf]
 *   touchdemo --headless WxH --replay FILE [--font F.psf]   (off-hardware test)
 *
 * SIGUSR1 writes a screenshot (PPM) to --shot-dir (default /tmp). SIGINT and
 * SIGTERM restore the console and print a summary. --text prints contact
 * changes to stdout as well (useful over SSH). It writes no hardware register
 * and touches nothing but the display, the console mode and the input nodes.
 */
#include <dirent.h>
#include <drm/drm.h>
#include <drm/drm_mode.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <linux/kd.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define MAX_SLOTS 256
#define MAX_DIRTY 32
#define EVLOG_LINES 64
#define CELL 128
#define MAX_CELLS 1024
#define NTARGETS 8

#define BIT_WORDS(n) (((n) + 8 * sizeof(unsigned long) - 1) / (8 * sizeof(unsigned long)))
#define TEST_BIT(b, a) (((a)[(b) / (8 * sizeof(unsigned long))] >> ((b) % (8 * sizeof(unsigned long)))) & 1UL)

enum mode { MODE_PAINT, MODE_GRID, MODE_EVENTS, MODE_COUNT };
static const char *mode_names[MODE_COUNT] = { "PAINT", "GRID", "EVENTS" };

enum { BTN_PAINT, BTN_GRID, BTN_EVENTS, BTN_CLEAR, BTN_HUD, NBUTTONS };
static const char *button_names[NBUTTONS] = { "PAINT", "GRID", "EVENTS", "CLEAR", "HUD" };

enum owner { OWN_DRAW, OWN_BAR, OWN_HUD };

struct rect { int x0, y0, x1, y1; };

struct axis { int present, min, max, res, fuzz, value; };

enum { AX_X, AX_Y, AX_MAJOR, AX_MINOR, AX_WMAJOR, AX_WMINOR, AX_ORIENT, AX_PRESSURE, AX_SLOT, AX_COUNT };
static const int axis_codes[AX_COUNT] = {
	ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TOUCH_MAJOR, ABS_MT_TOUCH_MINOR,
	ABS_MT_WIDTH_MAJOR, ABS_MT_WIDTH_MINOR, ABS_MT_ORIENTATION, ABS_MT_PRESSURE, ABS_MT_SLOT,
};
static const char *axis_names[AX_COUNT] = {
	"POSITION_X", "POSITION_Y", "TOUCH_MAJOR", "TOUCH_MINOR",
	"WIDTH_MAJOR", "WIDTH_MINOR", "ORIENTATION", "PRESSURE", "SLOT",
};

/* Per-slot values as the kernel last sent them (protocol B). */
struct slotval { int id, x, y, major, minor, wmajor, wminor, orient, pressure; };

/* A committed contact (state at the last SYN_REPORT). */
struct contact {
	int active, id;
	struct slotval v;
	int sx, sy;              /* screen position */
	int psx, psy, has_prev;  /* last trail point */
	struct rect marker;      /* where its marker was drawn */
	int marker_drawn;
	enum owner owner;
	int button;
	int target;              /* GRID target it started on, or -1 */
	double sum_x, sum_y;
	long samples;
	int cell;
	uint64_t down_ns;
};

struct target {
	int x, y;
	int done;
	double dx, dy;
	long samples;
	const char *name;
};

struct font { int w, h, pitch, stride, count; unsigned char *data; };

struct display {
	int w, h;
	uint32_t *back;      /* what is on screen, XRGB8888, w*h */
	uint32_t *canvas;    /* persistent layer under the markers */
	const char *kind;
	/* DRM */
	int drm_fd;
	uint32_t conn_id, crtc_id, fb_id, handle, pitch;
	uint64_t size;
	uint8_t *map;
	struct drm_mode_crtc saved_crtc;
	int have_saved;
	/* fbdev */
	int fb_fd;
	struct fb_var_screeninfo var;
	struct fb_fix_screeninfo fix;
	uint8_t *fbmem;
	size_t fblen;
};

static struct {
	enum mode mode;
	const char *device, *drm_path, *fb_path, *font_path, *replay, *shot_dir;
	int force_fb, text, no_display, keep_console, headless_w, headless_h, zero_axes;
	int swap_xy, flip_x, flip_y, fps;
	double size_scale, duration, wait;
} opt = {
	.mode = MODE_PAINT, .drm_path = "/dev/dri/card0", .fb_path = "/dev/fb0",
	.shot_dir = "/tmp", .fps = 60, .wait = 20,
};

static struct display D;
static struct font F;
static struct axis ax[AX_COUNT];
static struct slotval cur[MAX_SLOTS];
static struct contact con[MAX_SLOTS];
static int cur_slot, nslots = MAX_SLOTS;
static int touch_fd = -1, keys_fd = -1, tty_fd = -1, saved_kd_mode = -1;
static char dev_name[128] = "(none)", dev_path[300] = "";
static int dropped;

static struct rect dirty[MAX_DIRTY];
static int ndirty, full_dirty, hud_due, hud_visible = 1;
static struct rect hud_r, bar_r;

/* statistics */
static uint64_t t_start, total_reports, total_events, contacts_seen;
static int max_simul, rate_hz, rate_count;
static uint64_t rate_t0;
static double lat_sum, lat_ms;
static long lat_n;
static int raw_seen, raw_min_x, raw_max_x, raw_min_y, raw_max_y;
static int major_max_seen;

/* GRID */
static int gcols, grows;
static unsigned int cell_hits[MAX_CELLS];
static unsigned char cell_level[MAX_CELLS];
static struct target targets[NTARGETS];

/* EVENTS log */
static char evlog[EVLOG_LINES][96];
static int evlog_head, evlog_n;

static volatile sig_atomic_t quit, want_shot;
static int shot_seq;

static const uint32_t palette[12] = {
	0xff4040, 0x40c0ff, 0x60ff60, 0xffc020, 0xff60ff, 0x40ffe0,
	0xffffff, 0xff8040, 0xa080ff, 0xc0ff40, 0xff4090, 0x80a0ff,
};
#define C_BG      0x000000
#define C_GRIDLN  0x141414
#define C_PANEL   0x101820
#define C_TEXT    0xe0e0e0
#define C_DIM     0x808080
#define C_WARN    0xffb000
#define C_OK      0x40e060
#define C_BTN     0x203040
#define C_BTN_ON  0x2060a0

static uint64_t now_ns(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static void on_signal(int sig)
{
	if (sig == SIGUSR1)
		want_shot = 1;
	else
		quit = 1;
}

/* ---- dirty rectangles ---------------------------------------------------- */

static int rect_empty(struct rect r) { return r.x0 >= r.x1 || r.y0 >= r.y1; }

static struct rect rect_clip(struct rect r)
{
	if (r.x0 < 0) r.x0 = 0;
	if (r.y0 < 0) r.y0 = 0;
	if (r.x1 > D.w) r.x1 = D.w;
	if (r.y1 > D.h) r.y1 = D.h;
	return r;
}

static int rect_hit(struct rect a, struct rect b)
{
	return a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
}

static int in_rect(struct rect r, int x, int y)
{
	return x >= r.x0 && x < r.x1 && y >= r.y0 && y < r.y1;
}

static struct rect rect_union(struct rect a, struct rect b)
{
	struct rect u = a;

	if (b.x0 < u.x0) u.x0 = b.x0;
	if (b.y0 < u.y0) u.y0 = b.y0;
	if (b.x1 > u.x1) u.x1 = b.x1;
	if (b.y1 > u.y1) u.y1 = b.y1;
	return u;
}

static void mark(struct rect r)
{
	int i;

	r = rect_clip(r);
	if (rect_empty(r) || full_dirty)
		return;
	for (i = 0; i < ndirty; i++) {
		if (rect_hit(dirty[i], r)) {
			dirty[i] = rect_union(dirty[i], r);
			return;
		}
	}
	if (ndirty == MAX_DIRTY) {
		for (i = 1; i < ndirty; i++)
			dirty[0] = rect_union(dirty[0], dirty[i]);
		ndirty = 1;
		dirty[0] = rect_union(dirty[0], r);
		return;
	}
	dirty[ndirty++] = r;
}

static void mark_full(void) { full_dirty = 1; ndirty = 0; }

/* ---- drawing on a buffer -------------------------------------------------- */

static void fill(uint32_t *buf, struct rect r, uint32_t c)
{
	int x, y;

	r = rect_clip(r);
	for (y = r.y0; y < r.y1; y++) {
		uint32_t *p = buf + (size_t)y * D.w;
		for (x = r.x0; x < r.x1; x++)
			p[x] = c;
	}
}

static inline void px(uint32_t *buf, int x, int y, uint32_t c)
{
	if ((unsigned)x < (unsigned)D.w && (unsigned)y < (unsigned)D.h)
		buf[(size_t)y * D.w + x] = c;
}

static void disk(uint32_t *buf, int cx, int cy, int r, uint32_t c)
{
	int x, y;

	for (y = -r; y <= r; y++)
		for (x = -r; x <= r; x++)
			if (x * x + y * y <= r * r)
				px(buf, cx + x, cy + y, c);
}

static void ring(uint32_t *buf, int cx, int cy, int r, int t, uint32_t c)
{
	int x, y, ro = r * r, ri = (r - t) * (r - t);

	if (r - t < 0)
		ri = 0;
	for (y = -r; y <= r; y++)
		for (x = -r; x <= r; x++) {
			int d = x * x + y * y;
			if (d <= ro && d >= ri)
				px(buf, cx + x, cy + y, c);
		}
}

static void thick_line(uint32_t *buf, int x0, int y0, int x1, int y1, int r, uint32_t c)
{
	int dx = x1 - x0, dy = y1 - y0;
	int steps = (abs(dx) > abs(dy) ? abs(dx) : abs(dy));
	int step = r > 1 ? r / 2 : 1, i;

	if (steps == 0) {
		disk(buf, x0, y0, r, c);
		return;
	}
	for (i = 0; i <= steps; i += step)
		disk(buf, x0 + dx * i / steps, y0 + dy * i / steps, r, c);
	disk(buf, x1, y1, r, c);
}

/* Ellipse outline with semi-axes a (along angle) and b, by stamping small disks. */
static void ellipse(uint32_t *buf, int cx, int cy, double a, double b, double ang, int t, uint32_t c)
{
	int i, n = (int)(2 * M_PI * (a > b ? a : b) / 2) + 16;
	double ca = cos(ang), sa = sin(ang);

	for (i = 0; i < n; i++) {
		double th = 2 * M_PI * i / n, ex = a * cos(th), ey = b * sin(th);
		disk(buf, cx + (int)lround(ex * ca - ey * sa), cy + (int)lround(ex * sa + ey * ca), t, c);
	}
}

static void hline(uint32_t *buf, int x0, int x1, int y, int t, uint32_t c)
{
	fill(buf, (struct rect){ x0, y - t / 2, x1, y - t / 2 + t }, c);
}

static void vline(uint32_t *buf, int x, int y0, int y1, int t, uint32_t c)
{
	fill(buf, (struct rect){ x - t / 2, y0, x - t / 2 + t, y1 }, c);
}

static void frame_rect(uint32_t *buf, struct rect r, int t, uint32_t c)
{
	fill(buf, (struct rect){ r.x0, r.y0, r.x1, r.y0 + t }, c);
	fill(buf, (struct rect){ r.x0, r.y1 - t, r.x1, r.y1 }, c);
	fill(buf, (struct rect){ r.x0, r.y0, r.x0 + t, r.y1 }, c);
	fill(buf, (struct rect){ r.x1 - t, r.y0, r.x1, r.y1 }, c);
}

/* ---- text ----------------------------------------------------------------- */

static int text_w(const char *s, int scale) { return (int)strlen(s) * (F.data ? F.w : 8) * scale; }
static int line_h(int scale) { return (F.data ? F.h : 16) * scale; }

static void draw_text(uint32_t *buf, int x, int y, const char *s, uint32_t fg, int scale)
{
	int gx, gy, sx, sy;

	if (!F.data)
		return;
	for (; *s; s++, x += F.w * scale) {
		unsigned char ch = (unsigned char)*s;
		const unsigned char *g;

		if (ch >= F.count)
			ch = '?';
		g = F.data + (size_t)ch * F.stride;
		for (gy = 0; gy < F.h; gy++) {
			const unsigned char *row = g + gy * F.pitch;
			for (gx = 0; gx < F.w; gx++) {
				if (!(row[gx >> 3] & (0x80 >> (gx & 7))))
					continue;
				for (sy = 0; sy < scale; sy++)
					for (sx = 0; sx < scale; sx++)
						px(buf, x + gx * scale + sx, y + gy * scale + sy, fg);
			}
		}
	}
}

static void textf(uint32_t *buf, int x, int y, uint32_t fg, const char *fmt, ...)
	__attribute__((format(printf, 5, 6)));
static void textf(uint32_t *buf, int x, int y, uint32_t fg, const char *fmt, ...)
{
	char s[256];
	va_list ap;

	va_start(ap, fmt);
	vsnprintf(s, sizeof(s), fmt, ap);
	va_end(ap);
	draw_text(buf, x, y, s, fg, 1);
}

/* Read the console's own font (fbcon=font:TER16x32) before leaving text mode. */
static int font_from_console(int fd)
{
	static unsigned char buf[512 * 32 * 4];
	struct console_font_op op = {
		.op = KD_FONT_OP_GET, .width = 32, .height = 32, .charcount = 512, .data = buf,
	};

	if (ioctl(fd, KDFONTOP, &op) < 0)
		return -1;
	F.w = (int)op.width;
	F.h = (int)op.height;
	F.pitch = (F.w + 7) / 8;
	F.stride = F.pitch * 32;
	F.count = (int)op.charcount;
	F.data = buf;
	return 0;
}

/* PSF1 or PSF2 file (uncompressed), for --font and the headless test. */
static int font_from_psf(const char *path)
{
	FILE *f = fopen(path, "rb");
	unsigned char h[32];
	long len;

	if (!f)
		return -1;
	fseek(f, 0, SEEK_END);
	len = ftell(f);
	fseek(f, 0, SEEK_SET);
	if (len < 32 || fread(h, 1, 32, f) != 32)
		goto bad;
	if (h[0] == 0x36 && h[1] == 0x04) {
		F.w = 8;
		F.h = h[3];
		F.pitch = 1;
		F.stride = h[3];
		F.count = (h[2] & 1) ? 512 : 256;
		fseek(f, 4, SEEK_SET);
	} else if (h[0] == 0x72 && h[1] == 0xb5 && h[2] == 0x4a && h[3] == 0x86) {
		uint32_t hdr = h[8] | h[9] << 8 | h[10] << 16 | (uint32_t)h[11] << 24;

		F.count = (int)(h[16] | h[17] << 8 | h[18] << 16 | (uint32_t)h[19] << 24);
		F.stride = (int)(h[20] | h[21] << 8 | h[22] << 16 | (uint32_t)h[23] << 24);
		F.h = (int)(h[24] | h[25] << 8 | h[26] << 16 | (uint32_t)h[27] << 24);
		F.w = (int)(h[28] | h[29] << 8 | h[30] << 16 | (uint32_t)h[31] << 24);
		F.pitch = (F.w + 7) / 8;
		fseek(f, (long)hdr, SEEK_SET);
	} else {
		goto bad;
	}
	if (F.count > 512)
		F.count = 512;
	F.data = malloc((size_t)F.count * F.stride);
	if (!F.data || fread(F.data, (size_t)F.stride, (size_t)F.count, f) != (size_t)F.count)
		goto bad;
	fclose(f);
	return 0;
bad:
	fclose(f);
	free(F.data);
	memset(&F, 0, sizeof(F));
	return -1;
}

/* ---- display backends ------------------------------------------------------ */

static int drm_ioctl(int fd, unsigned long req, void *arg)
{
	int r;

	do {
		r = ioctl(fd, req, arg);
	} while (r < 0 && (errno == EINTR || errno == EAGAIN));
	return r;
}

static int drm_open(void)
{
	struct drm_mode_card_res res = { 0 };
	uint32_t conns[16], encs[16], crtcs[16], fbs[16];
	struct drm_mode_modeinfo mode = { 0 }, modes[64];
	uint32_t i, enc_id = 0;
	int fd, found = 0;

	fd = open(opt.drm_path, O_RDWR | O_CLOEXEC);
	if (fd < 0)
		return -1;
	ioctl(fd, DRM_IOCTL_SET_MASTER, 0);
	if (drm_ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, &res) < 0)
		goto fail;
	if (res.count_connectors > 16 || res.count_encoders > 16 || res.count_crtcs > 16 || res.count_fbs > 16)
		goto fail;
	res.connector_id_ptr = (uintptr_t)conns;
	res.encoder_id_ptr = (uintptr_t)encs;
	res.crtc_id_ptr = (uintptr_t)crtcs;
	res.fb_id_ptr = (uintptr_t)fbs;
	if (drm_ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, &res) < 0 || !res.count_crtcs)
		goto fail;

	for (i = 0; i < res.count_connectors && !found; i++) {
		struct drm_mode_get_connector c = { .connector_id = conns[i] };

		if (drm_ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, &c) < 0)
			continue;
		if (c.connection != 1 || !c.count_modes)
			continue;
		if (c.count_modes > 64)
			c.count_modes = 64;
		c.count_props = 0;
		c.count_encoders = 0;
		c.modes_ptr = (uintptr_t)modes;
		if (drm_ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, &c) < 0 || !c.count_modes)
			continue;
		mode = modes[0];
		for (uint32_t m = 0; m < c.count_modes; m++)
			if (modes[m].type & DRM_MODE_TYPE_PREFERRED) {
				mode = modes[m];
				break;
			}
		D.conn_id = conns[i];
		enc_id = c.encoder_id;
		found = 1;
	}
	if (!found)
		goto fail;
	D.crtc_id = crtcs[0];
	if (enc_id) {
		struct drm_mode_get_encoder e = { .encoder_id = enc_id };

		if (drm_ioctl(fd, DRM_IOCTL_MODE_GETENCODER, &e) == 0 && e.crtc_id)
			D.crtc_id = e.crtc_id;
	}
	D.saved_crtc.crtc_id = D.crtc_id;
	D.have_saved = drm_ioctl(fd, DRM_IOCTL_MODE_GETCRTC, &D.saved_crtc) == 0;

	D.w = mode.hdisplay;
	D.h = mode.vdisplay;
	{
		struct drm_mode_create_dumb cd = { .width = (uint32_t)D.w, .height = (uint32_t)D.h, .bpp = 32 };
		struct drm_mode_fb_cmd fb = { 0 };
		struct drm_mode_map_dumb md = { 0 };
		struct drm_mode_crtc set = { 0 };

		if (drm_ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &cd) < 0)
			goto fail;
		D.handle = cd.handle;
		D.pitch = cd.pitch;
		D.size = cd.size;
		fb.width = (uint32_t)D.w;
		fb.height = (uint32_t)D.h;
		fb.pitch = cd.pitch;
		fb.bpp = 32;
		fb.depth = 24;
		fb.handle = cd.handle;
		if (drm_ioctl(fd, DRM_IOCTL_MODE_ADDFB, &fb) < 0)
			goto fail;
		D.fb_id = fb.fb_id;
		md.handle = cd.handle;
		if (drm_ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &md) < 0)
			goto fail;
		D.map = mmap(NULL, (size_t)cd.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, (off_t)md.offset);
		if (D.map == MAP_FAILED) {
			D.map = NULL;
			goto fail;
		}
		memset(D.map, 0, (size_t)cd.size);
		set.crtc_id = D.crtc_id;
		set.fb_id = D.fb_id;
		set.set_connectors_ptr = (uintptr_t)&D.conn_id;
		set.count_connectors = 1;
		set.mode = mode;
		set.mode_valid = 1;
		if (drm_ioctl(fd, DRM_IOCTL_MODE_SETCRTC, &set) < 0) {
			fprintf(stderr, "touchdemo: SETCRTC: %s\n", strerror(errno));
			goto fail;
		}
	}
	D.drm_fd = fd;
	D.kind = "drm";
	return 0;
fail:
	if (D.map)
		munmap(D.map, (size_t)D.size);
	D.map = NULL;
	if (D.fb_id)
		ioctl(fd, DRM_IOCTL_MODE_RMFB, &D.fb_id);
	if (D.handle) {
		struct drm_mode_destroy_dumb dd = { .handle = D.handle };
		ioctl(fd, DRM_IOCTL_MODE_DESTROY_DUMB, &dd);
	}
	D.fb_id = D.handle = 0;
	close(fd);
	return -1;
}

static void drm_close(void)
{
	struct drm_mode_destroy_dumb dd = { .handle = D.handle };

	if (D.have_saved && D.saved_crtc.mode_valid && D.saved_crtc.fb_id) {
		D.saved_crtc.set_connectors_ptr = (uintptr_t)&D.conn_id;
		D.saved_crtc.count_connectors = 1;
		ioctl(D.drm_fd, DRM_IOCTL_MODE_SETCRTC, &D.saved_crtc);
	}
	munmap(D.map, (size_t)D.size);
	ioctl(D.drm_fd, DRM_IOCTL_MODE_RMFB, &D.fb_id);
	ioctl(D.drm_fd, DRM_IOCTL_MODE_DESTROY_DUMB, &dd);
	ioctl(D.drm_fd, DRM_IOCTL_DROP_MASTER, 0);
	close(D.drm_fd);
}

static int fb_open(void)
{
	int fd = open(opt.fb_path, O_RDWR | O_CLOEXEC);

	if (fd < 0)
		return -1;
	if (ioctl(fd, FBIOGET_VSCREENINFO, &D.var) < 0 || ioctl(fd, FBIOGET_FSCREENINFO, &D.fix) < 0 ||
	    (D.var.bits_per_pixel != 32 && D.var.bits_per_pixel != 16)) {
		close(fd);
		return -1;
	}
	D.fblen = D.fix.smem_len;
	D.fbmem = mmap(NULL, D.fblen, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (D.fbmem == MAP_FAILED) {
		close(fd);
		return -1;
	}
	D.w = (int)D.var.xres;
	D.h = (int)D.var.yres;
	D.fb_fd = fd;
	D.kind = "fbdev";
	return 0;
}

static inline uint32_t chan(uint32_t c8, const struct fb_bitfield *f)
{
	uint32_t max = f->length >= 32 ? 0xffffffffu : (1u << f->length) - 1;

	return (c8 * max / 255) << f->offset;
}

/* XRGB8888 to the fbdev's own layout (16 bpp, 30 bpp, any channel order). */
static inline uint32_t pack(uint32_t c, const struct fb_var_screeninfo *v)
{
	return chan((c >> 16) & 0xff, &v->red) | chan((c >> 8) & 0xff, &v->green) | chan(c & 0xff, &v->blue);
}

static void present(void)
{
	struct drm_clip_rect clips[MAX_DIRTY];
	struct rect all = { 0, 0, D.w, D.h };
	int i, n = full_dirty ? 1 : ndirty;

	if (!n)
		return;
	for (i = 0; i < n; i++) {
		struct rect r = full_dirty ? all : dirty[i];
		int y, x, w = r.x1 - r.x0;

		if (D.map) {
			for (y = r.y0; y < r.y1; y++)
				memcpy(D.map + (size_t)y * D.pitch + (size_t)r.x0 * 4,
				       D.back + (size_t)y * D.w + r.x0, (size_t)w * 4);
			clips[i] = (struct drm_clip_rect){ (unsigned short)r.x0, (unsigned short)r.y0,
							   (unsigned short)r.x1, (unsigned short)r.y1 };
		} else if (D.fbmem) {
			const struct fb_var_screeninfo *v = &D.var;
			int native = v->bits_per_pixel == 32 && v->red.offset == 16 && v->green.offset == 8 &&
				     v->blue.offset == 0 && v->red.length == 8;

			for (y = r.y0; y < r.y1; y++) {
				uint8_t *dst = D.fbmem + (size_t)(y + (int)v->yoffset) * D.fix.line_length;
				const uint32_t *src = D.back + (size_t)y * D.w;

				if (native) {
					memcpy(dst + (size_t)r.x0 * 4, src + r.x0, (size_t)w * 4);
				} else if (v->bits_per_pixel == 32) {
					for (x = r.x0; x < r.x1; x++)
						((uint32_t *)dst)[x] = pack(src[x], v);
				} else {
					for (x = r.x0; x < r.x1; x++)
						((uint16_t *)dst)[x] = (uint16_t)pack(src[x], v);
				}
			}
		}
	}
	if (D.map) {
		struct drm_mode_fb_dirty_cmd dc = {
			.fb_id = D.fb_id, .num_clips = (uint32_t)n, .clips_ptr = (uintptr_t)clips,
		};
		ioctl(D.drm_fd, DRM_IOCTL_MODE_DIRTYFB, &dc);
	}
}

static int write_shot(const char *path)
{
	FILE *f = fopen(path, "wb");
	size_t i, n = (size_t)D.w * D.h;
	unsigned char *row;

	if (!f)
		return -1;
	fprintf(f, "P6\n%d %d\n255\n", D.w, D.h);
	row = malloc((size_t)D.w * 3);
	for (i = 0; i < n; i++) {
		uint32_t c = D.back[i];
		size_t k = (i % (size_t)D.w) * 3;

		row[k] = (unsigned char)(c >> 16);
		row[k + 1] = (unsigned char)(c >> 8);
		row[k + 2] = (unsigned char)c;
		if (k + 3 == (size_t)D.w * 3)
			fwrite(row, 1, (size_t)D.w * 3, f);
	}
	free(row);
	return fclose(f);
}

/* ---- console --------------------------------------------------------------- */

static void console_graphics(void)
{
	tty_fd = open("/dev/tty0", O_RDWR | O_CLOEXEC);
	if (tty_fd < 0)
		return;
	if (!F.data && !opt.font_path)
		font_from_console(tty_fd);
	if (opt.keep_console)
		return;
	if (ioctl(tty_fd, KDGETMODE, &saved_kd_mode) < 0)
		saved_kd_mode = -1;
	ioctl(tty_fd, KDSETMODE, KD_GRAPHICS);
}

static void console_restore(void)
{
	if (tty_fd < 0)
		return;
	if (saved_kd_mode >= 0)
		ioctl(tty_fd, KDSETMODE, saved_kd_mode);
	close(tty_fd);
	tty_fd = -1;
}

/* ---- input ------------------------------------------------------------------ */

static const char *abs_name(int code)
{
	int i;

	for (i = 0; i < AX_COUNT; i++)
		if (axis_codes[i] == code)
			return axis_names[i];
	if (code == ABS_MT_TRACKING_ID) return "TRACKING_ID";
	if (code == ABS_X) return "ABS_X";
	if (code == ABS_Y) return "ABS_Y";
	return NULL;
}

static void read_axes(void)
{
	int i;

	for (i = 0; i < AX_COUNT; i++) {
		struct input_absinfo ai;

		if (touch_fd < 0 || ioctl(touch_fd, EVIOCGABS(axis_codes[i]), &ai) < 0) {
			if (touch_fd >= 0)
				ax[i].present = 0;
			continue;
		}
		ax[i].present = 1;
		ax[i].min = ai.minimum;
		ax[i].max = ai.maximum;
		ax[i].res = ai.resolution;
		ax[i].fuzz = ai.fuzz;
		ax[i].value = ai.value;
	}
	if (ax[AX_SLOT].present && ax[AX_SLOT].max >= 0)
		nslots = ax[AX_SLOT].max + 1 > MAX_SLOTS ? MAX_SLOTS : ax[AX_SLOT].max + 1;
}

static int is_touchscreen(int fd)
{
	unsigned long absbits[BIT_WORDS(ABS_CNT)] = { 0 };

	if (ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(absbits)), absbits) < 0)
		return 0;
	return TEST_BIT(ABS_MT_POSITION_X, absbits) && TEST_BIT(ABS_MT_SLOT, absbits);
}

static int has_home_key(int fd)
{
	unsigned long keybits[BIT_WORDS(KEY_CNT)] = { 0 };

	if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keybits)), keybits) < 0)
		return 0;
	return TEST_BIT(KEY_HOMEPAGE, keybits);
}

static void find_devices(void)
{
	DIR *d = opendir("/dev/input");
	struct dirent *e;

	if (opt.device) {
		touch_fd = open(opt.device, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
		snprintf(dev_path, sizeof(dev_path), "%s", opt.device);
	}
	if (!d)
		goto done;
	while ((e = readdir(d))) {
		char p[300];
		int fd;

		if (strncmp(e->d_name, "event", 5))
			continue;
		snprintf(p, sizeof(p), "/dev/input/%s", e->d_name);
		fd = open(p, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
		if (fd < 0)
			continue;
		if (touch_fd < 0 && is_touchscreen(fd)) {
			touch_fd = fd;
			snprintf(dev_path, sizeof(dev_path), "%s", p);
		} else if (keys_fd < 0 && has_home_key(fd)) {
			keys_fd = fd;
		} else {
			close(fd);
		}
	}
	closedir(d);
done:
	if (touch_fd >= 0) {
		int clk = CLOCK_MONOTONIC;

		ioctl(touch_fd, EVIOCGNAME(sizeof(dev_name) - 1), dev_name);
		ioctl(touch_fd, EVIOCSCLOCKID, &clk);
		read_axes();
		cur_slot = ax[AX_SLOT].value;
	}
}

/* Pull the current slot state after open or SYN_DROPPED. */
static void sync_slots(void)
{
	static const int codes[] = { ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TOUCH_MAJOR,
				     ABS_MT_TOUCH_MINOR };
	struct { uint32_t code; int32_t v[MAX_SLOTS]; } req;
	size_t k;
	int s;

	if (touch_fd < 0)
		return;
	for (k = 0; k < sizeof(codes) / sizeof(codes[0]); k++) {
		req.code = (uint32_t)codes[k];
		if (ioctl(touch_fd, EVIOCGMTSLOTS(sizeof(req)), &req) < 0)
			return;
		for (s = 0; s < nslots; s++) {
			switch (codes[k]) {
			case ABS_MT_TRACKING_ID: cur[s].id = req.v[s]; break;
			case ABS_MT_POSITION_X: cur[s].x = req.v[s]; break;
			case ABS_MT_POSITION_Y: cur[s].y = req.v[s]; break;
			case ABS_MT_TOUCH_MAJOR: cur[s].major = req.v[s]; break;
			case ABS_MT_TOUCH_MINOR: cur[s].minor = req.v[s]; break;
			}
		}
	}
}

static void evlog_add(const struct input_event *ev)
{
	char *l = evlog[evlog_head];
	double t = (double)ev->input_event_sec + ev->input_event_usec / 1e6;
	const char *n;

	if (ev->type == EV_SYN)
		snprintf(l, 96, "%12.6f  SYN %s", t, ev->code == SYN_REPORT ? "REPORT ------" :
			 ev->code == SYN_DROPPED ? "DROPPED !!!" : "other");
	else if (ev->type == EV_ABS && (n = abs_name(ev->code)))
		snprintf(l, 96, "%12.6f  ABS %-12s %d", t, n, ev->value);
	else if (ev->type == EV_KEY)
		snprintf(l, 96, "%12.6f  KEY %-12d %d", t, ev->code, ev->value);
	else
		snprintf(l, 96, "%12.6f  type %d code %d value %d", t, ev->type, ev->code, ev->value);
	evlog_head = (evlog_head + 1) % EVLOG_LINES;
	if (evlog_n < EVLOG_LINES)
		evlog_n++;
}

/* ---- geometry ----------------------------------------------------------------- */

static int axis_ok(int a) { return ax[a].present && ax[a].max > ax[a].min; }

/* With a zero axis range the mapping uses the range seen so far, which is meaningless until it spans some distance:
 * until then a touch must not press a button (the first one always lands mid-screen). */
static int range_known(void)
{
	return (axis_ok(AX_X) || raw_max_x - raw_min_x >= 256) && (axis_ok(AX_Y) || raw_max_y - raw_min_y >= 256);
}

static int map_axis(int v, int a, int lo, int hi, int size)
{
	int min = axis_ok(a) ? ax[a].min : lo, max = axis_ok(a) ? ax[a].max : hi;

	if (max <= min)
		return size / 2;
	v = v < min ? min : v > max ? max : v;
	return (int)((int64_t)(v - min) * (size - 1) / (max - min));
}

static void to_screen(const struct slotval *v, int *sx, int *sy)
{
	int x = map_axis(v->x, AX_X, raw_min_x, raw_max_x, D.w);
	int y = map_axis(v->y, AX_Y, raw_min_y, raw_max_y, D.h);

	if (opt.swap_xy) {
		x = map_axis(v->y, AX_Y, raw_min_y, raw_max_y, D.w);
		y = map_axis(v->x, AX_X, raw_min_x, raw_max_x, D.h);
	}
	if (opt.flip_x)
		x = D.w - 1 - x;
	if (opt.flip_y)
		y = D.h - 1 - y;
	*sx = x;
	*sy = y;
}

/* Marker radius in pixels: TOUCH_MAJOR is a diameter; apple_z2 sets the X
 * resolution in px/mm from a surface in 0.01 mm, so major * res / 100 px. */
static int marker_radius(const struct slotval *v)
{
	double d;

	if (opt.size_scale > 0)
		d = v->major * opt.size_scale;
	else if (ax[AX_X].res > 0)
		d = (double)v->major * ax[AX_X].res / 100.0;
	else
		d = 80;
	d /= 2;
	return d < 12 ? 12 : d > 220 ? 220 : (int)d;
}

#define HUD_H (line_h(1) * 7 + 24)
#define BAR_H 128

/* GRID keeps its panel in the middle, one cell in from the sides, so every outer cell stays touchable. */
static void grid_panel(struct rect *hud, struct rect *bar)
{
	int y0 = D.h / 2 - (HUD_H + BAR_H) / 2;

	*hud = (struct rect){ CELL + 8, y0, D.w - CELL - 8, y0 + HUD_H };
	*bar = (struct rect){ CELL + 8, y0 + HUD_H, D.w - CELL - 8, y0 + HUD_H + BAR_H };
}

static void layout(void)
{
	int hud_h = HUD_H, bar_h = BAR_H;

	if (opt.mode == MODE_GRID) {
		grid_panel(&hud_r, &bar_r);
	} else {
		hud_r = (struct rect){ 0, 0, D.w, (hud_visible || opt.mode == MODE_EVENTS) ? hud_h : 0 };
		bar_r = (struct rect){ 0, D.h - bar_h, D.w, D.h };
	}
}

static int button_at(int x, int y)
{
	int bw = (bar_r.x1 - bar_r.x0) / NBUTTONS;

	if (!in_rect(bar_r, x, y) || bw <= 0)
		return -1;
	x = (x - bar_r.x0) / bw;
	return x < NBUTTONS ? x : NBUTTONS - 1;
}

/* ---- GRID ------------------------------------------------------------------------ */

static int cell_excluded(int c)
{
	struct rect r = { (c % gcols) * CELL, (c / gcols) * CELL, (c % gcols + 1) * CELL, (c / gcols + 1) * CELL };
	struct rect h, b, p;

	grid_panel(&h, &b);
	p = rect_union(h, b);
	return r.x0 >= p.x0 && r.x1 <= p.x1 && r.y0 >= p.y0 && r.y1 <= p.y1;
}

static int cell_is_edge(int c)
{
	int x = c % gcols, y = c / gcols;

	return x == 0 || y == 0 || x == gcols - 1 || y == grows - 1;
}

static int level_of(unsigned int hits)
{
	int l = 0;

	while (hits && l < 6) {
		l++;
		hits >>= 2;
	}
	return l;
}

static void draw_cell(int c)
{
	static const uint32_t heat[7] = { 0x000000, 0x103060, 0x105080, 0x107060, 0x40a030, 0xa0b020, 0xe0c020 };
	struct rect r = { (c % gcols) * CELL, (c / gcols) * CELL, (c % gcols + 1) * CELL, (c / gcols + 1) * CELL };

	fill(D.canvas, r, heat[cell_level[c]]);
	frame_rect(D.canvas, r, 1, 0x303030);
	if (cell_is_edge(c) && !cell_hits[c])
		frame_rect(D.canvas, (struct rect){ r.x0 + 4, r.y0 + 4, r.x1 - 4, r.y1 - 4 }, 3, 0xa05010);
	mark(r);
}

static void draw_target(int i)
{
	struct target *t = &targets[i];
	uint32_t c = t->done ? C_OK : 0xffffff;

	ring(D.canvas, t->x, t->y, 60, 4, c);
	ring(D.canvas, t->x, t->y, 20, 3, c);
	hline(D.canvas, t->x - 80, t->x + 81, t->y, 3, c);
	vline(D.canvas, t->x, t->y - 80, t->y + 81, 3, c);
	if (t->done) {
		int lx = t->x < D.w / 2 ? t->x + 70 : t->x - 70 - text_w("dx +000 dy +000", 1);
		int ly = t->y < D.h / 2 ? t->y + 70 : t->y - 70 - 2 * line_h(1);

		textf(D.canvas, lx, ly, C_OK, "dx %+4.0f dy %+4.0f", t->dx, t->dy);
		textf(D.canvas, lx, ly + line_h(1), C_DIM, "%ld samples", t->samples);
		/* where the touches actually landed */
		disk(D.canvas, t->x + (int)lround(t->dx), t->y + (int)lround(t->dy), 8, C_WARN);
	}
	mark((struct rect){ 0, t->y - 400, D.w, t->y + 400 });
}

static void grid_setup(void)
{
	int in = 96, i;
	static const char *names[NTARGETS] = { "top-left", "top", "top-right", "right",
					       "bottom-right", "bottom", "bottom-left", "left" };
	int pos[NTARGETS][2] = {
		{ in, in }, { D.w / 2, in }, { D.w - in, in }, { D.w - in, D.h / 2 },
		{ D.w - in, D.h - in }, { D.w / 2, D.h - in }, { in, D.h - in }, { in, D.h / 2 },
	};

	gcols = D.w / CELL;
	grows = D.h / CELL;
	if (gcols * grows > MAX_CELLS)
		grows = MAX_CELLS / gcols;
	for (i = 0; i < NTARGETS; i++) {
		targets[i].x = pos[i][0];
		targets[i].y = pos[i][1];
		targets[i].name = names[i];
	}
}

static void grid_reset(void)
{
	memset(cell_hits, 0, sizeof(cell_hits));
	memset(cell_level, 0, sizeof(cell_level));
	for (int i = 0; i < NTARGETS; i++) {
		targets[i].done = 0;
		targets[i].samples = 0;
	}
}

static void grid_counts(int *hit, int *total, int *ehit, int *etotal, int *tdone)
{
	int c;

	*hit = *total = *ehit = *etotal = *tdone = 0;
	for (c = 0; c < gcols * grows; c++) {
		if (cell_excluded(c))
			continue;
		(*total)++;
		*hit += cell_hits[c] > 0;
		if (cell_is_edge(c)) {
			(*etotal)++;
			*ehit += cell_hits[c] > 0;
		}
	}
	for (c = 0; c < NTARGETS; c++)
		*tdone += targets[c].done;
}

/* ---- canvas ------------------------------------------------------------------------ */

static void canvas_reset(void)
{
	int x, y, c;

	fill(D.canvas, (struct rect){ 0, 0, D.w, D.h }, C_BG);
	if (opt.mode == MODE_PAINT) {
		for (x = CELL; x < D.w; x += CELL)
			vline(D.canvas, x, 0, D.h, 1, C_GRIDLN);
		for (y = CELL; y < D.h; y += CELL)
			hline(D.canvas, 0, D.w, y, 1, C_GRIDLN);
	} else if (opt.mode == MODE_GRID) {
		for (c = 0; c < gcols * grows; c++)
			draw_cell(c);
		for (c = 0; c < NTARGETS; c++)
			draw_target(c);
	}
	mark_full();
}

/* ---- contacts ---------------------------------------------------------------------- */

static struct rect marker_rect(const struct contact *c)
{
	int r = marker_radius(&c->v) + 24;

	return (struct rect){ c->sx - r - 40, c->sy - r - 40, c->sx + r + 40 + text_w("ID 00000", 1),
			      c->sy + r + 40 + line_h(1) };
}

static void draw_marker(const struct contact *c)
{
	uint32_t col = palette[(unsigned)c->id % 12];
	int r = marker_radius(&c->v);

	if (ax[AX_MINOR].present && c->v.minor > 0 && c->v.major > 0) {
		double b = r * (double)c->v.minor / c->v.major;
		double ang = ax[AX_ORIENT].present ? c->v.orient * (M_PI / 2) / 32768.0 : 0;

		ellipse(D.back, c->sx, c->sy, r, b < 6 ? 6 : b, ang, 2, col);
	} else {
		ring(D.back, c->sx, c->sy, r, 5, col);
	}
	hline(D.back, c->sx - r - 30, c->sx + r + 31, c->sy, 2, col);
	vline(D.back, c->sx, c->sy - r - 30, c->sy + r + 31, 2, col);
	fill(D.back, (struct rect){ c->sx + r + 12, c->sy - r - 12 - line_h(1),
				    c->sx + r + 20 + text_w("ID 00000", 1), c->sy - r - 8 }, 0x000000);
	textf(D.back, c->sx + r + 16, c->sy - r - 10 - line_h(1), col, "ID %d", c->id);
}

static void do_button(int b)
{
	switch (b) {
	case BTN_PAINT: case BTN_GRID: case BTN_EVENTS:
		opt.mode = (enum mode)b;
		layout();
		canvas_reset();
		break;
	case BTN_CLEAR:
		if (opt.mode == MODE_GRID)
			grid_reset();
		evlog_n = 0;
		canvas_reset();
		break;
	case BTN_HUD:
		hud_visible = !hud_visible;
		layout();
		canvas_reset();
		break;
	}
}

static void contact_down(struct contact *c)
{
	int i;

	c->owner = OWN_DRAW;
	c->target = -1;
	c->has_prev = 0;
	c->sum_x = c->sum_y = 0;
	c->samples = 0;
	c->cell = -1;
	c->down_ns = now_ns();
	contacts_seen++;
	if (!range_known()) {
		c->owner = OWN_HUD;
		return;
	}
	if (in_rect(bar_r, c->sx, c->sy)) {
		c->owner = OWN_BAR;
		c->button = button_at(c->sx, c->sy);
		return;
	}
	if (in_rect(hud_r, c->sx, c->sy) && opt.mode != MODE_PAINT) {
		c->owner = OWN_HUD;
		return;
	}
	if (opt.mode == MODE_GRID) {
		int best = -1, bd = 200 * 200;

		for (i = 0; i < NTARGETS; i++) {
			int dx = c->sx - targets[i].x, dy = c->sy - targets[i].y;

			if (dx * dx + dy * dy < bd) {
				bd = dx * dx + dy * dy;
				best = i;
			}
		}
		c->target = best;
	}
}

static void contact_move(struct contact *c)
{
	int r;

	if (c->owner != OWN_DRAW)
		return;
	if (opt.mode == MODE_PAINT) {
		r = marker_radius(&c->v) / 6;
		r = r < 4 ? 4 : r > 14 ? 14 : r;
		if (c->has_prev)
			thick_line(D.canvas, c->psx, c->psy, c->sx, c->sy, r, palette[(unsigned)c->id % 12]);
		else
			disk(D.canvas, c->sx, c->sy, r, palette[(unsigned)c->id % 12]);
		mark((struct rect){ (c->psx < c->sx ? c->psx : c->sx) - r - 1, (c->psy < c->sy ? c->psy : c->sy) - r - 1,
				    (c->psx > c->sx ? c->psx : c->sx) + r + 2, (c->psy > c->sy ? c->psy : c->sy) + r + 2 });
		if (!c->has_prev)
			mark((struct rect){ c->sx - r - 1, c->sy - r - 1, c->sx + r + 2, c->sy + r + 2 });
	} else if (opt.mode == MODE_GRID && gcols) {
		int cx = c->sx / CELL, cy = c->sy / CELL, cell = cy * gcols + cx;

		if (cx < gcols && cy < grows && !cell_excluded(cell)) {
			int lvl;

			cell_hits[cell]++;
			lvl = level_of(cell_hits[cell]);
			if (lvl != cell_level[cell]) {
				cell_level[cell] = (unsigned char)lvl;
				draw_cell(cell);
				for (int t = 0; t < NTARGETS; t++)
					if (abs(targets[t].x / CELL - cx) <= 1 && abs(targets[t].y / CELL - cy) <= 1)
						draw_target(t);
			}
		}
		if (c->target >= 0) {
			c->sum_x += c->sx;
			c->sum_y += c->sy;
			c->samples++;
		}
	}
	c->psx = c->sx;
	c->psy = c->sy;
	c->has_prev = 1;
}

static void contact_up(struct contact *c)
{
	if (c->owner == OWN_BAR) {
		if (c->button >= 0 && button_at(c->sx, c->sy) == c->button)
			do_button(c->button);
	} else if (opt.mode == MODE_GRID && c->target >= 0 && c->samples > 0) {
		struct target *t = &targets[c->target];

		t->dx = c->sum_x / c->samples - t->x;
		t->dy = c->sum_y / c->samples - t->y;
		t->samples = c->samples;
		t->done = 1;
		canvas_reset();
	}
}

static void text_contact(const char *what, int s, const struct contact *c)
{
	double t = (now_ns() - t_start) / 1e9;

	printf("%9.3f %-4s slot %3d id %5d x %5d y %5d major %5d minor %5d orient %6d screen %4d,%4d\n", t, what, s,
	       c->id, c->v.x, c->v.y, c->v.major, c->v.minor, c->v.orient, c->sx, c->sy);
}

/* SYN_REPORT: commit the slots into contacts. */
static void commit(uint64_t ev_ns)
{
	uint64_t n = now_ns();
	int s, live = 0;

	total_reports++;
	rate_count++;
	if (ev_ns && n >= ev_ns && n - ev_ns < 1000000000ull) {
		lat_sum += (n - ev_ns) / 1e6;
		lat_n++;
	}
	for (s = 0; s < nslots; s++) {
		struct slotval *v = &cur[s];
		struct contact *c = &con[s];
		int was = c->active, is = v->id >= 0;

		if (is) {
			if (!raw_seen) {
				raw_min_x = raw_max_x = v->x;
				raw_min_y = raw_max_y = v->y;
				raw_seen = 1;
			}
			if (v->x < raw_min_x) raw_min_x = v->x;
			if (v->x > raw_max_x) raw_max_x = v->x;
			if (v->y < raw_min_y) raw_min_y = v->y;
			if (v->y > raw_max_y) raw_max_y = v->y;
			if (v->major > major_max_seen) major_max_seen = v->major;
			live++;
		}
		if (!is && !was)
			continue;
		if (is) {
			int changed = !was || memcmp(&c->v, v, sizeof(*v));

			c->v = *v;
			c->id = v->id;
			to_screen(v, &c->sx, &c->sy);
			if (!was) {
				c->active = 1;
				contact_down(c);
			}
			if (changed) {
				contact_move(c);
				if (opt.text)
					text_contact(was ? "move" : "down", s, c);
			}
		} else {
			c->active = 0;
			contact_up(c);
			if (opt.text)
				text_contact("up", s, c);
		}
	}
	if (live > max_simul)
		max_simul = live;
}

static void handle_event(const struct input_event *ev)
{
	total_events++;
	if (opt.mode == MODE_EVENTS)
		evlog_add(ev);
	if (ev->type == EV_SYN && ev->code == SYN_DROPPED) {
		dropped = 1;
		return;
	}
	if (ev->type == EV_SYN && ev->code == SYN_REPORT) {
		if (dropped) {
			sync_slots();
			dropped = 0;
		}
		commit((uint64_t)ev->input_event_sec * 1000000000ull + (uint64_t)ev->input_event_usec * 1000ull);
		return;
	}
	if (dropped || ev->type != EV_ABS)
		return;
	if (ev->code == ABS_MT_SLOT) {
		cur_slot = ev->value >= 0 && ev->value < nslots ? ev->value : 0;
		return;
	}
	switch (ev->code) {
	case ABS_MT_TRACKING_ID: cur[cur_slot].id = ev->value; break;
	case ABS_MT_POSITION_X: cur[cur_slot].x = ev->value; break;
	case ABS_MT_POSITION_Y: cur[cur_slot].y = ev->value; break;
	case ABS_MT_TOUCH_MAJOR: cur[cur_slot].major = ev->value; break;
	case ABS_MT_TOUCH_MINOR: cur[cur_slot].minor = ev->value; break;
	case ABS_MT_WIDTH_MAJOR: cur[cur_slot].wmajor = ev->value; break;
	case ABS_MT_WIDTH_MINOR: cur[cur_slot].wminor = ev->value; break;
	case ABS_MT_ORIENTATION: cur[cur_slot].orient = ev->value; break;
	case ABS_MT_PRESSURE: cur[cur_slot].pressure = ev->value; break;
	}
}

static void handle_key(const struct input_event *ev)
{
	if (ev->type == EV_KEY && ev->code == KEY_HOMEPAGE && ev->value == 1)
		do_button((opt.mode + 1) % MODE_COUNT);
}

/* ---- panels ------------------------------------------------------------------------- */

static void axis_desc(char *s, size_t n, int a)
{
	if (!ax[a].present)
		snprintf(s, n, "n/a");
	else if (ax[a].max <= ax[a].min)
		snprintf(s, n, "%d..%d ZERO RANGE", ax[a].min, ax[a].max);
	else
		snprintf(s, n, "%d..%d r%d", ax[a].min, ax[a].max, ax[a].res);
}

static void draw_hud(void)
{
	int lh = line_h(1), x = hud_r.x0 + 12, y = hud_r.y0 + 12, s, shown = 0;
	char xa[48], ya[48];

	if (rect_empty(hud_r))
		return;
	fill(D.back, hud_r, C_PANEL);
	frame_rect(D.back, hud_r, 2, 0x304860);
	textf(D.back, x, y, 0xffffff, "touchdemo %s  %s  %s  %d reports/s  latency %.1f ms",
	      mode_names[opt.mode], D.kind, touch_fd >= 0 || opt.replay ? dev_name : "NO TOUCHSCREEN", rate_hz, lat_ms);
	y += lh;
	axis_desc(xa, sizeof(xa), AX_X);
	axis_desc(ya, sizeof(ya), AX_Y);
	textf(D.back, x, y, (axis_ok(AX_X) && axis_ok(AX_Y)) ? C_TEXT : C_WARN, "X %s  Y %s  slots %d%s", xa, ya,
	      nslots, (axis_ok(AX_X) && axis_ok(AX_Y)) ? "" : " (using seen range)");
	y += lh;
	if (raw_seen)
		textf(D.back, x, y, C_DIM, "seen x %d..%d y %d..%d  major max %d  max fingers %d  pressure %s",
		      raw_min_x, raw_max_x, raw_min_y, raw_max_y, major_max_seen, max_simul,
		      ax[AX_PRESSURE].present ? "yes" : "n/a");
	else
		textf(D.back, x, y, C_DIM, "%s", touch_fd >= 0 || opt.replay ? "touch the screen" : "waiting for touchscreen");
	y += lh;
	if (opt.mode == MODE_GRID) {
		int hit, total, ehit, etotal, tdone;

		grid_counts(&hit, &total, &ehit, &etotal, &tdone);
		textf(D.back, x, y, C_OK, "cells %d/%d  edge %d/%d  targets %d/%d", hit, total, ehit, etotal, tdone, NTARGETS);
		y += lh;
	}
	for (s = 0; s < nslots && y + lh <= hud_r.y1 - 8; s++) {
		const struct contact *c = &con[s];

		if (!c->active)
			continue;
		textf(D.back, x, y, palette[(unsigned)c->id % 12],
		      "s%-2d id %-5d x %5d y %5d  maj %5d min %5d  w %d/%d  ori %6d", s, c->id, c->v.x, c->v.y,
		      c->v.major, c->v.minor, c->v.wmajor, c->v.wminor, c->v.orient);
		y += lh;
		shown++;
	}
	if (!shown && opt.mode != MODE_GRID)
		textf(D.back, x, y, C_DIM, "Home button or the buttons below switch screens; SIGUSR1 saves a screenshot");
	mark(hud_r);
}

static void draw_bar(void)
{
	int bw = (bar_r.x1 - bar_r.x0) / NBUTTONS, i;

	fill(D.back, bar_r, C_PANEL);
	for (i = 0; i < NBUTTONS; i++) {
		struct rect b = { bar_r.x0 + i * bw + 8, bar_r.y0 + 12, bar_r.x0 + (i + 1) * bw - 8, bar_r.y1 - 12 };
		int on = (i == (int)opt.mode) || (i == BTN_HUD && hud_visible && opt.mode == MODE_PAINT);

		fill(D.back, b, on ? C_BTN_ON : C_BTN);
		frame_rect(D.back, b, 2, 0x5080b0);
		draw_text(D.back, (b.x0 + b.x1 - text_w(button_names[i], 1)) / 2, (b.y0 + b.y1 - line_h(1)) / 2,
			  button_names[i], 0xffffff, 1);
	}
	mark(bar_r);
}

static void draw_events_screen(void)
{
	int lh = line_h(1), x = 16, y = hud_r.y1 + 8, s, i, a;

	fill(D.back, (struct rect){ 0, hud_r.y1, D.w, bar_r.y0 }, C_BG);
	textf(D.back, x, y, 0xffffff, "%s  %s  events %llu  reports %llu", dev_path[0] ? dev_path : "(replay)", dev_name,
	      (unsigned long long)total_events, (unsigned long long)total_reports);
	y += lh + 8;
	textf(D.back, x, y, C_DIM, "%-12s %8s %8s %5s %5s", "axis", "min", "max", "res", "fuzz");
	y += lh;
	for (a = 0; a < AX_COUNT; a++, y += lh) {
		if (!ax[a].present) {
			textf(D.back, x, y, C_DIM, "%-12s  not reported", axis_names[a]);
			continue;
		}
		textf(D.back, x, y, ax[a].max > ax[a].min ? C_TEXT : C_WARN, "%-12s %8d %8d %5d %5d%s", axis_names[a],
		      ax[a].min, ax[a].max, ax[a].res, ax[a].fuzz, ax[a].max > ax[a].min ? "" : "  zero range");
	}
	y += 8;
	for (s = 0; s < nslots; s++) {
		const struct contact *c = &con[s];

		if (!c->active)
			continue;
		textf(D.back, x, y, palette[(unsigned)c->id % 12],
		      "slot %-3d id %-5d x %5d y %5d maj %5d min %5d wmaj %5d ori %6d -> %d,%d", s, c->id, c->v.x,
		      c->v.y, c->v.major, c->v.minor, c->v.wmajor, c->v.orient, c->sx, c->sy);
		y += lh;
	}
	y += 8;
	textf(D.back, x, y, C_DIM, "latest events (newest at the bottom)");
	y += lh;
	{
		int room = (bar_r.y0 - 8 - y) / lh, n = evlog_n < room ? evlog_n : room;

		for (i = 0; i < n; i++) {
			int k = (evlog_head - n + i + EVLOG_LINES) % EVLOG_LINES;

			draw_text(D.back, x, y, evlog[k], strstr(evlog[k], "REPORT") ? C_DIM : C_TEXT, 1);
			y += lh;
		}
	}
	mark((struct rect){ 0, hud_r.y1, D.w, bar_r.y0 });
}

/* ---- frame ---------------------------------------------------------------------------- */

static void render(int hud_now)
{
	int s, i;

	for (s = 0; s < nslots; s++) {
		struct contact *c = &con[s];

		if (c->marker_drawn) {
			mark(c->marker);
			c->marker_drawn = 0;
		}
		if (c->active && c->owner == OWN_DRAW && opt.mode != MODE_EVENTS) {
			c->marker = marker_rect(c);
			mark(c->marker);
		}
	}
	if (opt.mode == MODE_EVENTS && hud_now)
		mark((struct rect){ 0, hud_r.y1, D.w, bar_r.y0 });
	if (full_dirty) {
		memcpy(D.back, D.canvas, (size_t)D.w * D.h * 4);
	} else {
		for (i = 0; i < ndirty; i++) {
			struct rect r = dirty[i];

			for (int y = r.y0; y < r.y1; y++)
				memcpy(D.back + (size_t)y * D.w + r.x0, D.canvas + (size_t)y * D.w + r.x0,
				       (size_t)(r.x1 - r.x0) * 4);
		}
	}
	if (opt.mode == MODE_EVENTS) {
		if (hud_now || full_dirty)
			draw_events_screen();
	} else {
		for (s = 0; s < nslots; s++) {
			struct contact *c = &con[s];

			if (c->active && c->owner == OWN_DRAW) {
				draw_marker(c);
				c->marker_drawn = 1;
			}
		}
	}
	/* Panels go on top of whatever touched them. */
	{
		int over_hud = full_dirty || hud_now, over_bar = full_dirty;

		for (i = 0; i < ndirty; i++) {
			over_hud |= rect_hit(dirty[i], hud_r);
			over_bar |= rect_hit(dirty[i], bar_r);
		}
		if (over_hud)
			draw_hud();
		if (over_bar)
			draw_bar();
	}
	present();
	ndirty = 0;
	full_dirty = 0;
}

static void shot(const char *path)
{
	char p[512];

	if (!path) {
		snprintf(p, sizeof(p), "%s/touchdemo-%d.ppm", opt.shot_dir, shot_seq++);
		path = p;
	}
	if (write_shot(path) == 0)
		fprintf(stderr, "touchdemo: screenshot %s\n", path);
	else
		fprintf(stderr, "touchdemo: screenshot %s: %s\n", path, strerror(errno));
}

static void summary(void)
{
	double secs = (now_ns() - t_start) / 1e9;
	int hit, total, ehit, etotal, tdone, i;

	printf("touchdemo summary: device \"%s\" %s, display %s %dx%d, %.1f s\n", dev_name, dev_path, D.kind, D.w, D.h,
	       secs);
	printf("reports %llu events %llu (%.1f reports/s), contacts %llu, max fingers %d, latency avg %.2f ms\n",
	       (unsigned long long)total_reports, (unsigned long long)total_events,
	       secs > 0 ? total_reports / secs : 0.0, (unsigned long long)contacts_seen, max_simul,
	       lat_n ? lat_sum / lat_n : 0.0);
	printf("axis x %d..%d y %d..%d major %d..%d%s\n", ax[AX_X].min, ax[AX_X].max, ax[AX_Y].min, ax[AX_Y].max,
	       ax[AX_MAJOR].min, ax[AX_MAJOR].max, axis_ok(AX_X) && axis_ok(AX_Y) ? "" : " (ZERO RANGE)");
	if (raw_seen)
		printf("seen x %d..%d y %d..%d major max %d\n", raw_min_x, raw_max_x, raw_min_y, raw_max_y, major_max_seen);
	grid_counts(&hit, &total, &ehit, &etotal, &tdone);
	printf("grid cells %d/%d edge %d/%d targets %d/%d\n", hit, total, ehit, etotal, tdone, NTARGETS);
	for (i = 0; i < NTARGETS; i++)
		if (targets[i].done)
			printf("target %-12s at %4d,%4d offset dx %+.1f dy %+.1f px (%ld samples)\n", targets[i].name,
			       targets[i].x, targets[i].y, targets[i].dx, targets[i].dy, targets[i].samples);
	fflush(stdout);
}

/* ---- replay (off-hardware test) --------------------------------------------------------- */

static void feed(int type, int code, int value)
{
	struct input_event ev = { .type = (unsigned short)type, .code = (unsigned short)code, .value = value };
	uint64_t n = now_ns();

	ev.input_event_sec = (long)(n / 1000000000ull);
	ev.input_event_usec = (long)(n % 1000000000ull / 1000);
	if (type == EV_KEY)
		handle_key(&ev);
	else
		handle_event(&ev);
}

static int replay(const char *path)
{
	FILE *f = fopen(path, "r");
	char line[256];
	int lineno = 0;

	if (!f) {
		perror(path);
		return -1;
	}
	while (fgets(line, sizeof(line), f)) {
		char cmd[32], arg[200];
		int a = 0, b = 0, c = 0, d = 0, e = 0, n;

		lineno++;
		n = sscanf(line, "%31s", cmd);
		if (n < 1 || cmd[0] == '#')
			continue;
		if (!strcmp(cmd, "down") && sscanf(line, "%*s %d %d %d %d %d", &a, &b, &c, &d, &e) >= 4) {
			feed(EV_ABS, ABS_MT_SLOT, a);
			feed(EV_ABS, ABS_MT_TRACKING_ID, b);
			feed(EV_ABS, ABS_MT_POSITION_X, c);
			feed(EV_ABS, ABS_MT_POSITION_Y, d);
			feed(EV_ABS, ABS_MT_TOUCH_MAJOR, e);
			feed(EV_ABS, ABS_MT_TOUCH_MINOR, e * 3 / 4);
		} else if (!strcmp(cmd, "move") && sscanf(line, "%*s %d %d %d", &a, &b, &c) == 3) {
			feed(EV_ABS, ABS_MT_SLOT, a);
			feed(EV_ABS, ABS_MT_POSITION_X, b);
			feed(EV_ABS, ABS_MT_POSITION_Y, c);
		} else if (!strcmp(cmd, "drag") && sscanf(line, "%*s %d %d %d %d %d", &a, &b, &c, &d, &e) == 5) {
			/* drag SLOT X1 Y1 STEPS: interpolate from the slot's position, a frame per step */
			int x0 = cur[a].x, y0 = cur[a].y;

			for (int i = 1; i <= e; i++) {
				feed(EV_ABS, ABS_MT_SLOT, a);
				feed(EV_ABS, ABS_MT_POSITION_X, x0 + (b - x0) * i / e);
				feed(EV_ABS, ABS_MT_POSITION_Y, y0 + (c - y0) * i / e);
				feed(EV_SYN, SYN_REPORT, 0);
				render(0);
			}
			(void)d;
		} else if (!strcmp(cmd, "up") && sscanf(line, "%*s %d", &a) == 1) {
			feed(EV_ABS, ABS_MT_SLOT, a);
			feed(EV_ABS, ABS_MT_TRACKING_ID, -1);
		} else if (!strcmp(cmd, "frame")) {
			feed(EV_SYN, SYN_REPORT, 0);
			render(1);
		} else if (!strcmp(cmd, "home")) {
			feed(EV_KEY, KEY_HOMEPAGE, 1);
			feed(EV_KEY, KEY_HOMEPAGE, 0);
			render(1);
		} else if (!strcmp(cmd, "shot") && sscanf(line, "%*s %199s", arg) == 1) {
			render(1);
			shot(arg);
		} else {
			fprintf(stderr, "%s:%d: bad line: %s", path, lineno, line);
			fclose(f);
			return -1;
		}
	}
	fclose(f);
	return 0;
}

/* ---- main ------------------------------------------------------------------------------- */

static void usage(void)
{
	fprintf(stderr,
		"usage: touchdemo [--mode paint|grid|events] [--device PATH] [--fb] [--drm PATH] [--text]\n"
		"                 [--no-display] [--duration SEC] [--wait SEC] [--swap-xy] [--flip-x] [--flip-y]\n"
		"                 [--size-scale F] [--keep-console] [--shot-dir DIR] [--font FILE.psf]\n"
		"       touchdemo --headless WxH --replay FILE [--zero-axes] [--font FILE.psf]\n");
	exit(2);
}

static void parse_args(int argc, char **argv)
{
	int i;

	for (i = 1; i < argc; i++) {
		const char *a = argv[i];
		const char *v = i + 1 < argc ? argv[i + 1] : NULL;

#define NEEDV do { if (!v) usage(); i++; } while (0)
		if (!strcmp(a, "--mode")) {
			NEEDV;
			if (!strcmp(v, "paint")) opt.mode = MODE_PAINT;
			else if (!strcmp(v, "grid")) opt.mode = MODE_GRID;
			else if (!strcmp(v, "events")) opt.mode = MODE_EVENTS;
			else usage();
		} else if (!strcmp(a, "--device")) { NEEDV; opt.device = v; }
		else if (!strcmp(a, "--drm")) { NEEDV; opt.drm_path = v; }
		else if (!strcmp(a, "--fbdev")) { NEEDV; opt.fb_path = v; opt.force_fb = 1; }
		else if (!strcmp(a, "--fb")) opt.force_fb = 1;
		else if (!strcmp(a, "--font")) { NEEDV; opt.font_path = v; }
		else if (!strcmp(a, "--replay")) { NEEDV; opt.replay = v; }
		else if (!strcmp(a, "--shot-dir")) { NEEDV; opt.shot_dir = v; }
		else if (!strcmp(a, "--duration")) { NEEDV; opt.duration = atof(v); }
		else if (!strcmp(a, "--wait")) { NEEDV; opt.wait = atof(v); }
		else if (!strcmp(a, "--size-scale")) { NEEDV; opt.size_scale = atof(v); }
		else if (!strcmp(a, "--fps")) { NEEDV; opt.fps = atoi(v) > 0 ? atoi(v) : 60; }
		else if (!strcmp(a, "--headless")) {
			NEEDV;
			if (sscanf(v, "%dx%d", &opt.headless_w, &opt.headless_h) != 2 || opt.headless_w < 256 ||
			    opt.headless_h < 256 || opt.headless_w > 8192 || opt.headless_h > 8192)
				usage();
		}
		else if (!strcmp(a, "--text")) opt.text = 1;
		else if (!strcmp(a, "--no-display")) opt.no_display = 1;
		else if (!strcmp(a, "--keep-console")) opt.keep_console = 1;
		else if (!strcmp(a, "--zero-axes")) opt.zero_axes = 1;
		else if (!strcmp(a, "--swap-xy")) opt.swap_xy = 1;
		else if (!strcmp(a, "--flip-x")) opt.flip_x = 1;
		else if (!strcmp(a, "--flip-y")) opt.flip_y = 1;
		else usage();
#undef NEEDV
	}
	if (opt.replay && !opt.headless_w)
		usage();
}

static int open_display(void)
{
	if (opt.headless_w || opt.no_display) {
		D.w = opt.headless_w ? opt.headless_w : 1536;
		D.h = opt.headless_h ? opt.headless_h : 2048;
		D.kind = opt.no_display ? "none" : "headless";
		return 0;
	}
	console_graphics();
	if (!opt.force_fb && drm_open() == 0)
		return 0;
	if (fb_open() == 0)
		return 0;
	console_restore();
	fprintf(stderr, "touchdemo: no usable display (%s or %s)\n", opt.drm_path, opt.fb_path);
	return -1;
}

static void close_display(void)
{
	if (D.map)
		drm_close();
	if (D.fbmem) {
		munmap(D.fbmem, D.fblen);
		close(D.fb_fd);
	}
	console_restore();
}

int main(int argc, char **argv)
{
	struct sigaction sa = { 0 };
	uint64_t last_frame = 0, last_hud = 0, last_axes = 0, wait_until;
	int s, rc = 0;

	parse_args(argc, argv);
	setvbuf(stdout, NULL, _IOLBF, 0);
	sa.sa_handler = on_signal;
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGTERM, &sa, NULL);
	sigaction(SIGHUP, &sa, NULL);
	sigaction(SIGUSR1, &sa, NULL);

	if (opt.font_path && font_from_psf(opt.font_path) < 0)
		fprintf(stderr, "touchdemo: cannot read font %s, no text\n", opt.font_path);
	for (s = 0; s < MAX_SLOTS; s++)
		cur[s].id = -1;
	if (open_display() < 0)
		return 1;
	D.back = calloc((size_t)D.w * D.h, 4);
	D.canvas = calloc((size_t)D.w * D.h, 4);
	if (!D.back || !D.canvas) {
		close_display();
		return 1;
	}
	t_start = rate_t0 = now_ns();
	grid_setup();
	layout();
	canvas_reset();

	if (opt.replay) {
		snprintf(dev_name, sizeof(dev_name), "replay %s", opt.replay);
		ax[AX_X] = (struct axis){ 1, 0, opt.zero_axes ? 0 : D.w - 1, 10, 0, 0 };
		ax[AX_Y] = (struct axis){ 1, 0, opt.zero_axes ? 0 : D.h - 1, 10, 0, 0 };
		ax[AX_MAJOR] = (struct axis){ 1, 0, 65535, 0, 0, 0 };
		ax[AX_MINOR] = (struct axis){ 1, 0, 65535, 0, 0, 0 };
		ax[AX_ORIENT] = (struct axis){ 1, -32768, 32767, 0, 0, 0 };
		ax[AX_SLOT] = (struct axis){ 1, 0, 15, 0, 0, 0 };
		nslots = 16;
		render(1);
		rc = replay(opt.replay) < 0;
		summary();
		return rc;
	}

	render(1);
	wait_until = now_ns() + (uint64_t)(opt.wait * 1e9);
	while (!quit) {
		struct pollfd pfd[2];
		int nfd = 0, timeout;
		uint64_t n = now_ns();

		if (touch_fd < 0) {
			find_devices();
			if (touch_fd >= 0) {
				sync_slots();
				fprintf(stderr, "touchdemo: %s \"%s\"\n", dev_path, dev_name);
				hud_due = 1;
			} else if (n > wait_until) {
				fprintf(stderr, "touchdemo: no multi-touch device in /dev/input after %.0f s\n", opt.wait);
				rc = 1;
				break;
			}
		}
		if (touch_fd >= 0)
			pfd[nfd++] = (struct pollfd){ .fd = touch_fd, .events = POLLIN };
		if (keys_fd >= 0)
			pfd[nfd++] = (struct pollfd){ .fd = keys_fd, .events = POLLIN };
		timeout = touch_fd < 0 ? 500 : (ndirty || full_dirty) ? 1000 / opt.fps : 100;
		if (poll(pfd, (nfds_t)nfd, timeout) < 0 && errno != EINTR)
			break;
		for (int k = 0; k < nfd; k++) {
			struct input_event evs[64];
			ssize_t r;

			if (!(pfd[k].revents & (POLLIN | POLLERR | POLLHUP)))
				continue;
			while ((r = read(pfd[k].fd, evs, sizeof(evs))) > 0) {
				for (size_t e = 0; e < (size_t)r / sizeof(evs[0]); e++) {
					if (pfd[k].fd == touch_fd)
						handle_event(&evs[e]);
					else
						handle_key(&evs[e]);
				}
			}
			if (r < 0 && errno == ENODEV && pfd[k].fd == touch_fd) {
				close(touch_fd);
				touch_fd = -1;
				wait_until = now_ns() + (uint64_t)(opt.wait * 1e9);
			}
		}
		n = now_ns();
		if (n - rate_t0 >= 1000000000ull) {
			rate_hz = (int)(rate_count * 1e9 / (n - rate_t0));
			rate_count = 0;
			rate_t0 = n;
			lat_ms = lat_n ? lat_sum / lat_n : 0;
		}
		if (n - last_axes >= 1000000000ull && touch_fd >= 0) {
			read_axes();
			last_axes = n;
		}
		if (n - last_hud >= 100000000ull) {
			hud_due = 1;
			last_hud = n;
		}
		if (!opt.no_display && n - last_frame >= 1000000000ull / (uint64_t)opt.fps) {
			render(hud_due);
			hud_due = 0;
			last_frame = n;
		} else if (opt.no_display) {
			ndirty = full_dirty = 0;
		}
		if (want_shot) {
			want_shot = 0;
			shot(NULL);
		}
		if (opt.duration > 0 && n - t_start >= (uint64_t)(opt.duration * 1e9))
			break;
	}
	close_display();
	summary();
	return rc;
}
