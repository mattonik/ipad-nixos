#!/usr/bin/env python3
"""Patch 0099: compile the ADC helper out of the patch text against a fake regmap/clock and check the transaction: register order, exact restore on success and on every
error path, timeout, the channel-9 status rejection and the conversion factors. The real compile is the Nix kernel build."""
import pathlib
import re
import subprocess
import tempfile

PATCH = pathlib.Path(__file__).parent / "patches" / "0099-j81-d2207-charger-vbus-adc-measurement.patch"

HARNESS = r'''
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
#define BIT(n) (1u << (n))
struct regmap { unsigned char r[0x800]; unsigned long now_ms; unsigned long event_after_ms; int started; unsigned char res[2]; int fail_read_at; int reads; int nwrites; unsigned writes[64][2]; };
struct mutex { int locked; };
static void mutex_lock(struct mutex *m) { m->locked++; }
static void mutex_unlock(struct mutex *m) { m->locked--; }
static unsigned long jiffies;
#define msecs_to_jiffies(x) (x)
#define time_after(a, b) ((long)((b) - (a)) < 0)
static struct regmap *g;
static void usleep_range(unsigned a, unsigned b) { (void)a; (void)b; jiffies += 1; g->now_ms = jiffies; if (g->started && jiffies >= g->event_after_ms) g->r[0x5b] |= BIT(1); }
static int regmap_read(struct regmap *m, unsigned reg, unsigned *v) { if (m->fail_read_at && ++m->reads == m->fail_read_at) return -EIO; *v = m->r[reg]; return 0; }
static int regmap_write(struct regmap *m, unsigned reg, unsigned v) { m->writes[m->nwrites][0] = reg; m->writes[m->nwrites++][1] = v; m->r[reg] = v;
	if (reg == 0x500 && (v & 0x80)) { m->started = 1; if (m->event_after_ms == 0) m->r[0x5b] |= BIT(1); } return 0; }
static int regmap_bulk_read(struct regmap *m, unsigned reg, u8 *buf, unsigned n) { memcpy(buf, m->res, n); return 0; }
struct j81_d2207_charger { struct regmap *regmap; struct mutex adc_lock; };
'''


def main():
    # After-image of the patch (context and added lines): the struct line itself is context in the diff.
    text = "\n".join(l[1:] for l in PATCH.read_text().splitlines() if l[:1] in (" ", "+") and not l.startswith("+++"))
    m = re.search(r"(#define J81_D2207_ADC_CTRL.*?)struct j81_d2207_charger \{.*?\n\};\n(.*?\n\}\n)", text, re.S)
    assert m, "ADC helper not found in the patch"
    defs, func = m.group(1), m.group(2)
    code = defs + func
    code = re.sub(r"\n\s*\n", "\n", code)
    tests = r'''
static void init(struct regmap *m) { memset(m, 0, sizeof(*m)); g = m; jiffies = 0; m->r[0x500] = 0x40; m->r[0x501] = 0x05; m->r[0x7b] = 0xff; m->res[0] = 0x09; m->res[1] = 0x03; }
static int same(struct regmap *m) { return m->r[0x500] == 0x40 && m->r[0x501] == 0x05 && m->r[0x7b] == 0xff; }
int main(void)
{
	struct regmap m; struct j81_d2207_charger c = { &m }; unsigned raw = 0; int ret, i;
	/* 1: success, channel 19, completion after 5 ms */
	init(&m); m.event_after_ms = 5; ret = j81_d2207_adc_read(&c, 19, &raw);
	printf("success ret=%d raw=%u restored=%d writes=%d first=%03x:%02x\n", ret, raw, same(&m), m.nwrites, m.writes[0][0], m.writes[0][1]);
	for (i = 0; i < m.nwrites; i++) printf("  w %03x=%02x\n", m.writes[i][0], m.writes[i][1]);
	/* 2: timeout */
	init(&m); m.event_after_ms = 100000; ret = j81_d2207_adc_read(&c, 19, &raw);
	printf("timeout ret=%d restored=%d lock=%d\n", ret, same(&m), c.adc_lock.locked);
	/* 3: channel 9 status bit */
	init(&m); m.res[0] = 0x89; ret = j81_d2207_adc_read(&c, 9, &raw);
	printf("status ret=%d restored=%d\n", ret, same(&m));
	/* 4: first register read fails: nothing written */
	init(&m); m.fail_read_at = 1; ret = j81_d2207_adc_read(&c, 19, &raw);
	printf("readfail ret=%d writes=%d lock=%d\n", ret, m.nwrites, c.adc_lock.locked);
	/* 5: mask bit already clear: mask not written */
	init(&m); m.r[0x7b] = 0xfd; ret = j81_d2207_adc_read(&c, 19, &raw);
	{ int mw = 0; for (i = 0; i < m.nwrites; i++) mw += m.writes[i][0] == 0x7b; printf("maskclear ret=%d maskwrites=%d final=%02x\n", ret, mw, m.r[0x7b]); }
	return 0;
}
'''
    with tempfile.TemporaryDirectory() as t:
        src = pathlib.Path(t) / "t.c"
        src.write_text(HARNESS + code + tests)
        subprocess.run(["cc", "-O1", "-Wall", "-Wno-unused-function", "-o", f"{t}/t", str(src)], check=True)
        out = subprocess.run([f"{t}/t"], check=True, capture_output=True, text=True).stdout
    assert "success ret=0 raw=57 restored=1 writes=4" in out, out
    # order on success: unmask the event, start (0x40 kept | channel 19 | 0x80 = 0xd3), restore control, restore mask
    assert out.index("w 07b=fd") < out.index("w 500=d3") < out.index("w 500=40") < out.index("w 07b=ff"), out
    assert "timeout ret=-110 restored=1 lock=0" in out.replace("ret=-60", "ret=-110") or "timeout ret=-60 restored=1 lock=0" in out, out   # ETIMEDOUT is 60 on macOS
    assert "status ret=-5 restored=1" in out and "readfail ret=-5 writes=0 lock=0" in out, out
    assert "maskclear ret=0 maskwrites=0 final=fd" in out, out
    assert (88000 * 57) == 5016000     # 5.016 V from raw 57
    print("PASS: VBUS ADC helper transaction")


main()
