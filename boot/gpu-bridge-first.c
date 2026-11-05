/* J81 first bridge write only; no readback and no automatic retry. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
int main(int argc, char **argv) {
 char reply[16]; uint32_t state; int fd, rc=1; void *gpc=MAP_FAILED,*bridge=MAP_FAILED;
 (void)argv;
 if (argc!=1 || mkdir("/tmp/gpu-bridge-first.once",0700)) return 2;
 fd=open("/dev/mem",O_RDWR|O_SYNC); if(fd<0)return 1;
 gpc=mmap(NULL,0x2000,PROT_READ,MAP_SHARED,fd,0x201e00000ULL);
 bridge=mmap(NULL,0x1000,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0x201f00000ULL);
 if(gpc==MAP_FAILED||bridge==MAP_FAILED)goto out;
 if(printf("stage=before-gpc-state address=0x201e01000 op=read value=0x00000000\n")<0||fflush(stdout)||!fgets(reply,sizeof(reply),stdin)||strcmp(reply,"ACCESS\n"))goto out;
 state=*(volatile const uint32_t *)((const char *)gpc+0x1000);
 if(printf("stage=after-gpc-state value=0x%08x\n",state)<0||fflush(stdout)||state!=0)goto out;
 if(printf("stage=before-bridge-first address=0x201f00018 op=write value=0x80010004\n")<0||fflush(stdout)||!fgets(reply,sizeof(reply),stdin)||strcmp(reply,"ACCESS\n"))goto out;
 *(volatile uint32_t *)((char *)bridge+0x18)=0x80010004; __sync_synchronize();
 if(printf("stage=after-bridge-first value=0x80010004\n")<0||fflush(stdout))goto out;
 rc=0;
out: printf("stage=finished rc=%d\n",rc); fflush(stdout);
 if(bridge!=MAP_FAILED)munmap(bridge,0x1000); if(gpc!=MAP_FAILED)munmap(gpc,0x2000); close(fd); return rc;
}
