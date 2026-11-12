#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
uint64_t test_thread=0x1234, test_pmgr[1], test_vtable[400];
unsigned char test_buffer[4096] __attribute__((aligned(16)));
const char test_format[]="test %s";
static char lines[32][256];static unsigned count,reads;
void fake_logger(const char*f,...){(void)f;va_list v;va_start(v,f);const char*s=va_arg(v,const char*);if(count<32)snprintf(lines[count++],256,"%s",s);va_end(v);}
void fake_inner(void*p,unsigned a,unsigned b,unsigned c,unsigned d){(void)p;(void)a;(void)b;(void)c;(void)d;}
extern uint32_t test_readsite(void*,void*,unsigned,unsigned,unsigned);
static unsigned char fake_mmio[0x6000] __attribute__((aligned(16)));
uint64_t fake_read(void*self,unsigned reg,unsigned off,unsigned instance){if(self!=test_pmgr||reg||off!=0x5004||instance)return 0xbad;++reads; *(uint32_t *)(fake_mmio+0x5004)=reads==1?0:0x40000000; return test_readsite(fake_mmio,self,off,reg,instance);}
uint64_t fake_other(void *p,unsigned a,unsigned b,unsigned c){(void)p;(void)a;(void)b;(void)c;return 0;}
uint64_t fake_power(void){return 0x9876;}
extern uint64_t test_power(void),test_control(void);
extern void test_store(void *,void *,unsigned,unsigned,unsigned,unsigned);

extern uint64_t test_pm(unsigned,unsigned,unsigned,unsigned),test_gpc(unsigned),test_entry(unsigned char*);extern void test_identity(unsigned,unsigned);
uint64_t fake_provider(void*p){(void)p;test_pm(0x3ff,0,0x20320,0);return 0x1234;}
int main(void) {
 *(uint32_t *)(test_buffer+3720)=1; /* A reserved but unpublished event. */
 *(uint32_t *)(test_buffer+4008)=2; /* Two writers remain in flight. */
 test_identity(0x00070500, 0x011b0803);
 int unready=0, inflight=0;
 for (unsigned i=0;i<count;i++) {
  unready |= !strcmp(lines[i], "W=UNREADY");
  inflight |= !strcmp(lines[i], "Y=00000000:00000000:00000000:00000000:00000000:00000000:00000002:00000000:00000000:00000000");
 }
 if (!unready || !inflight) return puts("FAIL: missing incomplete or in-flight marker"),1;
 puts("PASS: incomplete publication and in-flight state are reported");
 return 0;
}
