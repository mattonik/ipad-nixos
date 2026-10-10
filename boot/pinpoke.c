/*
 * pinpoke: read the Apple GPIO pad register of one pin of the T7000/T7001 pinctrl block (0x20e300000) through /dev/mem, and (for ONE allow-listed pin only)
 * drive it. A bring-up tool for the iPad Air 2 Bluetooth BT_WAKE line (AP GPIO 164, ADT bluetooth node `function-bt_wake`); nothing else can be written.
 * Run only with the user's explicit approval (2026-10-10) on the running iPad; the test-only payload m1n1-hoolock-wifi-btwake does the same with a DT gpio-hog.
 *
 *   pinpoke read PIN                  print the 32-bit register of PIN (any pin 0..255)
 *   pinpoke high 164                  read-modify-write: PERIPH=0, MODE=OUT, DATA=1 (what the kernel's gpio direction_output(1) does); other bits kept
 *   pinpoke low 164                   same with DATA=0
 *   pinpoke restore 164 0xVALUE       write back a previously read register value (only for the allow-listed pin)
 *
 * Register layout (drivers/pinctrl/pinctrl-apple-gpio.c): reg = base + 4*pin; DATA bit 0, MODE bits 3:1 (1 = output), PERIPH bits 6:5, pull bits 8:7, input enable bit 9.
 * Writes are refused for every pin except WRITE_PIN, and `restore` refuses values that set the lock bit (bit 21) or a peripheral function.
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define PINCTRL_BASE 0x20e300000ULL
#define WRITE_PIN 164
#define REG_DATA (1u << 0)
#define REG_MODE_MASK (7u << 1)
#define REG_MODE_OUT (1u << 1)
#define REG_PERIPH_MASK (3u << 5)
#define REG_LOCK (1u << 21)

static volatile uint32_t *map_reg(int pin, int *fd, void **base)
{
	*fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (*fd < 0) {
		perror("open /dev/mem");
		exit(2);
	}
	*base = mmap(NULL, 0x1000, PROT_READ | PROT_WRITE, MAP_SHARED, *fd, PINCTRL_BASE);
	if (*base == MAP_FAILED) {
		perror("mmap");
		exit(2);
	}
	return (volatile uint32_t *)((char *)*base + 4 * pin);
}

int main(int argc, char **argv)
{
	int pin, fd;
	void *base;
	volatile uint32_t *reg;
	uint32_t v;

	if (argc < 3) {
		fprintf(stderr, "usage: %s read PIN | high 164 | low 164 | restore 164 0xVALUE\n", argv[0]);
		return 1;
	}
	pin = atoi(argv[2]);
	if (pin < 0 || pin > 255) {
		fprintf(stderr, "pin out of range\n");
		return 1;
	}
	if (strcmp(argv[1], "read") == 0) {
		reg = map_reg(pin, &fd, &base);
		printf("pin %d reg 0x%08x\n", pin, *reg);
		return 0;
	}
	if (pin != WRITE_PIN) {
		fprintf(stderr, "refusing to write pin %d (only %d is allowed)\n", pin, WRITE_PIN);
		return 1;
	}
	reg = map_reg(pin, &fd, &base);
	if (strcmp(argv[1], "high") == 0 || strcmp(argv[1], "low") == 0) {
		v = *reg;
		if (v & REG_LOCK) {
			fprintf(stderr, "pad is locked\n");
			return 1;
		}
		v &= ~(REG_PERIPH_MASK | REG_MODE_MASK | REG_DATA);
		v |= REG_MODE_OUT | (argv[1][0] == 'h' ? REG_DATA : 0);
		*reg = v;
	} else if (strcmp(argv[1], "restore") == 0 && argc == 4) {
		v = (uint32_t)strtoul(argv[3], NULL, 0);
		if ((v & REG_LOCK) || (v & REG_PERIPH_MASK)) {
			fprintf(stderr, "refusing a value that sets the lock bit or a peripheral function\n");
			return 1;
		}
		*reg = v;
	} else {
		fprintf(stderr, "bad command\n");
		return 1;
	}
	printf("pin %d reg now 0x%08x\n", pin, *reg);
	return 0;
}
