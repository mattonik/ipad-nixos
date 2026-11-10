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
int main(void){*(uint64_t *)(test_buffer+3640)=(uint64_t)test_pmgr;*(uint32_t *)(test_buffer+3712)=1;test_store(fake_mmio,test_pmgr,0,0x5004,0,0x12345678);if(*(uint32_t *)(test_buffer+3744)!=1||*(uint32_t *)(test_buffer+3748)!=2||*(uint32_t *)(test_buffer+3752)!=0x12345678||*(uint32_t *)(test_buffer+3756)!=1)return puts("FAIL boundary race"),1;puts("PASS: boundary-crossing store recorded with distinct phases");return 0;}
