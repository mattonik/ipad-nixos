#include <stdint.h>
#include <stddef.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
int fake_open(const char *, int, ...);
ssize_t fake_read(int, void *, size_t);
int fake_close(int);
void *fake_mmap(void *, size_t, int, int, int, off_t);
int fake_munmap(void *, size_t);
int fake_mkdir(const char *, mode_t);
char *fake_fgets(char *, int, FILE *);
static uint32_t fake_read32(const void *p);
static void fake_write32(void *p, uint32_t v);
#define BRIDGE_READ32(p) fake_read32(p)
#define BRIDGE_WRITE32(p,v) fake_write32(p,v)
#define open fake_open
#define read fake_read
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define mkdir fake_mkdir
#define fgets fake_fgets
#define main bridge_main
#include "gpu-bridge-once.c"
#undef main
#include <assert.h>
#include <errno.h>
#include <string.h>
static uint32_t gpc[0x2000/4], fabric[0x101000/4];
static uint32_t *const banks[2] = {fabric, fabric + 0x80000/4};
static struct pair plan[2][33];
static int guard, writes, reads, acks, allow, plan_reads, fail_layout;
int fake_mkdir(const char *s, mode_t m) {assert(!strcmp(s,"/tmp/gpu-bridge-once.once") && m==0700);if(guard++){errno=EEXIST;return -1;}return 0;}
char *fake_fgets(char *s,int n,FILE *f) {(void)f;assert(n>=8);acks++;strcpy(s,acks<=allow?"ACCESS\n":"NO\n");return s;}
int fake_open(const char *s,int flags,...) {
 if(!strcmp(s,"/tmp/gfx-bridge-plan.bin")){assert((flags&O_ACCMODE)==O_RDONLY);return 8;}
 assert(!strcmp(s,"/dev/mem") && (flags&O_ACCMODE)==O_RDWR);return 7;
}
ssize_t fake_read(int fd,void *buf,size_t n) {
 assert(fd==8);if(plan_reads++)return 0;assert(n==sizeof(plan));memcpy(buf,plan,n);
 if(fail_layout)((struct pair *)buf)[10].offset=3;
 return n;
}
int fake_close(int fd){assert(fd==7 || fd==8);return 0;}
void *fake_mmap(void *a,size_t n,int prot,int flags,int fd,off_t off) {
 (void)a;assert(flags==MAP_SHARED && fd==7);
 if((uint64_t)off==0x201e00000ULL){assert(n==sizeof(gpc)&&prot==PROT_READ);return gpc;}
 assert(n==0x81000&&prot==PROT_WRITE);
 if((uint64_t)off==0x201f00000ULL)return banks[0];
 assert((uint64_t)off==0x201f80000ULL);return banks[1];
}
int fake_munmap(void *p,size_t n){assert((p==gpc&&n==sizeof(gpc))||((p==banks[0]||p==banks[1])&&n==0x81000));return 0;}
static uint32_t fake_read32(const void *p){assert(p==&gpc[0x1000/4]);reads++;return gpc[0x1000/4];}
static void fake_write32(void *p,uint32_t v){int t=writes/33,i=writes%33;assert(writes<66);assert(p==&banks[t][plan[t][i].offset/4]&&v==plan[t][i].value);*(uint32_t *)p=v;writes++;}
static void reset(void){guard=writes=reads=acks=plan_reads=fail_layout=0;allow=100;gpc[0x1000/4]=0;}
int main(void){char *args[]={"gpu-bridge-once","bad",0};int t,i;
 for(t=0;t<2;t++)for(i=0;i<33;i++){plan[t][i].offset=i?0x40000+(i-1)*4:0x18;plan[t][i].value=(t<<8)|i;}
 assert(bridge_main(2,args)==2 && !guard);
 reset();fail_layout=1;assert(bridge_main(1,args)==1 && !guard && !reads && !writes);
 reset();gpc[0x1000/4]=1;assert(bridge_main(1,args)==1 && reads==1 && !writes);
 reset();allow=3;assert(bridge_main(1,args)==1 && reads==1 && writes==2);
 assert(bridge_main(1,args)==1 && writes==2);
 reset();assert(bridge_main(1,args)==0 && reads==1 && writes==66 && acks==67);
 assert(&banks[0][0x80018/4] == &banks[1][0x18/4]);
 assert(banks[0][0x80018/4] == plan[1][0].value);
 return 0;
}
