/*
 * hciscan: bring hciN up and COUNT nearby Bluetooth devices, without BlueZ userland (the W1 NixOS payload has none).
 *
 *   hciscan <dev-id> <seconds>
 *
 * Classic: one HCIINQUIRY ioctl (length = seconds / 1.28). LE: passive scan on a raw HCI socket for <seconds>, unique
 * advertisers counted in memory. Prints only counts; addresses and names are never printed or stored past the run.
 * Run-time bring-up tool only, pushed to the iPad (research/2026-11-02-bt-uart3-pinmux-lead.md).
 */
#include <errno.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define AF_BT 31
#define BTPROTO_HCI 1
#define SOL_HCI 0
#define HCI_FILTER 2
#define HCIDEVUP _IOW('H', 201, int)
#define HCIINQUIRY _IOR('H', 240, int)

struct sockaddr_hci { sa_family_t family; uint16_t dev; uint16_t channel; };
struct hci_filter { uint32_t type_mask; uint32_t event_mask[2]; uint16_t opcode; };
struct inq_req { uint16_t dev_id; uint16_t flags; uint8_t lap[3]; uint8_t length; uint8_t num_rsp; } __attribute__((packed));

#define MAX_LE 1024
static uint8_t seen[MAX_LE][7];
static int nseen;

static void note(const uint8_t *addr, uint8_t type)
{
	for (int i = 0; i < nseen; i++)
		if (seen[i][6] == type && !memcmp(seen[i], addr, 6))
			return;
	if (nseen < MAX_LE) {
		memcpy(seen[nseen], addr, 6);
		seen[nseen++][6] = type;
	}
}

static int cmd(int s, uint16_t opcode, const uint8_t *p, uint8_t len)
{
	uint8_t buf[260] = { 0x01, opcode & 0xff, opcode >> 8, len };
	memcpy(buf + 4, p, len);
	return write(s, buf, 4 + len) == 4 + len ? 0 : -1;
}

int main(int argc, char **argv)
{
	if (argc != 3) {
		fprintf(stderr, "usage: hciscan <dev-id> <seconds>\n");
		return 2;
	}
	int dev = atoi(argv[1]), secs = atoi(argv[2]);
	int ctl = socket(AF_BT, SOCK_RAW, BTPROTO_HCI);
	if (ctl < 0) { perror("socket"); return 1; }
	if (ioctl(ctl, HCIDEVUP, dev) < 0 && errno != EALREADY) { perror("HCIDEVUP"); return 1; }
	printf("hci%d up\n", dev);

	struct { struct inq_req r; uint8_t info[255 * 14]; } iq = { 0 };
	iq.r.dev_id = dev;
	iq.r.flags = 1; /* IREQ_CACHE_FLUSH */
	memcpy(iq.r.lap, "\x33\x8b\x9e", 3); /* GIAC */
	iq.r.length = (uint8_t)(secs * 100 / 128 ? secs * 100 / 128 : 1);
	iq.r.num_rsp = 255;
	if (ioctl(ctl, HCIINQUIRY, &iq) < 0)
		perror("HCIINQUIRY");
	else
		printf("classic inquiry: %d device(s)\n", iq.r.num_rsp);

	int s = socket(AF_BT, SOCK_RAW, BTPROTO_HCI);
	struct sockaddr_hci a = { AF_BT, dev, 0 };
	if (s < 0 || bind(s, (struct sockaddr *)&a, sizeof(a)) < 0) { perror("bind"); return 1; }
	struct hci_filter f = { 1 << 4 /* event packets */, { 0xffffffff, 0xffffffff }, 0 };
	setsockopt(s, SOL_HCI, HCI_FILTER, &f, sizeof(f));
	const uint8_t params[7] = { 0x00, 0x10, 0x00, 0x10, 0x00, 0x00, 0x00 }; /* passive, 10 ms/10 ms, public, accept all */
	const uint8_t on[2] = { 0x01, 0x00 }, off[2] = { 0x00, 0x00 };
	if (cmd(s, 0x200b, params, 7) < 0 || cmd(s, 0x200c, on, 2) < 0) { perror("LE scan"); return 1; }
	time_t end = time(NULL) + secs;
	uint8_t buf[260];
	while (time(NULL) < end) {
		struct pollfd p = { s, POLLIN, 0 };
		if (poll(&p, 1, 500) <= 0)
			continue;
		ssize_t n = read(s, buf, sizeof(buf));
		if (n < 5 || buf[0] != 0x04 || buf[1] != 0x3e || buf[3] != 0x02)
			continue;
		int k = 5;
		for (int r = 0; r < buf[4] && k + 9 <= n; r++) {
			note(buf + k + 2, buf[k + 1]);
			k += 9 + buf[k + 8] + 1;
		}
	}
	cmd(s, 0x200c, off, 2);
	printf("LE passive scan %d s: %d advertiser(s)\n", secs, nseen);
	memset(seen, 0, sizeof(seen));
	return 0;
}
