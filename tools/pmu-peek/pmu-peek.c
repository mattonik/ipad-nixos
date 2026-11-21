/*
 * Read-only sample of D2207 PMU rows on I2C bus 0 (address 0x3c), the same transaction as
 * `i2ctransfer -f -y 0 w2@0x3c <hi> <lo> r8`, for a kernel userland that has no i2c-tools.
 * Usage: pmu-peek <row-hex>...   (row = 16-bit register, 4 hex digits, at most 8 rows)
 * Output: one line per row, "rowXXXX 0x.. 0x.. 0x.. 0x.. 0x.. 0x.. 0x.. 0x..", or "rowXXXX error <errno>".
 * Never writes a PMU register: the only write is the two address bytes of the combined read.
 * Constants are defined locally so no kernel headers are needed.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define I2C_RDWR 0x0707
#define I2C_M_RD 0x0001
#define PMU_ADDR 0x3c
#define MAX_ROWS 8

struct msg { uint16_t addr, flags, len; uint8_t *buf; };
struct rdwr { struct msg *msgs; uint32_t nmsgs; };

int main(int argc, char **argv)
{
	int fd, i, k, rc = 0;

	if (argc < 2 || argc - 1 > MAX_ROWS) {
		fprintf(stderr, "usage: pmu-peek <row-hex>... (1..%d)\n", MAX_ROWS);
		return 2;
	}
	fd = open("/dev/i2c-0", O_RDWR);
	if (fd < 0) {
		printf("pmu-peek open-error %d\n", errno);
		return 1;
	}
	for (i = 1; i < argc; i++) {
		char *end;
		unsigned long row;
		uint8_t out[2], in[8];
		struct msg m[2];
		struct rdwr r;

		errno = 0;
		row = strtoul(argv[i], &end, 16);
		if (errno || end == argv[i] || *end || row > 0xffff) {
			printf("row%s bad-argument\n", argv[i]);
			rc = 2;
			continue;
		}
		out[0] = row >> 8;
		out[1] = row & 0xff;
		memset(in, 0, sizeof(in));
		m[0] = (struct msg){ PMU_ADDR, 0, 2, out };
		m[1] = (struct msg){ PMU_ADDR, I2C_M_RD, 8, in };
		r.msgs = m;
		r.nmsgs = 2;
		if (ioctl(fd, I2C_RDWR, &r) < 0) {
			printf("row%04lx error %d\n", row, errno);
			rc = 1;
			continue;
		}
		printf("row%04lx", row);
		for (k = 0; k < 8; k++)
			printf(" 0x%02x", in[k]);
		printf("\n");
	}
	close(fd);
	return rc;
}
