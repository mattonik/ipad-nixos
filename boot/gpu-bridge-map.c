/* Map the J81 bridge windows without loading or storing device registers. */
#include <fcntl.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	const off_t bases[] = { 0x201f00000ULL, 0x201f80000ULL };
	void *maps[2] = { MAP_FAILED, MAP_FAILED };
	int fd, i, rc = 1;
	(void)argv;
	if (argc != 1) return 2;
	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) { perror("open /dev/mem"); return 1; }
	for (i = 0; i < 2; i++) {
		maps[i] = mmap(NULL, 0x81000, PROT_WRITE, MAP_SHARED, fd, bases[i]);
		if (maps[i] == MAP_FAILED) { perror("mmap bridge"); goto out; }
	}
	puts("stage=bridge-windows-mapped-no-access");
	rc = 0;
 out:
	for (i = 0; i < 2; i++) if (maps[i] != MAP_FAILED) munmap(maps[i], 0x81000);
	close(fd);
	return rc;
}
