/* Feed only after a completed diagnostic stage receives a host acknowledgement. */
#include <fcntl.h>
#include <linux/watchdog.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

static void fail_closed(void) { for (;;) pause(); }

static void simulated_child(int stalled)
{
	char reply[16];
	puts("stage=before-sim address=0x0 op=read value=0x00000000"); fflush(stdout);
	if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, "ACCESS\n")) _exit(1);
	puts("stage=after-sim value=0x00000000"); fflush(stdout);
	if (stalled) for (;;) pause();
	puts("stage=finished rc=0"); fflush(stdout);
	_exit(0);
}

int main(int argc, char **argv)
{
	int fd, timeout = 20, disable = WDIOS_DISABLECARD, pin[2], pout[2], status, n = 0, saw_finish = 0;
	int simulation, stalled, bridge_sim = 0, bridge_peek = 0, bridge_first = 0, bridge_segment = 0;
	int bridge_cycle = 0, gpc_init_cycle = 0, postgpc_cycle = 0;
	int core_revision_cycle = 0, mcc_read_once = 0, page5_read_once = 0, gpc_page5_timed = 0, gpc_page5_kpoll = 0;
	pid_t child;
	FILE *in, *out;
	char line[512], reply[128], expected[64];
	struct watchdog_info info;
	if (argc == 2 && (!strcmp(argv[1], "--simulate-ok") || !strcmp(argv[1], "--simulate-stall"))) {
		simulation = 1; stalled = !strcmp(argv[1], "--simulate-stall");
	} else if (argc == 6 && !strcmp(argv[1], "--page5-read-once") && strlen(argv[2]) == 64 && strspn(argv[2], "0123456789abcdef") == 64 && strlen(argv[3]) == 64 && strspn(argv[3], "0123456789abcdef") == 64 && strlen(argv[4]) == 36 && (!strcmp(argv[5], "0") || !strcmp(argv[5], "4") || !strcmp(argv[5], "8"))) {
		simulation = stalled = 0; page5_read_once = 1;
	} else if (argc == 4 && !strcmp(argv[1], "--gpc-page5-timed") && strlen(argv[2]) == 64 && strspn(argv[2], "0123456789abcdef") == 64 && strlen(argv[3]) == 36 && strspn(argv[3], "0123456789abcdef-") == 36) {
		simulation = stalled = 0; gpc_page5_timed = 1;
	} else if (argc == 5 && !strcmp(argv[1], "--gpc-page5-kpoll") && strlen(argv[2]) == 64 && strspn(argv[2], "0123456789abcdef") == 64 && strlen(argv[3]) == 36 && strspn(argv[3], "0123456789abcdef-") == 36 && (!strcmp(argv[4], "immediate") || !strcmp(argv[4], "paired") || !strcmp(argv[4], "delayed"))) {
		simulation = stalled = 0; gpc_page5_kpoll = 1;
	} else if (argc == 5 && !strcmp(argv[1], "--mcc-read-once") && strlen(argv[2]) == 64 && strspn(argv[2], "0123456789abcdef") == 64 && strlen(argv[3]) == 64 && strspn(argv[3], "0123456789abcdef") == 64 && strlen(argv[4]) == 36) {
		simulation = stalled = 0; mcc_read_once = 1;
	} else if (argc == 3 && (!strcmp(argv[1], "--bridge") || !strcmp(argv[1], "--simulate-bridge") || !strcmp(argv[1], "--bridge-peek") || !strcmp(argv[1], "--bridge-first") || !strcmp(argv[1], "--bridge-segment") || !strcmp(argv[1], "--bridge-cycle") || !strcmp(argv[1], "--gpc-init-cycle") || !strcmp(argv[1], "--postgpc-cycle") || !strcmp(argv[1], "--core-revision-cycle")) && strlen(argv[2]) == 64 &&
	           strspn(argv[2], "0123456789abcdef") == 64) {
		simulation = stalled = 0; bridge_sim = !strcmp(argv[1], "--simulate-bridge");
		bridge_peek = !strcmp(argv[1], "--bridge-peek");
		bridge_first = !strcmp(argv[1], "--bridge-first");
		bridge_segment = !strcmp(argv[1], "--bridge-segment");
		bridge_cycle = !strcmp(argv[1], "--bridge-cycle");
		gpc_init_cycle = !strcmp(argv[1], "--gpc-init-cycle");
		postgpc_cycle = !strcmp(argv[1], "--postgpc-cycle");
		core_revision_cycle = !strcmp(argv[1], "--core-revision-cycle");
	} else return 2;
	if (pipe(pin) || pipe(pout)) return 1;
	if (puts("stage=before-watchdog-open") == EOF || fflush(stdout) ||
	    !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "ARM\n")) return 1;
	fd = open("/dev/watchdog0", O_WRONLY | O_CLOEXEC);
	if (fd < 0) { perror("watchdog open"); return 1; }
	memset(&info, 0, sizeof(info));
	if (ioctl(fd, WDIOC_GETSUPPORT, &info) || !(info.options & WDIOF_MAGICCLOSE) ||
	    ioctl(fd, WDIOC_SETTIMEOUT, &timeout) || timeout != 20) {
		if (write(fd, "V", 1) != 1) perror("watchdog disarm");
		close(fd); return 1;
	}
	/* A lost host must not terminate the process and silently close the watchdog. */
	signal(SIGHUP, SIG_IGN); signal(SIGTERM, SIG_IGN); signal(SIGPIPE, SIG_IGN);
	if (puts("stage=watchdog-armed timeout=20") == EOF || fflush(stdout)) fail_closed();
	child = fork();
	if (child < 0) fail_closed();
	if (child == 0) {
		close(fd); close(pin[1]); close(pout[0]);
		if (dup2(pin[0], STDIN_FILENO) < 0 || dup2(pout[1], STDOUT_FILENO) < 0) _exit(1);
		close(pin[0]); close(pout[1]);
		if (simulation) simulated_child(stalled);
		if (page5_read_once)
			execl("/tmp/j81-page5-read-once-run", "j81-page5-read-once-run", "--run", argv[2], argv[3], argv[4], argv[5], (char *)NULL);
		else if (mcc_read_once)
			execl("/tmp/j81-mcc-read-once-run", "j81-mcc-read-once-run", "--run", argv[2], argv[3], argv[4], (char *)NULL);
		else if (bridge_peek)
			execl("/tmp/gpu-bridge-peek-run", "gpu-bridge-peek-run", argv[2], (char *)NULL);
		else if (bridge_first)
			execl("/tmp/gpu-bridge-first-run", "gpu-bridge-first-run", argv[2], (char *)NULL);
		else if (bridge_segment)
			execl("/tmp/gpu-bridge-segment-run", "gpu-bridge-segment-run", argv[2], (char *)NULL);
		else if (bridge_cycle)
			execl("/tmp/gpu-bridge-once-cycle-run", "gpu-bridge-once-cycle-run", argv[2], (char *)NULL);
		else if (gpc_page5_kpoll)
			execl("/tmp/gpu-gpc-page5-kpoll-run", "gpu-gpc-page5-kpoll-run", argv[2], argv[3], argv[4], (char *)NULL);
		else if (gpc_page5_timed)
			execl("/tmp/gpu-gpc-page5-timed-run", "gpu-gpc-page5-timed-run", argv[2], argv[3], (char *)NULL);
		else if (gpc_init_cycle)
			execl("/tmp/gpu-gpc-init-cycle-run", "gpu-gpc-init-cycle-run", argv[2], (char *)NULL);
		else if (postgpc_cycle)
			execl("/tmp/gpu-bridge-postgpc-cycle-run", "gpu-bridge-postgpc-cycle-run", argv[2], (char *)NULL);
		else if (core_revision_cycle)
			execl("/tmp/gpu-core-revision-once-cycle-run", "gpu-core-revision-once-cycle-run", argv[2], (char *)NULL);
		else if (bridge_sim)
			execl("/tmp/gpu-bridge-sim-live-run", "gpu-bridge-sim-live-run", argv[2], (char *)NULL);
		else
			execl("/tmp/gpu-bridge-once-run", "gpu-bridge-once-run", argv[2], (char *)NULL);
		_exit(1);
	}
	close(pin[0]); close(pout[1]);
	in = fdopen(pin[1], "w"); out = fdopen(pout[0], "r");
	if (!in || !out) fail_closed();
	while (fgets(line, sizeof(line), out)) {
		if (!strchr(line, '\n') || fputs(line, stdout) == EOF || fflush(stdout)) fail_closed();
		if (!strncmp(line, "stage=before-", 13)) {
			const char *ack = (!strncmp(line, "stage=before-pmgr-read ", 23) || !strncmp(line, "stage=before-mcc-read ", 22) || strstr(line, " width=32")) ? "READ\n" : "ACCESS\n";
			if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, ack) ||
			    fputs(ack, in) == EOF || fflush(in)) fail_closed();
		} else if (!strncmp(line, "stage=after-", 12)) {
			snprintf(expected, sizeof(expected), "FEED %d\n", ++n);
			if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, expected) ||
			    ioctl(fd, WDIOC_KEEPALIVE, 0)) fail_closed();
		} else if (!strcmp(line, "stage=finished rc=0\n")) {
			saw_finish = 1;
		} else if (!strncmp(line, "stage=finished", 14)) fail_closed();
	}
	if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status) || !saw_finish || n == 0)
		fail_closed();
	if (ioctl(fd, WDIOC_SETOPTIONS, &disable) || write(fd, "V", 1) != 1 || close(fd)) fail_closed();
	puts("stage=watchdog-disarmed");
	return 0;
}
