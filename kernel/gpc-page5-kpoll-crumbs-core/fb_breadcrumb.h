/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Best-effort visible progress marks on the iPad's simple framebuffer. TEST ONLY.
 *
 * Why: when a risky MMIO access hangs the bus, the watchdog resets the iPad about 20 s later and every in-memory or
 * interrupt-driven log (dmesg, USB network, USB serial) is lost. A plain store into the framebuffer needs neither
 * interrupts nor a driver, and the last frame stays on the panel until the reset. Call fb_crumb_init() at module
 * load (it only maps memory), then fb_crumb_mark(n) right BEFORE each risky step: n white squares appear in a row
 * at the bottom-left of the screen (n = 1..8). After a hang, the number of squares is the last step reached.
 *
 * Source of the geometry: the DT `simple-framebuffer` node that the Pongo/m1n1 hand-off fills in at boot (reg, width,
 * height, stride, format), so nothing is hardcoded. If anything is missing or the mapping fails, crumbs are silently
 * disabled (fb_crumb_state() reports "off"); a diagnostic aid must never stop the experiment. White (0xffffffff) is
 * white in every 32-bit RGB format. The fbcon text console can scroll over the marks if something else prints.
 */
#ifndef FB_BREADCRUMB_H
#define FB_BREADCRUMB_H
#include <linux/io.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/string.h>

#define CRUMB_SQ 32		/* square size in pixels */
#define CRUMB_GAP 8
#define CRUMB_MAX 8

static struct {
	void __iomem *base;
	u32 width, height, stride;
	bool ok;
} fb_crumb_dev;

static void fb_crumb_init(void)
{
	struct device_node *np = of_find_compatible_node(NULL, NULL, "simple-framebuffer");
	struct resource res;
	u32 w, h, s;
	const char *fmt;

	if (!np)
		return;
	if (of_address_to_resource(np, 0, &res) || of_property_read_u32(np, "width", &w) ||
	    of_property_read_u32(np, "height", &h) || of_property_read_u32(np, "stride", &s) ||
	    of_property_read_string(np, "format", &fmt))
		goto out;
	/* 32-bit pixels only, and the squares must fit on screen and inside the region */
	if (s < w * 4 || w < CRUMB_MAX * (CRUMB_SQ + CRUMB_GAP) + CRUMB_GAP || h < 2 * CRUMB_SQ ||
	    resource_size(&res) < (u64)s * h || !strstr(fmt, "8888") ||
	    resource_size(&res) > 64ULL * 1024 * 1024)
		goto out;
	fb_crumb_dev.base = ioremap_wc(res.start, resource_size(&res));
	if (!fb_crumb_dev.base)
		goto out;
	fb_crumb_dev.width = w;
	fb_crumb_dev.height = h;
	fb_crumb_dev.stride = s;
	fb_crumb_dev.ok = true;
out:
	of_node_put(np);
}

static const char *fb_crumb_state(void)
{
	return fb_crumb_dev.ok ? "on" : "off";
}

/* Draw square number n (1..CRUMB_MAX). Plain stores plus a barrier: safe with interrupts off. */
static void fb_crumb_mark(unsigned int n)
{
	u32 x0, y0, x, y;

	if (!fb_crumb_dev.ok || n < 1 || n > CRUMB_MAX)
		return;
	x0 = CRUMB_GAP + (n - 1) * (CRUMB_SQ + CRUMB_GAP);
	y0 = fb_crumb_dev.height - CRUMB_SQ - CRUMB_GAP;
	for (y = 0; y < CRUMB_SQ; y++)
		for (x = 0; x < CRUMB_SQ; x++)
			__raw_writel(0xffffffff, fb_crumb_dev.base + (u64)(y0 + y) * fb_crumb_dev.stride + (x0 + x) * 4);
	wmb();
}
#endif
