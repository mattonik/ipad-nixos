// SPDX-License-Identifier: GPL-2.0-only
/*
 * touch-diag: bounded J81 touchscreen power-up diagnostic (RAM-only payload).
 *
 * Sequence and values come from Apple's iPad5,3 iOS 8.1 AppleMultitouchSPI
 * (research/j81-touch-clock-kclt-a8x.md, j81-touch-gpio-polarity-a8x.md,
 * j81-z2-n1-transport-framing.md). By default it makes NO SPI transfer; with
 * --spi-dev it sends only the four handshake frames described below. It uploads firmware only with --upload-fw/--upload-ack/--approve-firmware-upload (see upload_firmware()) and never writes the D2207 voltage register. It answers:
 * "after Apple's power order and one reset release, does the controller
 * raise its boot interrupt on GPIO84?" Then it unwinds in reverse order.
 *
 *   touch-diag [plan]   print the sequence, touch nothing (default)
 *   touch-diag status   read-only: PMU, clock register, GPIO config words
 *   touch-diag run --execute --approve-pmu-write
 *                       perform the sequence; every step is verified and the
 *                       original state is restored on success, error or signal
 *   touch-diag spi-check [--spi-dev D] [--spi-mode M] [--spi-hz H]
 *                       NOT read-only: it opens the spidev node and configures it
 *                       with write ioctls (mode, bits per word, speed), then reads
 *                       the settings back. It sends NO SPI frame, powers nothing
 *                       and touches no other hardware.
 *   ... run ... --spi-dev D [--spi-mode M] [--spi-hz H]
 *                       also send the four minimal frames of
 *                       research/j81-touch-spi-experiment-design.md
 *                       (no firmware, no register write)
 *   ... run ... --spi-dev D --display-sync-pinmux --approve-display-sync-pinmux
 *                       opt-in experiment: before the SPI frames, select
 *                       peripheral function 1 on GPIO55 (Apple's display_sync
 *                       enable, research/2026-10-04-display-sync-pinmux-decode.md).
 *                       This is a PINMUX change of the pin's PERIPH field, NOT a
 *                       GPIO-high write. Requires --spi-dev, refuses a pin that
 *                       is already muxed, and restores the exact saved 32-bit word
 *                       on every exit. A user-approved experiment only.
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/gpio.h>
#include <linux/spi/spidev.h>
#include <poll.h>
#include <stdarg.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define I2C_SLAVE_FORCE 0x0706
#define PMU_ADDR 0x3c
#define PMU_I2C_DEV "/dev/i2c-0"
#define REG_LDO14_ENABLE 0x0084		/* bit 2 enables LDO14 */
#define REG_LDO14_VOLTAGE 0x0398	/* read only; never written here */
#define LDO14_ENABLE_BIT 0x04
#define LDO14_VOLTAGE_EXPECTED 0x14	/* 6.0 V as recorded in the ADT audit */

#define PMGR_BASE 0x20e000000ULL
#define CLK_REG_OFF 0x1e000
#define CLK_GATE_OFF (1u << 31)
#define CLK_APPLY (1u << 19)
#define CLK_BUSY (1u << 18)
#define CLK_DIV_MASK 0x3ffu
#define CLK_DIVIDER 0x2dc		/* 24 MHz / 32768 = 732 */
#define CLK_ENABLE_SETTLE_US 8
#define CLK_DISABLE_SETTLE_US 100

#define GPIO_BASE 0x20e300000ULL
#define GPIO_RESET 82			/* OIPG flags 01 00 01 00: active low */
#define GPIO_IRQ 84
#define GPIO_POWER 95			/* OIPG flags 01 01 00 00: active high */
#define GPIO_DISPLAY_SYNC 55		/* not driven by this diagnostic */
#define GPIO_CS 51			/* owned by the SPI3 pinmux; never requested */
/* Apple pin-mode 2: (word & ~0x260) | 0x220 = PERIPH 1 + input enable. */
#define PINMUX_MASK 0x260u
#define PINMUX_PERIPH1 0x220u
#define PINMUX_PERIPH_FIELD 0x60u	/* bits 6:5 */

#define RESET_DEASSERT_DELAY_MS 15	/* AppleMultitouchSPIJ82 personality */
#define RAIL_DELAY_MS 10		/* conservative; Apple's value unknown */
#define IRQ_TIMEOUT_MS 2000

static int g_i2c = -1, g_mem = -1;
static volatile uint32_t *g_clk;
static volatile uint32_t *g_gpio;
static volatile uint32_t *g_gpio_w;	/* writable GPIO page: only with the pinmux flag */
static int g_ds_pinmux;			/* --display-sync-pinmux acknowledged */
static int g_restore_failed;
static int g_reset_fd = -1, g_power_fd = -1, g_irq_fd = -1;
static volatile sig_atomic_t g_signal;

/*
 * Optional SPI stage (spidev). Defaults: SPI mode 2 (Apple's controller writes
 * CFG 0xd = AUTO_TX | CPOL | ROLESEL, i.e. CPOL=1 CPHA=0) and 124 * 16 kHz.
 * Both can be overridden per run with --spi-mode and --spi-hz.
 */
static const char *g_spi_dev;
/* Apple's J81 touch SPI configuration is LSB-first (research/2026-10-11-touch-no-ack-analysis.md); --spi-msb restores the old spidev default for comparison. */
static int g_spi_lsb = 1;
static unsigned int g_word_delay_us;	/* spidev word_delay_usecs (needs patch 0096); Apple uses 5 */
static int g_detect_ok;
static unsigned int g_spi_mode = 2;		/* CPOL=1, CPHA=0: Apple's decoded default */
static unsigned int g_spi_hz = 1984000;		/* 124 * 16 kHz */
static int g_spi = -1;

/* Frames recovered from AppleMultitouchSPI (research/j81-z2-n1-transport-framing.md). */
static const uint8_t F_DUMMY[16] = { 0x1a, 0xa1, 0x18, 0xe1, 0x18, 0xe1, 0x18, 0xe1,
				     0x18, 0xe1, 0x18, 0xe1, 0x18, 0xe1, 0x18, 0xe1 };
static const uint8_t F_WAKE[16] = { 0xee, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xee, 0 };
static const uint8_t F_ATN_SHORT[2] = { 0x1a, 0xa1 };
static const uint8_t F_ATN_LONG[8] = { 0x1a, 0xa1, 0x18, 0xe1, 0x18, 0xe1, 0x18, 0xe1 };

/* State needed to unwind. */
static struct {
	int ldo_changed, power_on, clock_changed, reset_released, ds_changed;
	uint32_t ds_saved;
	uint8_t ldo_orig;
	uint32_t clk_orig;
} g_st;

static void on_signal(int s) { g_signal = s; }

static void msleep(unsigned int ms)
{
	struct timespec ts = { ms / 1000, (long)(ms % 1000) * 1000000L };
	nanosleep(&ts, NULL);
}

static void usleep_(unsigned int us)
{
	struct timespec ts = { 0, (long)us * 1000L };
	nanosleep(&ts, NULL);
}

static int pmu_read(unsigned int reg, uint8_t *val)
{
	uint8_t a[2] = { reg >> 8, reg & 0xff };

	if (write(g_i2c, a, 2) != 2 || read(g_i2c, val, 1) != 1)
		return -1;
	return 0;
}

static int pmu_write(unsigned int reg, uint8_t val)
{
	uint8_t a[3] = { reg >> 8, reg & 0xff, val };

	return write(g_i2c, a, 3) == 3 ? 0 : -1;
}

static int open_pmu(void)
{
	g_i2c = open(PMU_I2C_DEV, O_RDWR);
	if (g_i2c < 0 || ioctl(g_i2c, I2C_SLAVE_FORCE, PMU_ADDR) < 0) {
		perror("pmu i2c");
		return -1;
	}
	return 0;
}

static int open_mem(int writable, int gpio_writable)
{
	int prot = PROT_READ | (writable ? PROT_WRITE : 0);
	void *p;

	g_mem = open("/dev/mem", writable ? O_RDWR | O_SYNC : O_RDONLY | O_SYNC);
	if (g_mem < 0) {
		perror("/dev/mem");
		return -1;
	}
	p = mmap(NULL, 4096, prot, MAP_SHARED, g_mem, PMGR_BASE + CLK_REG_OFF);
	if (p == MAP_FAILED) {
		perror("mmap clock");
		return -1;
	}
	g_clk = p;
	p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, g_mem, GPIO_BASE);
	if (p == MAP_FAILED) {
		perror("mmap gpio");
		return -1;
	}
	g_gpio = p;
	if (gpio_writable) {
		/* A second, writable view, created only for the opt-in pinmux experiment. */
		p = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, g_mem, GPIO_BASE);
		if (p == MAP_FAILED) {
			perror("mmap gpio (writable)");
			return -1;
		}
		g_gpio_w = p;
	}
	return 0;
}

static int request_line(unsigned int line, uint64_t flags, int out_value, const char *name)
{
	struct gpio_v2_line_request rq;
	int chip = open("/dev/gpiochip0", O_RDWR), fd;

	if (chip < 0) {
		perror("gpiochip0");
		return -1;
	}
	memset(&rq, 0, sizeof(rq));
	rq.offsets[0] = line;
	rq.num_lines = 1;
	strncpy(rq.consumer, name, sizeof(rq.consumer) - 1);
	rq.config.flags = flags;
	if (flags & GPIO_V2_LINE_FLAG_OUTPUT) {
		rq.config.num_attrs = 1;
		rq.config.attrs[0].attr.id = GPIO_V2_LINE_ATTR_ID_OUTPUT_VALUES;
		rq.config.attrs[0].attr.values = out_value ? 1 : 0;
		rq.config.attrs[0].mask = 1;
	}
	if (ioctl(chip, GPIO_V2_GET_LINE_IOCTL, &rq) < 0) {
		perror("GPIO_V2_GET_LINE");
		fd = -1;
	} else {
		fd = rq.fd;
	}
	close(chip);
	return fd;
}

static int set_line(int fd, int logical)
{
	struct gpio_v2_line_values v = { .bits = logical ? 1 : 0, .mask = 1 };

	return ioctl(fd, GPIO_V2_LINE_SET_VALUES_IOCTL, &v);
}

static int get_line(int fd)
{
	struct gpio_v2_line_values v = { .bits = 0, .mask = 1 };

	if (ioctl(fd, GPIO_V2_LINE_GET_VALUES_IOCTL, &v) < 0)
		return -1;
	return v.bits & 1;
}

static int clk_wait_not_busy(void)
{
	for (int i = 0; i < 10000; i++) {
		if (!(*g_clk & CLK_BUSY))
			return 0;
		usleep_(10);
	}
	return -1;
}

static int clock_enable(void)
{
	uint32_t r = *g_clk;

	*g_clk = r & 0x7fffffffu;
	usleep_(CLK_ENABLE_SETTLE_US);
	*g_clk = (r & 0x7ff7fc00u) | CLK_DIVIDER | CLK_APPLY;
	return clk_wait_not_busy();
}

static int clock_disable(void)
{
	uint32_t r = *g_clk;

	*g_clk = r & ~CLK_APPLY;
	if (clk_wait_not_busy())
		return -1;
	*g_clk = (r & ~CLK_APPLY) | CLK_GATE_OFF;
	usleep_(CLK_DISABLE_SETTLE_US);
	return 0;
}

static void say(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void say(const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	vprintf(fmt, ap);
	va_end(ap);
	fflush(stdout);
}

/* Reverse order of the power-up; every step is best-effort and logged. */
static void unwind(void)
{
	say("unwind: asserting reset\n");
	if (g_reset_fd >= 0)
		set_line(g_reset_fd, 1);
	if (g_st.ds_changed && g_gpio_w) {
		uint32_t rb;

		g_gpio_w[GPIO_DISPLAY_SYNC] = g_st.ds_saved;
		rb = g_gpio[GPIO_DISPLAY_SYNC];
		say("unwind: GPIO%d word restored 0x%08x (saved 0x%08x)%s\n", GPIO_DISPLAY_SYNC, rb,
		    g_st.ds_saved, rb == g_st.ds_saved ? "" : "  RESTORE MISMATCH");
		if (rb != g_st.ds_saved)
			g_restore_failed = 1;
		g_st.ds_changed = 0;
	}
	if (g_st.power_on && g_power_fd >= 0) {
		say("unwind: GPIO95 low\n");
		set_line(g_power_fd, 0);
		g_st.power_on = 0;
	}
	if (g_st.ldo_changed) {
		uint8_t v = 0;

		say("unwind: restoring LDO14 enable 0x%02x\n", g_st.ldo_orig);
		pmu_write(REG_LDO14_ENABLE, g_st.ldo_orig);
		if (!pmu_read(REG_LDO14_ENABLE, &v))
			say("unwind: LDO14 enable reads 0x%02x\n", v);
		g_st.ldo_changed = 0;
	}
	if (g_st.clock_changed) {
		say("unwind: disabling touch clock\n");
		clock_disable();
		say("unwind: clock register 0x%08x (was 0x%08x)\n", *g_clk, g_st.clk_orig);
		g_st.clock_changed = 0;
	}
}

static int spi_open(void)
{
	uint8_t mode = (g_spi_mode & 3) | (g_spi_lsb ? SPI_LSB_FIRST : 0), bits = 8, rbits = 0, rmode = 0;
	uint32_t hz = g_spi_hz, rhz = 0;

	if (!g_spi_dev) {
		fprintf(stderr, "no --spi-dev given\n");
		return -1;
	}
	g_spi = open(g_spi_dev, O_RDWR);
	if (g_spi < 0) {
		perror(g_spi_dev);
		return -1;
	}
	if (ioctl(g_spi, SPI_IOC_WR_MODE, &mode) < 0 ||
	    ioctl(g_spi, SPI_IOC_WR_BITS_PER_WORD, &bits) < 0 ||
	    ioctl(g_spi, SPI_IOC_WR_MAX_SPEED_HZ, &hz) < 0) {
		perror("spidev configure");
		return -1;
	}
	if (ioctl(g_spi, SPI_IOC_RD_MODE, &rmode) < 0 ||
	    ioctl(g_spi, SPI_IOC_RD_BITS_PER_WORD, &rbits) < 0 ||
	    ioctl(g_spi, SPI_IOC_RD_MAX_SPEED_HZ, &rhz) < 0) {
		perror("spidev readback");
		return -1;
	}
	say("spidev %s: mode %u (CPOL %u CPHA %u), %s, %u bits, %u Hz\n", g_spi_dev, rmode & 3,
	    !!(rmode & SPI_CPOL), !!(rmode & SPI_CPHA), (rmode & SPI_LSB_FIRST) ? "LSB first" : "MSB first", rbits, rhz);
	return (rmode & (3 | SPI_LSB_FIRST)) == mode && rbits == bits && rhz == hz ? 0 : -1;
}

/* The seven words Apple's HBPP detect accepts (research/2026-10-11-touch-no-ack-analysis.md). */
static int known_word(unsigned int w)
{
	return w == 0x18e1 || w == 0x1aa1 || w == 0x1f01 || w == 0x4879 || w == 0x4969 || w == 0x4ad1 || w == 0x4bc1;
}

static int g_last_known[2];

static void hexline(const char *label, const uint8_t *tx, const uint8_t *rx, unsigned int n)
{
	say("  %-10s tx", label);
	for (unsigned int i = 0; i < n; i++)
		say(" %02x", tx[i]);
	say("\n  %-10s rx", "");
	for (unsigned int i = 0; i < n; i++)
		say(" %02x", rx[i]);
	g_last_known[0] = n >= 2 && known_word(rx[0] << 8 | rx[1]);
	g_last_known[1] = n >= 4 && known_word(rx[2] << 8 | rx[3]);
	say("   [known words: first %s, second %s]\n", g_last_known[0] ? "yes" : "no", g_last_known[1] ? "yes" : "no");
}

/* One full-duplex transfer = one chip-select interval. */
static int spi_frame(const char *label, const uint8_t *tx, unsigned int n)
{
	uint8_t rx[16] = { 0 };
	struct spi_ioc_transfer t;

	memset(&t, 0, sizeof(t));
	t.tx_buf = (uintptr_t)tx;
	t.rx_buf = (uintptr_t)rx;
	t.len = n;
	t.speed_hz = g_spi_hz;
	t.bits_per_word = 8;
	t.word_delay_usecs = g_word_delay_us;
	if (ioctl(g_spi, SPI_IOC_MESSAGE(1), &t) < 0) {
		perror("spi transfer");
		return -1;
	}
	hexline(label, tx, rx, n);
	return 0;
}

/*
 * Firmware-upload experiment (research/2026-10-11-touch-firmware-upload-spec.md): ONE full-duplex message with the 59,288-byte constructed packet exported by
 * boot/touch_fw_packets.py, then the 2-byte ATN/ACK query; the only accepted reply is 4b c1. No retry, no calibration, no execute command.
 * Needs spidev.bufsiz >= the packet size (the default 4096 would reject it). Only the reply length and the ACK bytes are printed; the packet content is never logged.
 */
static const char *g_fw_file, *g_ack_file;
static unsigned int g_ack_tries = 1, g_chunk;
static int g_apple_upload, g_apple_order, g_upload_rx, g_probe_txonly;
static unsigned int g_chunk_delay_us;	/* delay after every chunk of a chunked transmit-only packet (--chunk N --chunk-delay-us D) */
static const char *g_probe_sizes;	/* comma-separated byte counts for the transfer-size probe */

static uint8_t *slurp(const char *path, unsigned int max, unsigned int *len)
{
	FILE *f = fopen(path, "rb");
	uint8_t *b;
	long n;

	if (!f) {
		perror(path);
		return NULL;
	}
	fseek(f, 0, SEEK_END);
	n = ftell(f);
	rewind(f);
	if (n <= 0 || (unsigned long)n > max) {
		fprintf(stderr, "%s: bad size %ld\n", path, n);
		fclose(f);
		return NULL;
	}
	b = malloc(n);
	if (!b || fread(b, 1, n, f) != (size_t)n) {
		fclose(f);
		free(b);
		return NULL;
	}
	fclose(f);
	*len = n;
	return b;
}

static int upload_firmware(void)
{
	unsigned int fn = 0, an = 0;
	uint8_t *fw = slurp(g_fw_file, 0x10000, &fn), *ack = slurp(g_ack_file, 16, &an);
	uint8_t *rx = NULL, arx[16] = { 0 };
	struct spi_ioc_transfer t;
	int rc = -1;

	if (!fw || !ack)
		goto out;
	if (fn < 2 || fw[0] != 0x18 || fw[1] != 0xe1 || (fn & 3) || an != 2 || ack[0] != 0x1a || ack[1] != 0xa1) {
		fprintf(stderr, "packet sanity check failed (need 18 e1 header, 4-byte aligned length, ack 1a a1)\n");
		goto out;
	}
	if (g_apple_upload) {
		/*
		 * Apple's order (research/2026-10-11-touch-no-ack-analysis.md): the firmware is ONE transmit-only transfer (no rx buffer), the 2-byte ATN/ACK query follows
		 * immediately, and the packet + query pair is retried up to five times (g_ack_tries, capped at 5). No other delay, no IRQ watching.
		 */
		for (unsigned int k = 0; k < g_ack_tries && k < 5; k++) {
			struct timespec t0, t1;
			double ms;

			if (g_chunk && g_chunk < fn && !g_upload_rx) {
				/* Same bytes, still ONE message (chip select held), cut into transmit-only chunks with a pause after each: gives the ROM time to drain its receive buffer. */
				unsigned int nx = (fn + g_chunk - 1) / g_chunk, i2;
				struct spi_ioc_transfer *xs = calloc(nx, sizeof(*xs));

				if (!xs)
					goto out;
				for (i2 = 0; i2 < nx; i2++) {
					unsigned int off = i2 * g_chunk;

					xs[i2].tx_buf = (uintptr_t)(fw + off);
					xs[i2].len = fn - off < g_chunk ? fn - off : g_chunk;
					xs[i2].speed_hz = g_spi_hz;
					xs[i2].bits_per_word = 8;
					xs[i2].word_delay_usecs = g_word_delay_us;
					xs[i2].delay_usecs = i2 + 1 < nx ? g_chunk_delay_us : 0;
				}
				say("upload: pair %u: sending %u bytes transmit-only as %u chunks of %u bytes, %u us pause after each, %u Hz\n", k + 1, fn, nx, g_chunk, g_chunk_delay_us, g_spi_hz);
				clock_gettime(CLOCK_MONOTONIC, &t0);
				i2 = ioctl(g_spi, SPI_IOC_MESSAGE(nx), xs);
				free(xs);
				if ((int)i2 < 0) {
					perror("firmware transfer (chunked)");
					goto out;
				}
				clock_gettime(CLOCK_MONOTONIC, &t1);
				ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
				say("upload: transfer took %.1f ms\n", ms);
			} else {
				memset(&t, 0, sizeof(t));
				t.tx_buf = (uintptr_t)fw;
				if (g_upload_rx) {
					if (!rx)
						rx = calloc(1, fn);
					if (!rx)
						goto out;
					memset(rx, 0, fn);
					t.rx_buf = (uintptr_t)rx;
				}
				t.len = fn;
				t.speed_hz = g_spi_hz;
				t.bits_per_word = 8;
				t.word_delay_usecs = g_word_delay_us;
				say("upload: pair %u: sending %u bytes %s, one transfer, %u Hz, word delay %u us\n", k + 1, fn, g_upload_rx ? "full duplex (reply captured)" : "transmit-only",
				    g_spi_hz, g_word_delay_us);
				clock_gettime(CLOCK_MONOTONIC, &t0);
				if (ioctl(g_spi, SPI_IOC_MESSAGE(1), &t) < 0) {
					perror("firmware transfer");
					goto out;
				}
				clock_gettime(CLOCK_MONOTONIC, &t1);
				ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
				say("upload: transfer took %.1f ms (%.2f us per byte; bare clock alone would be %.2f us per byte)\n", ms, ms * 1000.0 / fn, 8e6 / g_spi_hz);
			}
			if (g_upload_rx) {
				/* Only the ROM's reply is summarised, never the packet. */
				unsigned int same = 0, i;
				uint16_t first = rx[0] << 8 | rx[1];

				for (i = 0; i + 1 < fn; i += 2)
					same += (uint16_t)(rx[i] << 8 | rx[i + 1]) == first;
				say("upload: reply during transfer: first bytes");
				for (i = 0; i < 16; i++)
					say(" %02x", rx[i]);
				say("; %u of %u words equal the first word\n", same, fn / 2);
			}
			memset(&t, 0, sizeof(t));
			memset(arx, 0, sizeof(arx));
			t.tx_buf = (uintptr_t)ack;
			t.rx_buf = (uintptr_t)arx;
			t.len = an;
			t.speed_hz = g_spi_hz;
			t.bits_per_word = 8;
			t.word_delay_usecs = g_word_delay_us;
			if (ioctl(g_spi, SPI_IOC_MESSAGE(1), &t) < 0) {
				perror("ack query");
				goto out;
			}
			say("upload: pair %u ack reply %02x %02x (expected 4b c1)\n", k + 1, arx[0], arx[1]);
			if (arx[0] == 0x4b && arx[1] == 0xc1) {
				rc = 0;
				break;
			}
			if (g_signal)
				break;
		}
		say("upload: %s\n", rc ? "NOT ACKNOWLEDGED after the pair retries" : "ACKNOWLEDGED");
		if (rc) {
			/* Post-mortem without resending anything: repeat the query, then the long ATN, then the detect frame, to see whether the ROM is still alive. */
			static const unsigned int gap_ms[3] = { 0, 1, 10 };

			for (unsigned int k = 0; k < 3; k++) {
				if (gap_ms[k])
					msleep(gap_ms[k]);
				spi_frame("post-query", F_ATN_SHORT, sizeof(F_ATN_SHORT));
			}
			spi_frame("post-atn8", F_ATN_LONG, sizeof(F_ATN_LONG));
			spi_frame("post-detect", F_DUMMY, sizeof(F_DUMMY));
		}
		goto out;
	}
	rx = calloc(1, fn);
	if (!rx)
		goto out;
	if (!g_chunk || g_chunk >= fn) {
		memset(&t, 0, sizeof(t));
		t.tx_buf = (uintptr_t)fw;
		t.rx_buf = (uintptr_t)rx;
		t.len = fn;
		t.speed_hz = g_spi_hz;
		t.bits_per_word = 8;
		t.word_delay_usecs = g_word_delay_us;
		say("upload: sending %u bytes as one message, one transfer, %u Hz\n", fn, g_spi_hz);
		if (ioctl(g_spi, SPI_IOC_MESSAGE(1), &t) < 0) {
			perror("firmware transfer");
			goto out;
		}
	} else {
		/* Same bytes, same single message (chip select stays asserted: cs_change = 0 on every transfer), but cut into g_chunk-byte transfers so the controller
		 * driver handles short PIO runs instead of one 59 KB run. The byte stream on the wire is unchanged. */
		unsigned int nx = (fn + g_chunk - 1) / g_chunk;
		struct spi_ioc_transfer *xs = calloc(nx, sizeof(*xs));
		int r;

		if (!xs)
			goto out;
		for (unsigned int i = 0; i < nx; i++) {
			unsigned int off = i * g_chunk, len = fn - off < g_chunk ? fn - off : g_chunk;

			xs[i].tx_buf = (uintptr_t)(fw + off);
			xs[i].rx_buf = (uintptr_t)(rx + off);
			xs[i].len = len;
			xs[i].speed_hz = g_spi_hz;
			xs[i].bits_per_word = 8;
			xs[i].word_delay_usecs = g_word_delay_us;
		}
		say("upload: sending %u bytes as one message, %u transfers of %u bytes, %u Hz\n", fn, nx, g_chunk, g_spi_hz);
		r = ioctl(g_spi, SPI_IOC_MESSAGE(nx), xs);
		free(xs);
		if (r < 0) {
			perror("firmware transfer (chunked)");
			goto out;
		}
	}
	say("upload: transfer completed\n");
	/*
	 * Repeat-query experiment: the packet is NOT resent. The ATN/ACK query is repeated up to g_ack_tries times on a growing delay schedule; during each wait the IRQ line is
	 * watched (falling-edge events counted, level logged) so the log shows whether the controller reacts to the transfer at all. Stops at the first 4b c1.
	 */
	{
		static const unsigned int wait_ms[] = { 0, 2, 10, 50, 200, 1000, 1000, 1000, 1000, 1000 };

		for (unsigned int k = 0; k < g_ack_tries; k++) {
			struct pollfd pf = { .fd = g_irq_fd, .events = POLLIN };
			int edges = 0;
			struct gpio_v2_line_event ev;

			if (wait_ms[k]) {
				int left = wait_ms[k];

				while (left > 0 && poll(&pf, 1, left) > 0 && (pf.revents & POLLIN)) {
					if (read(g_irq_fd, &ev, sizeof(ev)) == (ssize_t)sizeof(ev))
						edges++;
					left = 0;	/* count the first edge; the level below shows the rest */
				}
			}
			memset(&t, 0, sizeof(t));
			memset(arx, 0, sizeof(arx));
			t.tx_buf = (uintptr_t)ack;
			t.rx_buf = (uintptr_t)arx;
			t.len = an;
			t.speed_hz = g_spi_hz;
			t.bits_per_word = 8;
			t.word_delay_usecs = g_word_delay_us;
			if (ioctl(g_spi, SPI_IOC_MESSAGE(1), &t) < 0) {
				perror("ack query");
				goto out;
			}
			say("upload: query %u after wait %u ms: irq edges %d, irq level %d, reply %02x %02x\n", k + 1, wait_ms[k], edges, get_line(g_irq_fd), arx[0], arx[1]);
			if (arx[0] == 0x4b && arx[1] == 0xc1) {
				rc = 0;
				break;
			}
			if (g_signal) {
				say("interrupted\n");
				break;
			}
		}
	}
	say("upload: %s\n", rc ? "NOT ACKNOWLEDGED, aborting (the packet is not resent)" : "ACKNOWLEDGED");
out:
	free(fw);
	free(ack);
	free(rx);
	return rc;
}

/*
 * Transfer-size probe (no firmware): after the detect frame, send ATN frames `1a a1` + `18 e1` words (words the ROM already accepts) of each requested size as ONE full-duplex
 * transfer, time each one, and summarise the reply. Finds where the SPI controller's PIO path breaks (transfers larger than its 16-byte FIFO hung in the T3 run).
 * Stops at the first failed transfer.
 */
static int probe_sizes(void)
{
	char *list = strdup(g_probe_sizes), *tok, *save = NULL;
	int rc = 0;

	for (tok = strtok_r(list, ",", &save); tok && !rc; tok = strtok_r(NULL, ",", &save)) {
		unsigned int n = strtoul(tok, NULL, 0), i, ok = 0;
		uint8_t *tx, *rx;
		struct spi_ioc_transfer t;
		struct timespec t0, t1;
		double ms;

		if (n < 2 || n > 8192 || (n & 1)) {
			say("probe: skipping bad size %s\n", tok);
			continue;
		}
		tx = malloc(n);
		rx = calloc(1, n);
		if (!tx || !rx) {
			rc = -1;
			break;
		}
		tx[0] = 0x1a;
		tx[1] = 0xa1;
		for (i = 2; i + 1 < n; i += 2) {
			tx[i] = 0x18;
			tx[i + 1] = 0xe1;
		}
		memset(&t, 0, sizeof(t));
		t.tx_buf = (uintptr_t)tx;
		t.rx_buf = g_probe_txonly ? 0 : (uintptr_t)rx;
		t.len = n;
		t.speed_hz = g_spi_hz;
		t.bits_per_word = 8;
		t.word_delay_usecs = g_word_delay_us;
		clock_gettime(CLOCK_MONOTONIC, &t0);
		if (ioctl(g_spi, SPI_IOC_MESSAGE(1), &t) < 0) {
			say("probe %u bytes: FAILED (%s)\n", n, strerror(errno));
			rc = -1;
		} else {
			clock_gettime(CLOCK_MONOTONIC, &t1);
			ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
			for (i = 0; i + 1 < n; i += 2)
				ok += (rx[i] << 8 | rx[i + 1]) == 0x1f01;
			say("probe %u bytes: %.2f ms (%.2f us/byte; clock alone %.2f), reply words 1f01: %u of %u, first bytes %02x %02x %02x %02x\n", n, ms, ms * 1000.0 / n,
			    8e6 / g_spi_hz, ok, n / 2, rx[0], rx[1], rx[2], rx[3]);
		}
		free(tx);
		free(rx);
	}
	free(list);
	return rc;
}

static int status(void)
{
	uint8_t v;
	static const unsigned int pins[] = { GPIO_CS, GPIO_DISPLAY_SYNC, GPIO_RESET, GPIO_IRQ, GPIO_POWER };

	if (open_pmu() || open_mem(0, 0))
		return 1;
	if (!pmu_read(REG_LDO14_ENABLE, &v))
		say("PMU 0x%04x LDO14 enable   = 0x%02x (bit2 %s)\n", REG_LDO14_ENABLE, v,
		    (v & LDO14_ENABLE_BIT) ? "on" : "off");
	if (!pmu_read(REG_LDO14_VOLTAGE, &v))
		say("PMU 0x%04x LDO14 voltage  = 0x%02x\n", REG_LDO14_VOLTAGE, v);
	say("PMGR+0x%x touch clock    = 0x%08x (gate-off %u, busy %u, divider %u)\n", CLK_REG_OFF,
	    *g_clk, !!(*g_clk & CLK_GATE_OFF), !!(*g_clk & CLK_BUSY), *g_clk & CLK_DIV_MASK);
	for (unsigned int i = 0; i < sizeof(pins) / sizeof(pins[0]); i++)
		say("GPIO%-3u config word       = 0x%08x\n", pins[i], g_gpio[pins[i]]);
	return 0;
}

static void plan(void)
{
	say("touch-diag plan (nothing is touched in plan mode):\n"
	    " 0. read-only snapshot; abort unless LDO14 is off and voltage is 0x%02x\n"
	    " 1. GPIO%d (reset, active low): request, assert (drive low)\n"
	    " 2. touch clock at PMGR+0x%x: Apple's enable, divider %u, then verify\n"
	    " 3. D2207 0x%04x |= 0x%02x (LDO14), read back (voltage register never written)\n"
	    " 4. GPIO%d (power_ldo, active high): drive high, wait %d ms\n"
	    " 5. skip display_sync (GPIO%d) and the dummy SPI transfer: no SPI at all\n"
	    " 6. release reset (drive high), wait %d ms, then watch GPIO%d for up to %d ms\n"
	    " 7. unwind in reverse: reset low, GPIO%d low, LDO14 restored, clock disabled\n"
	    "Optional opt-in experiment (needs --spi-dev): --display-sync-pinmux\n"
	    "    --approve-display-sync-pinmux selects peripheral function 1 on GPIO55 before step 5\n"
	    "    (a pinmux change, not a GPIO-high write); refused if the pin is already muxed;\n"
	    "    the exact saved word is restored on every exit\n"
	    "Optional SPI stage: add --spi-dev /dev/spidevB.C [--spi-mode 0..3] [--spi-hz N]:\n"
	    "    before step 6 a 16-byte dummy transfer; after the IRQ edge wake, short and long\n"
	    "    ATN/ACK (handshake frames only: no firmware, no register write)\n"
	    "Run with: touch-diag run --execute --approve-pmu-write\n",
	    LDO14_VOLTAGE_EXPECTED, GPIO_RESET, CLK_REG_OFF, CLK_DIVIDER, REG_LDO14_ENABLE,
	    LDO14_ENABLE_BIT, GPIO_POWER, RAIL_DELAY_MS, GPIO_DISPLAY_SYNC,
	    RESET_DEASSERT_DELAY_MS, GPIO_IRQ, IRQ_TIMEOUT_MS, GPIO_POWER);
}

#define CHECK_ABORT() do { if (g_signal) { say("signal %d: unwinding\n", (int)g_signal); rc = 3; goto out; } } while (0)

static int step_clock(void)
{
	say("step 2: touch clock enable\n");
	g_st.clock_changed = 1;
	if (clock_enable()) {
		say("abort: clock busy bit did not clear\n");
		return -1;
	}
	say("        clock register now 0x%08x\n", *g_clk);
	return 0;
}

static int step_ldo(uint8_t *v)
{
	say("step 3: LDO14 enable\n");
	g_st.ldo_changed = 1;
	if (pmu_write(REG_LDO14_ENABLE, g_st.ldo_orig | LDO14_ENABLE_BIT) ||
	    pmu_read(REG_LDO14_ENABLE, v) || !(*v & LDO14_ENABLE_BIT)) {
		say("abort: LDO14 enable did not read back (0x%02x)\n", *v);
		return -1;
	}
	say("        LDO14 enable reads 0x%02x\n", *v);
	return 0;
}

static int step_power(void)
{
	say("step 4: GPIO%d high\n", GPIO_POWER);
	g_power_fd = request_line(GPIO_POWER, GPIO_V2_LINE_FLAG_OUTPUT, 0, "touch-diag-power");
	if (g_power_fd < 0)
		return -1;
	if (set_line(g_power_fd, 1)) {
		perror("power set");
		return -1;
	}
	g_st.power_on = 1;
	return 0;
}

static int run(void)
{
	int rc = 1, level_before = -1, level_after = -1, got_edge = 0;
	uint8_t v = 0, volt = 0;

	if (open_pmu() || open_mem(1, g_ds_pinmux))
		return 1;
	if (pmu_read(REG_LDO14_ENABLE, &g_st.ldo_orig) || pmu_read(REG_LDO14_VOLTAGE, &volt)) {
		say("abort: cannot read PMU\n");
		return 1;
	}
	if (g_spi_dev && spi_open()) {
		say("abort: spidev did not accept the requested settings\n");
		return 1;
	}
	g_st.clk_orig = *g_clk;
	say("snapshot: LDO14 enable 0x%02x voltage 0x%02x clock 0x%08x\n", g_st.ldo_orig, volt,
	    g_st.clk_orig);
	if ((g_st.ldo_orig & LDO14_ENABLE_BIT) || volt != LDO14_VOLTAGE_EXPECTED) {
		say("abort: LDO14 is not in the expected off/6.0V state; refusing to run\n");
		return 1;
	}
	if (!(g_st.clk_orig & CLK_GATE_OFF))
		say("note: touch clock gate already open before the test\n");

	g_reset_fd = request_line(GPIO_RESET, GPIO_V2_LINE_FLAG_OUTPUT | GPIO_V2_LINE_FLAG_ACTIVE_LOW,
				  1, "touch-diag-reset");
	if (g_reset_fd < 0)
		return 1;
	say("step 1: reset asserted (logical 1, drives low)\n");
	g_irq_fd = request_line(GPIO_IRQ, GPIO_V2_LINE_FLAG_INPUT | GPIO_V2_LINE_FLAG_EDGE_FALLING |
				GPIO_V2_LINE_FLAG_EDGE_RISING, 0, "touch-diag-irq");
	if (g_irq_fd < 0)
		goto out;
	level_before = get_line(g_irq_fd);
	CHECK_ABORT();

	if (!g_apple_order) {
		if (step_clock())
			goto out;
		CHECK_ABORT();
		if (step_ldo(&v))
			goto out;
		CHECK_ABORT();
		if (step_power())
			goto out;
		msleep(RAIL_DELAY_MS);
		CHECK_ABORT();
	} else {
		/* Apple's order: LDO14, GPIO95 (no delay), 5 ms, clock, 15 ms, the 2-byte wake 19 c1 (reply ignored) with reset still asserted, 10 ms. */
		static const uint8_t F_WAKE2[2] = { 0x19, 0xc1 };

		if (step_ldo(&v) || step_power())
			goto out;
		CHECK_ABORT();
		msleep(5);
		if (step_clock())
			goto out;
		msleep(15);
		CHECK_ABORT();
		if (g_spi_dev) {
			say("step 4a: 2-byte wake 19 c1 (reset still asserted)\n");
			if (spi_frame("wake19c1", F_WAKE2, sizeof(F_WAKE2)))
				goto out;
			msleep(10);
		}
		CHECK_ABORT();
	}

	if (g_ds_pinmux) {
		uint32_t saved = g_gpio[GPIO_DISPLAY_SYNC], want, rb;

		say("step 4b: GPIO%d display_sync pinmux (PERIPH field, not a level)\n", GPIO_DISPLAY_SYNC);
		say("        saved word 0x%08x\n", saved);
		if (saved & PINMUX_PERIPH_FIELD) {
			say("abort: GPIO%d is already muxed to a peripheral (PERIPH != 0); not touching it\n",
			    GPIO_DISPLAY_SYNC);
			goto out;
		}
		want = (saved & ~PINMUX_MASK) | PINMUX_PERIPH1;
		g_st.ds_saved = saved;
		g_st.ds_changed = 1;		/* set first so every exit restores */
		g_gpio_w[GPIO_DISPLAY_SYNC] = want;
		rb = g_gpio[GPIO_DISPLAY_SYNC];
		say("        requested field 0x%03x, wrote 0x%08x, readback 0x%08x\n", PINMUX_PERIPH1, want, rb);
		if ((rb & PINMUX_MASK) != PINMUX_PERIPH1) {
			say("abort: pinmux readback does not show PERIPH=1\n");
			goto out;
		}
		CHECK_ABORT();
	}

	if (g_spi_dev) {
		say("step 5: SPI dummy transfer (clock high before reset release)\n");
		if (spi_frame("dummy", F_DUMMY, sizeof(F_DUMMY)))
			goto out;
		CHECK_ABORT();
	}

	say("step 6: release reset\n");
	if (set_line(g_reset_fd, 0)) {
		perror("reset release");
		goto out;
	}
	g_st.reset_released = 1;
	msleep(RESET_DEASSERT_DELAY_MS);
	for (int waited = 0; waited < IRQ_TIMEOUT_MS && !g_signal; waited += 50) {
		struct pollfd p = { .fd = g_irq_fd, .events = POLLIN };

		if (poll(&p, 1, 50) > 0 && (p.revents & POLLIN)) {
			struct gpio_v2_line_event ev;

			if (read(g_irq_fd, &ev, sizeof(ev)) == (ssize_t)sizeof(ev)) {
				say("        IRQ edge (%s) after ~%d ms\n",
				    ev.id == GPIO_V2_LINE_EVENT_RISING_EDGE ? "rising" : "falling", waited);
				got_edge = 1;
				break;
			}
		}
	}
	level_after = get_line(g_irq_fd);
	CHECK_ABORT();
	if (g_spi_dev) {
		/* Apple's HBPP detect: after reset release plus 15 ms + 15 ms, the 16-byte frame must come back with two known words. */
		msleep(30);
		say("step 6b: detect frame (Apple: both reply words must be known)\n");
		if (spi_frame("detect", F_DUMMY, sizeof(F_DUMMY)))
			goto out;
		g_detect_ok = g_last_known[0] && g_last_known[1];
		say("DETECT %s\n", g_detect_ok ? "PASS" : "FAIL");
	}
	if (g_spi_dev && g_probe_sizes) {
		if (g_detect_ok) {
			say("step 7: transfer-size probe (no firmware)\n");
			if (probe_sizes())
				goto out;
		} else {
			say("step 7 skipped: detect frame failed, not probing\n");
		}
	} else if (g_spi_dev && g_fw_file && !g_detect_ok) {
		say("step 7 skipped: detect frame failed, not sending firmware\n");
	} else if (g_spi_dev && g_fw_file) {
		if (g_apple_order)
			msleep(30);	/* Apple starts bootloadDevice at least 15 ms after the detect */
		say("step 7: firmware upload experiment\n");
		if (upload_firmware())
			goto out;
	} else if (g_spi_dev && (got_edge || g_detect_ok)) {
		say("step 7: minimal frames (handshake only: no firmware, no register write)\n");
		if (spi_frame("wake", F_WAKE, sizeof(F_WAKE)) ||
		    spi_frame("atn-short", F_ATN_SHORT, sizeof(F_ATN_SHORT)) ||
		    spi_frame("atn-long", F_ATN_LONG, sizeof(F_ATN_LONG)))
			goto out;
	} else if (g_spi_dev) {
		say("step 7 skipped: no boot interrupt, not sending frames\n");
	}
	rc = 0;
out:
	say("RESULT irq_edge=%d level_before=%d level_after=%d\n", got_edge, level_before, level_after);
	unwind();
	return rc;
}

int main(int argc, char **argv)
{
	const char *cmd = argc > 1 ? argv[1] : "plan";

	signal(SIGINT, on_signal);
	signal(SIGTERM, on_signal);
	if (!strcmp(cmd, "plan")) {
		plan();
		return 0;
	}
	if (!strcmp(cmd, "status"))
		return status();
	for (int i = 2; i < argc; i++) {
		if (!strcmp(argv[i], "--spi-msb"))
			g_spi_lsb = 0;
		else if (!strcmp(argv[i], "--apple-upload"))
			g_apple_upload = 1;
		else if (!strcmp(argv[i], "--apple-order"))
			g_apple_order = 1;
		else if (!strcmp(argv[i], "--probe-txonly"))
			g_probe_txonly = 1;
		else if (!strcmp(argv[i], "--upload-rx"))
			g_upload_rx = 1;
	}
	for (int i = 2; i + 1 < argc; i++) {
		if (!strcmp(argv[i], "--spi-dev"))
			g_spi_dev = argv[i + 1];
		else if (!strcmp(argv[i], "--spi-mode"))
			g_spi_mode = strtoul(argv[i + 1], NULL, 0);
		else if (!strcmp(argv[i], "--spi-hz"))
			g_spi_hz = strtoul(argv[i + 1], NULL, 0);
		else if (!strcmp(argv[i], "--upload-fw"))
			g_fw_file = argv[i + 1];
		else if (!strcmp(argv[i], "--chunk-delay-us"))
			g_chunk_delay_us = strtoul(argv[i + 1], NULL, 0);
		else if (!strcmp(argv[i], "--probe-sizes"))
			g_probe_sizes = argv[i + 1];
		else if (!strcmp(argv[i], "--chunk"))
			g_chunk = strtoul(argv[i + 1], NULL, 0);
		else if (!strcmp(argv[i], "--word-delay-us"))
			g_word_delay_us = strtoul(argv[i + 1], NULL, 0);
		else if (!strcmp(argv[i], "--ack-tries"))
			g_ack_tries = strtoul(argv[i + 1], NULL, 0);
		else if (!strcmp(argv[i], "--upload-ack"))
			g_ack_file = argv[i + 1];
	}
	if (g_chunk && (g_chunk < 128 || g_chunk > 32768 || (g_chunk & 3))) {
		fprintf(stderr, "--chunk must be 128..32768 and a multiple of 4\n");
		return 2;
	}
	if (g_ack_tries < 1 || g_ack_tries > 10) {
		fprintf(stderr, "--ack-tries must be 1..10\n");
		return 2;
	}
	if (g_spi_mode > 3 || g_spi_hz < 10000 || g_spi_hz > 8000000) {
		fprintf(stderr, "--spi-mode must be 0..3 and --spi-hz 10000..8000000\n");
		return 2;
	}
	if (!strcmp(cmd, "spi-check"))
		return spi_open() ? 1 : 0;
	if (!strcmp(cmd, "run")) {
		int exec = 0, approve = 0, ds_flag = 0, ds_approve = 0;

		for (int i = 2; i < argc; i++) {
			exec |= !strcmp(argv[i], "--execute");
			approve |= !strcmp(argv[i], "--approve-pmu-write");
			ds_flag |= !strcmp(argv[i], "--display-sync-pinmux");
			ds_approve |= !strcmp(argv[i], "--approve-display-sync-pinmux");
		}
		if (!exec || !approve) {
			fprintf(stderr, "run needs --execute and --approve-pmu-write; showing the plan only\n");
			plan();
			return 2;
		}
		if (ds_flag != ds_approve) {
			fprintf(stderr, "--display-sync-pinmux and --approve-display-sync-pinmux must be given together\n");
			return 2;
		}
		if (ds_flag && !g_spi_dev) {
			fprintf(stderr, "--display-sync-pinmux requires --spi-dev: it is only meaningful with the SPI frames\n");
			return 2;
		}
		if (g_fw_file || g_ack_file) {
			int up = 0;

			for (int i = 2; i < argc; i++)
				up |= !strcmp(argv[i], "--approve-firmware-upload");
			if (!g_fw_file || !g_ack_file || !g_spi_dev || !up) {
				fprintf(stderr, "firmware upload needs --spi-dev, --upload-fw, --upload-ack and --approve-firmware-upload\n");
				return 2;
			}
		}
		g_ds_pinmux = ds_flag;
		{
			int rc = run();

			return (!rc && g_restore_failed) ? 1 : rc;
		}
	}
	fprintf(stderr, "usage: touch-diag [plan|status|spi-check|run --execute --approve-pmu-write] [--spi-dev D --spi-mode M --spi-hz H] [--display-sync-pinmux --approve-display-sync-pinmux]\n");
	return 2;
}
