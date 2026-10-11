/*
 * uartpoke: read and write ONLY the three baud registers (+0x28, +0x34, +0x38) of the Bluetooth UART3 (0x20a0cc000, Linux ttySAC1) through /dev/mem.
 * Bring-up tool for the Apple uart-version-1 baud study (research/2026-10-11-uart-baud-register-semantics.md); the Bluetooth UART carries nothing but
 * Bluetooth, so the worst a wrong value does is a wrong baud rate on that UART.
 *
 *   uartpoke get                      print +0x28 +0x34 +0x38
 *   uartpoke set R28 R34 R38          write the three registers (hex or decimal), then print them
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define UART3_BASE 0x20a0cc000ULL
#define REG_BAUD0 0x28
#define REG_BAUD1 0x34
#define REG_BAUD2 0x38

int main(int argc, char **argv)
{
	int fd;
	void *m;
	volatile uint32_t *r;

	if (argc < 2 || (strcmp(argv[1], "get") != 0 && !(strcmp(argv[1], "set") == 0 && argc == 5))) {
		fprintf(stderr, "usage: %s get | set R28 R34 R38\n", argv[0]);
		return 1;
	}
	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) {
		perror("open /dev/mem");
		return 2;
	}
	m = mmap(NULL, 0x1000, PROT_READ | PROT_WRITE, MAP_SHARED, fd, UART3_BASE);
	if (m == MAP_FAILED) {
		perror("mmap");
		return 2;
	}
	r = (volatile uint32_t *)m;
	if (strcmp(argv[1], "set") == 0) {
		r[REG_BAUD0 / 4] = (uint32_t)strtoul(argv[2], NULL, 0);
		r[REG_BAUD1 / 4] = (uint32_t)strtoul(argv[3], NULL, 0);
		r[REG_BAUD2 / 4] = (uint32_t)strtoul(argv[4], NULL, 0);
	}
	printf("+0x28=0x%08x +0x34=0x%08x +0x38=0x%08x\n", r[REG_BAUD0 / 4], r[REG_BAUD1 / 4], r[REG_BAUD2 / 4]);
	return 0;
}
