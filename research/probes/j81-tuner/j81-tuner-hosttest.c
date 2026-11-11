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
extern void j81_tuner_policy_entry(void), j81_tuner_policy_exit(void);
uint64_t fake_provider(void*p){j81_tuner_policy_entry();j81_tuner_policy_exit();test_thread=0x9999;j81_tuner_policy_entry();j81_tuner_policy_exit();test_thread=0;j81_tuner_policy_entry();j81_tuner_policy_exit();test_thread=0x1234;(void)p;test_pm(0xaaaa,1,0x20320,0);test_pm(0xbbbb,0,0x20324,0);test_thread=0x9999;test_pm(0xcccc,0,0x20320,0);test_thread=0x1234;test_pm(0x3ff,0,0x20320,0);if((test_gpc(0x11)&0xf0000000)!=0xa0000000) return 0xbad;if((test_gpc(1)&0xf0000000)!=0xa0000000)return 0xbad;test_identity(0x00070500,0x011b0803);return 0x1234;}
int main(void){unsigned char v[32];j81_tuner_policy_entry();j81_tuner_policy_exit();if(*(unsigned *)(test_buffer+3644)!=0)return puts("FAIL: closed window"),1;test_buffer[0]=1;uint64_t x=test_entry(v);int found=0;for(unsigned i=0;i<count;i++)if(!strcmp(lines[i],"P1=000003ff G1=00000001 I=00070500"))found++;int flags=0;for(unsigned i=0;i<count;i++)if(!strcmp(lines[i],"U=0000005f:00000000:00000001:00000004"))flags++;if(x!=0x1234||found!=1||flags!=1)return printf("FAIL result=%llx found=%d count=%u line=%s\n",(unsigned long long)x,found,count,lines[0]),1;puts("PASS: tuner entry/exit same and other thread, PMGR/GPC and identity output");return 0;}
