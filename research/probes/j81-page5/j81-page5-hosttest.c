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
uint64_t fake_read(void*self,unsigned reg,unsigned off,unsigned instance){if(self!=test_pmgr||reg||off!=(0x5000+J81_PAGE5_OFFSET)||instance)return 0xbad;reads++;return 0x12ab34cd;}
extern uint64_t test_pm(unsigned,unsigned,unsigned,unsigned),test_gpc(unsigned),test_entry(unsigned char*);extern void test_identity(unsigned,unsigned);
uint64_t fake_provider(void*p){(void)p;test_pm(0x3ff,0,0x20320,0);test_gpc(1);test_identity(0x00070500,0x011b0803);test_identity(0x00070500,0x011b0803);return 0x1234;}
int main(void){unsigned char v[32];test_vtable[0x980/8]=(uint64_t)fake_read;test_pmgr[0]=(uint64_t)test_vtable;test_buffer[0]=1;uint64_t x=test_entry(v);int before=0,after=0;for(unsigned i=0;i<count;i++){before+=!strcmp(lines[i],"PAGE5-before");after+=!strcmp(lines[i],"Q=12ab34cd");}if(x!=0x1234||before!=1||after!=1||reads!=1)return printf("FAIL result=%llx before=%d after=%d reads=%u count=%u\n",(unsigned long long)x,before,after,reads,count),1;puts("fixed PMGR read arguments, before/after and single-shot passed");return 0;}
