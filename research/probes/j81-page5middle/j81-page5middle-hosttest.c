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
extern uint64_t test_pm(unsigned,unsigned,unsigned,unsigned),test_gpc(unsigned),test_entry(unsigned char*);extern void test_identity(unsigned,unsigned);
uint64_t fake_provider(void*p){(void)p;test_pm(0x3ff,0,0x20320,0);return 0x1234;}
int main(void){unsigned char v[32];test_vtable[0x980/8]=(uint64_t)fake_read;test_pmgr[0]=(uint64_t)test_vtable;test_buffer[0]=1;uint64_t x=test_entry(v);test_gpc(0x11);if(reads!=1)return puts("busy polled"),1; test_thread++;test_gpc(1);if(reads!=1)return puts("wrong thread read"),1;test_thread--;test_gpc(1);test_gpc(1);test_identity(0x00070500,0x011b0803);test_identity(0x00070500,0x011b0803);int e=-1,l=-1,q0=-1,q1=-1,mid=-1;for(unsigned i=0;i<count;i++){if(!strcmp(lines[i],"PAGE5-early-before"))e=i;if(!strcmp(lines[i],"PAGE5-before"))l=i;if(!strcmp(lines[i],"M=40000000") && mid<0)mid=i;if(!strcmp(lines[i],"Q=00000000"))q0=i;if(!strcmp(lines[i],"Q=40000000"))q1=i;}if(x!=0x1234||reads!=3||e<0||q0<=e||mid<=q0||l<=mid||q1<=l)return printf("FAIL x=%llx reads=%u markers=%d,%d,%d,%d count=%u\n",(unsigned long long)x,reads,e,q0,l,q1,count),1;puts("early/middle/late fixed address, busy skip and one-shot passed");return 0;}
