/* RAM-boot recovery check: --expire deliberately requests a watchdog reboot. */
#include <errno.h>
#include <fcntl.h>
#include <linux/watchdog.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	char reply[16];
	int fd, timeout = 20, expire;
	struct watchdog_info info;
	if (argc != 2 || (strcmp(argv[1], "--check") && strcmp(argv[1], "--expire"))) return 2;
	expire = !strcmp(argv[1], "--expire");
	if (printf("stage=before-watchdog-open mode=%s\n", expire ? "expire" : "check") < 0 ||
	    fflush(stdout) || !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "ARM\n")) return 1;
	fd = open("/dev/watchdog0", O_WRONLY | O_CLOEXEC);
	if (fd < 0) { perror("open watchdog"); return 1; }
	memset(&info, 0, sizeof(info));
	if (ioctl(fd, WDIOC_GETSUPPORT, &info) || !(info.options & WDIOF_MAGICCLOSE) ||
	    ioctl(fd, WDIOC_SETTIMEOUT, &timeout) || timeout < 10 || timeout > 30) {
		perror("watchdog preflight");
		if (write(fd, "V", 1) != 1) perror("watchdog disarm");
		close(fd);
		return 1;
	}
	if (!expire) {
		if (write(fd, "V", 1) != 1) { perror("watchdog disarm"); close(fd); return 1; }
		if (close(fd)) { perror("close watchdog"); return 1; }
		printf("stage=watchdog-check-closed timeout=%d\n", timeout);
		return 0;
	}
	printf("stage=watchdog-armed timeout=%d expecting-reset\n", timeout);
	fflush(stdout);
	for (;;) pause();
}
