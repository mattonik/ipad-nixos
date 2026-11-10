#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
uint64_t test_thread=0x1234;
unsigned char test_buffer[4096] __attribute__((aligned(16)));
const char test_format[]="test %s";
static char lines[16][256];static unsigned count;
void fake_logger(const char*f,...){(void)f;va_list v;va_start(v,f);const char*s=va_arg(v,const char*);if(count<16)snprintf(lines[count++],256,"%s",s);va_end(v);}
void fake_inner(void*p,unsigned a,unsigned b,unsigned c,unsigned d){(void)p;(void)a;(void)b;(void)c;(void)d;}
extern uint64_t test_pm(unsigned,unsigned,unsigned,unsigned),test_gpc(unsigned),test_entry(unsigned char*);extern void test_identity(unsigned,unsigned);
uint64_t fake_provider(void*p){(void)p;test_pm(0xaaaa,1,0x20320,0);test_pm(0xbbbb,0,0x20324,0);test_thread=0x9999;test_pm(0xcccc,0,0x20320,0);test_thread=0x1234;if((test_gpc(0x11)&0xf0000000)!=0xa0000000) return 0xbad;test_identity(0x00070500,0x011b0803);return 0x1234;}
int main(void){unsigned char v[32];test_buffer[0]=1;uint64_t x=test_entry(v);int found=0;for(unsigned i=0;i<count;i++)if(!strcmp(lines[i],"P0=00000000 G0=00000000 I=00070500"))found++;if(x!=0x1234||found!=1)return printf("FAIL result=%llx found=%d count=%u line=%s\n",(unsigned long long)x,found,count,lines[0]),1;puts("unobserved PMGR and busy-only GPC are reported as unseen");return 0;}
