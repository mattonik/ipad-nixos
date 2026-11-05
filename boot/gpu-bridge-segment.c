/* J81 selector-9 setup plus four table entries; one shot, no retry. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
struct w{uint32_t off,val;}; static const struct w ws[]={{0x18,0x80010004},{0x40000,0x7c7c01},{0x40004,0x7c7c01},{0x40008,0x7c7c01},{0x4000c,0x7c7901}};
int main(int c,char**v){char r[16],n[32];uint32_t s;int f,x=1;void*g=MAP_FAILED,*b=MAP_FAILED;size_t i;(void)v;if(c!=1||mkdir("/tmp/gpu-bridge-segment.once",0700))return 2;f=open("/dev/mem",O_RDWR|O_SYNC);if(f<0)return 1;g=mmap(0,0x2000,PROT_READ,MAP_SHARED,f,0x201e00000ULL);b=mmap(0,0x50000,PROT_READ|PROT_WRITE,MAP_SHARED,f,0x201f00000ULL);if(g==MAP_FAILED||b==MAP_FAILED)goto o;if(printf("stage=before-gpc-state address=0x201e01000 op=read value=0x00000000\n")<0||fflush(stdout)||!fgets(r,16,stdin)||strcmp(r,"ACCESS\n"))goto o;s=*(volatile const uint32_t*)((char*)g+0x1000);if(printf("stage=after-gpc-state value=0x%08x\n",s)<0||fflush(stdout)||s)goto o;for(i=0;i<5;i++){snprintf(n,32,"bridge-segment-%02zu",i);if(printf("stage=before-%s address=0x%llx op=write value=0x%08x\n",n,0x201f00000ULL+ws[i].off,ws[i].val)<0||fflush(stdout)||!fgets(r,16,stdin)||strcmp(r,"ACCESS\n"))goto o;*(volatile uint32_t*)((char*)b+ws[i].off)=ws[i].val;__sync_synchronize();if(printf("stage=after-%s value=0x%08x\n",n,ws[i].val)<0||fflush(stdout))goto o;}x=0;o:printf("stage=finished rc=%d\n",x);fflush(stdout);if(b!=MAP_FAILED)munmap(b,0x50000);if(g!=MAP_FAILED)munmap(g,0x2000);close(f);return x;}
