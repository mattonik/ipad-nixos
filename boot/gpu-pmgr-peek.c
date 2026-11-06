/* Read only the J81 GFX PMGR state word; never access the GPU or Fender. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	int fd;
	void *map;
	uint32_t value;
	char reply[16];

	(void)argv;
	if (argc != 1) {
		fprintf(stderr, "usage: gpu-pmgr-peek\n");
		return 2;
	}
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	map = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x20e020000ULL);
	if (map == MAP_FAILED) {
		perror("mmap PMGR");
		close(fd);
		return 1;
	}
	if (puts("stage=before-pmgr-read address=0x20e020320 width=32") == EOF ||
	    fflush(stdout) == EOF) {
		munmap(map, 0x1000);
		close(fd);
		return 1;
	}
	if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n") != 0) {
		munmap(map, 0x1000);
		close(fd);
		return 1;
	}
	value = *(volatile const uint32_t *)((const char *)map + 0x320);
	printf("stage=after-pmgr-read raw=0x%08x target=%u actual=%u auto=%u reset=%u\n",
	       value, value & 0xf, (value >> 4) & 0xf,
	       (value >> 28) & 1, value >> 31);
	munmap(map, 0x1000);
	close(fd);
	return 0;
}
