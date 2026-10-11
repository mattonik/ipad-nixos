/*
 * uartpeek: READ-ONLY dump of the first 16 32-bit registers (offsets 0x00..0x3c) of an allow-listed T7001 UART block through /dev/mem. It cannot write: the
 * mapping is PROT_READ and the file is opened O_RDONLY. For the Bluetooth UART baud-register investigation (research/2026-10-11-research-agent-brief-uart-baud-registers.md).
 *
 *   uartpeek 3     UART3 at 0x20a0cc000 (Bluetooth, Linux ttySAC1)
 *   uartpeek 5     UART5 at 0x20a0d4000 (battery gauge HDQ, Linux ttySAC2)
 *   uartpeek pmgr  the PMGR clock-gate registers of gates 0x50..0x59 (UART0..UART9): 0x20e020000 + 0x20000 + gate*8 = 0x20e020280..0x20e0202cf, 8 bytes each
 *
 * Only these windows are accepted; reading any other address is refused (a read of an unmapped or powered-down block can hang the SoC).
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	uint64_t base;
	int fd, i;
	void *m;
	volatile uint32_t *r;

	if (argc != 2) {
		fprintf(stderr, "usage: %s 3|5|pmgr\n", argv[0]);
		return 1;
	}
	if (strcmp(argv[1], "pmgr") == 0) {
		fd = open("/dev/mem", O_RDONLY | O_SYNC);
		if (fd < 0) {
			perror("open /dev/mem");
			return 2;
		}
		m = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x20e020000ULL);
		if (m == MAP_FAILED) {
			perror("mmap");
			return 2;
		}
		r = (volatile uint32_t *)m;
		for (i = 0x50; i <= 0x59; i++)
			printf("gate 0x%02x (UART%d) @0x20e02%04x: 0x%08x 0x%08x\n", i, i - 0x50, 0x0 + i * 8, r[(i * 8) / 4], r[(i * 8) / 4 + 1]);
		return 0;
	}
	if (strcmp(argv[1], "3") == 0)
		base = 0x20a0cc000ULL;
	else if (strcmp(argv[1], "5") == 0)
		base = 0x20a0d4000ULL;
	else {
		fprintf(stderr, "only UART 3 and 5 are allowed\n");
		return 1;
	}
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		perror("open /dev/mem");
		return 2;
	}
	m = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, base);
	if (m == MAP_FAILED) {
		perror("mmap");
		return 2;
	}
	r = (volatile uint32_t *)m;
	printf("UART%s @ 0x%llx\n", argv[1], (unsigned long long)base);
	for (i = 0; i < 16; i++)
		printf("  +0x%02x = 0x%08x\n", i * 4, r[i]);
	return 0;
}
