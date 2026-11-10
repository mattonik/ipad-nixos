#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
uint64_t test_thread=0x1234, test_pmgr[1], test_vtable[400];
unsigned char test_buffer[4096] __attribute__((aligned(16)));
const char test_format[]="test %s";
static char lines[16][256];static unsigned count,reads;
void fake_logger(const char*f,...){(void)f;va_list v;va_start(v,f);const char*s=va_arg(v,const char*);if(count<16)snprintf(lines[count++],256,"%s",s);va_end(v);}
void fake_inner(void*p,unsigned a,unsigned b,unsigned c,unsigned d){(void)p;(void)a;(void)b;(void)c;(void)d;}
uint64_t fake_read(void*self,unsigned reg,unsigned off,unsigned instance){if(self!=test_pmgr||reg||off!=0x5004||instance)return 0xbad;++reads; return reads==1?0:0x40000000;}
uint64_t fake_other(void *p,unsigned a,unsigned b,unsigned c){(void)p;(void)a;(void)b;(void)c;return 0;}
uint64_t fake_power(void){return 0x9876;}
extern uint64_t test_power(void),test_control(void);
extern void test_store(void *,void *,unsigned,unsigned,unsigned,unsigned);
static unsigned char fake_mmio[0x6000];
extern uint64_t test_pm(unsigned,unsigned,unsigned,unsigned),test_gpc(unsigned),test_entry(unsigned char*);extern void test_identity(unsigned,unsigned);
uint64_t fake_provider(void*p){(void)p;test_pm(0x3ff,0,0x20320,0);return 0x1234;}

#include <pthread.h>
static unsigned char maps[4][0x6000];
static void *worker(void *arg) {
 unsigned i=(unsigned)(uintptr_t)arg;
 for(unsigned n=0;n<12;n++)test_store(maps[i],test_pmgr,0,0x5004,0,0x100+i);
 return 0;
}
int main(void) {
 pthread_t threads[4];
 *(uint64_t *)(test_buffer+3640)=(uint64_t)test_pmgr;
 test_store(fake_mmio,test_pmgr,1,0x5004,0,0x11111111);
 if(*(uint32_t *)(fake_mmio+0x5004)!=0x11111111 || *(uint32_t *)(test_buffer+3720)!=0) return puts("FAIL mismatch"),1;
 *(uint32_t *)(test_buffer+3712)=1;
 for(unsigned i=0;i<4;i++)if(pthread_create(&threads[i],0,worker,(void *)(uintptr_t)i))return 2;
 for(unsigned i=0;i<4;i++)pthread_join(threads[i],0);
 unsigned count=*(uint32_t *)(test_buffer+3720);
 if(count>16 || !count || *(uint32_t *)(test_buffer+3724)!=1 || *(uint32_t *)(test_buffer+3716)!=1)return puts("FAIL count/overflow"),1;
 for(unsigned i=0;i<count;i++) {
  unsigned char *p=test_buffer+3744+i*16;
  if(*(uint32_t *)(p+12)!=1 || *(uint32_t *)p!=1 || *(uint32_t *)(p+4)!=1 || *(uint32_t *)(p+8)<0x100 || *(uint32_t *)(p+8)>0x103)return puts("FAIL publication"),1;
 }
 for(unsigned i=0;i<4;i++)if(*(uint32_t *)(maps[i]+0x5004)!=0x100+i)return puts("FAIL displaced store"),1;
 puts("PASS: mismatch store, concurrent reservations, overflow and publication"); return 0;
}
