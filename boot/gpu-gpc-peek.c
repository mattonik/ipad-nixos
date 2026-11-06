/* Read only the GPC state and handshake; an acknowledged read can still hang. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static int read_word(const void *map, unsigned offset, const char *name, uint32_t *result)
{
	char reply[16];
	uint32_t value;

	if (printf("stage=before-%s address=0x%llx width=32\n", name,
	           0x201e00000ULL + offset) < 0 || fflush(stdout) == EOF)
		return 1;
	if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n") != 0)
		return 1;
	value = *(volatile const uint32_t *)((const char *)map + offset);
	if (printf("stage=after-%s raw=0x%08x\n", name, value) < 0 ||
	    fflush(stdout) == EOF)
		return 1;
	*result = value;
	return 0;
}

int main(int argc, char **argv)
{
	int fd, rc, map_only;
	uint32_t state, control;
	void *map;

	map_only = argc == 2 && strcmp(argv[1], "--map-only") == 0;
	if (argc != 1 && !map_only) {
		fprintf(stderr, "usage: gpu-gpc-peek [--map-only]\n");
		return 2;
	}
	if (!map_only && mkdir("/tmp/gpu-gpc-peek.once", 0700) != 0) {
		perror("one-shot guard");
		return 1;
	}
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	map = mmap(NULL, 0x2000, PROT_READ, MAP_SHARED, fd, 0x201e00000ULL);
	if (map == MAP_FAILED) {
		perror("mmap GPC");
		close(fd);
		return 1;
	}
	if (map_only) {
		puts("stage=gpc-mapped-no-access");
		munmap(map, 0x2000);
		close(fd);
		return 0;
	}
	rc = read_word(map, 0x1000, "gpc-state", &state);
	if (!rc && (state & 0x1f) != 1) {
		puts("stage=blocked-gpc-state");
		rc = 1;
	}
	if (!rc)
		rc = read_word(map, 0, "gpc-control", &control);
	munmap(map, 0x2000);
	close(fd);
	return rc;
}
