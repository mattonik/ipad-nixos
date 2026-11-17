/* J81 known GPC setup followed by read-only Fender/page-5 status capture. */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define FENDER_BASE 0x201e00000ULL
#define FENDER_SIZE 0x21000

static int capture(void *base, int page5_fd)
{
	volatile uint32_t *r = base;
	uint32_t state, control, settle, hold, page5;
	unsigned i;
	char result[128], tail;
	ssize_t n;
	struct timespec delay;

	if (puts("checkpoint=before-gpc-writes") == EOF || fflush(stdout)) return 1;
	r[0x10000 / 4] = 0xffff0000; __sync_synchronize();
	r[0] = 0x40000000; __sync_synchronize();
	r[0x1000 / 4] = 0x11; __sync_synchronize();
	if (puts("checkpoint=before-gpc-poll") == EOF || fflush(stdout)) return 1;
	for (i = 0; i < 1000; i++) {
		state = r[0x1000 / 4]; __sync_synchronize();
		if (!(state & 0x10)) break;
		delay = (struct timespec){0, 10000};
		while (nanosleep(&delay, &delay) && errno == EINTR) {}
	}
	if (i == 1000 || (state & 0x1f) != 1) {
		printf("checkpoint=gpc-poll-failed raw=0x%08x polls=%u\n", state, i == 1000 ? i : i + 1);
		return 1;
	}
	control = r[0];
	settle = r[0x8 / 4];
	state = r[0x1000 / 4];
	hold = r[0x20000 / 4];
	n = read(page5_fd, result, sizeof(result) - 1);
	if (n <= 0) return 1;
	result[n] = 0;
	if (sscanf(result, "address=0x20e005004 value=0x%8x%c", &page5, &tail) != 2 || tail != '\n') return 1;
	if (printf("checkpoint=gpc-poll-ok raw=0x%08x polls=%u\n", state, i + 1) < 0 ||
	    printf("stage=after-gpc-fender control=0x%08x settle=0x%08x state=0x%08x hold=0x%08x page5=0x%08x\n",
		   control, settle, state, hold, page5) < 0 || fflush(stdout)) return 1;
	return 0;
}

int main(int argc, char **argv)
{
	void *fender = MAP_FAILED;
	uint32_t initial;
	int mem = -1, page5 = -1, rc = 1;
	char reply[16];
	(void)argv;
	if (argc != 1 || mkdir("/tmp/gpu-gpc-fender-status.once", 0700)) return 2;
	mem = open("/dev/mem", O_RDWR | O_SYNC);
	page5 = open("/sys/devices/j81-page5-read-once/read_once", O_RDONLY | O_CLOEXEC);
	if (mem < 0 || page5 < 0) goto out;
	fender = mmap(NULL, FENDER_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, mem, FENDER_BASE);
	if (fender == MAP_FAILED) goto out;
	if (puts("stage=before-gpc-state address=0x201e01000 width=32") == EOF || fflush(stdout) ||
	    !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n")) goto out;
	initial = *(volatile uint32_t *)((char *)fender + 0x1000); __sync_synchronize();
	if (printf("stage=after-gpc-state raw=0x%08x\n", initial) < 0 || fflush(stdout) || initial != 0) goto out;
	if (puts("stage=before-gpc-fender address=0x201e00000 width=32") == EOF || fflush(stdout) ||
	    !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n")) goto out;
	rc = capture(fender, page5);
out:
	printf("stage=finished rc=%d\n", rc); fflush(stdout);
	if (fender != MAP_FAILED) munmap(fender, FENDER_SIZE);
	if (page5 >= 0) close(page5);
	if (mem >= 0) close(mem);
	return rc;
}
