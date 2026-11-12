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
int main(void){unsigned char v[32];test_vtable[0x980/8]=(uint64_t)fake_read;test_pmgr[0]=(uint64_t)test_vtable;test_buffer[0]=1;uint64_t x=test_entry(v);test_thread++;if(test_power()!=0x9876||reads!=1)return puts("power thread skip failed"),1;test_thread--;test_vtable[0x980/8]=(uint64_t)fake_other;if(test_power()!=0x9876||reads!=1)return puts("power target skip failed"),1;test_vtable[0x980/8]=(uint64_t)fake_read;if(test_power()!=0x9876||reads!=2||test_power()!=0x9876||reads!=2)return puts("power wrapper or one-shot failed"),1;test_thread++;if(test_control()!=0x11||reads!=2)return puts("control wrong thread"),1;test_thread--;test_vtable[0x980/8]=(uint64_t)fake_other;if(test_control()!=0x11||reads!=2)return puts("control wrong method"),1;test_vtable[0x980/8]=(uint64_t)fake_read;if(test_control()!=0x11||reads!=3||test_control()!=0x11||reads!=3)return puts("control wrapper or one-shot failed"),1;test_store(fake_mmio,test_pmgr,0,0x5004,0,0x12345678);if(*(uint32_t *)(fake_mmio+0x5004)!=0x12345678)return puts("store failed"),1;test_gpc(0x11);if(reads!=3)return puts("busy polled"),1; test_thread++;test_gpc(1);if(reads!=3)return puts("wrong thread read"),1;test_thread--;test_vtable[0x980/8]=(uint64_t)fake_other;test_gpc(1);if(reads!=3)return puts("wrong method read"),1;test_vtable[0x980/8]=(uint64_t)fake_read;test_gpc(1);test_gpc(1);test_identity(0x00070500,0x011b0803);test_identity(0x00070500,0x011b0803);int e=-1,l=-1,q0=-1,q1=-1,mid=-1,pow=-1,ctrl=-1,writer=-1,summary=-1,y=-1,synthetic=-1;for(unsigned i=0;i<count;i++){if(!strcmp(lines[i],"Y=00000001:00000000:00000000:00000000:00000000:00000000:00000000:00000000:00000000:00000001"))y=i;if(!strcmp(lines[i],"W=00000502:00000502:53545349"))synthetic=i;if(!strcmp(lines[i],"PAGE5-early-before"))e=i;if(!strcmp(lines[i],"PAGE5-before"))l=i;if(!strcmp(lines[i],"Z=00000002:00000001:00000002:00000000"))summary=i;if(!strcmp(lines[i],"W=00000101:00000101:12345678"))writer=i;if(!strcmp(lines[i],"C=40000000") && ctrl<0)ctrl=i;if(!strcmp(lines[i],"T=40000000") && pow<0)pow=i;if(!strcmp(lines[i],"M=40000000") && mid<0)mid=i;if(!strcmp(lines[i],"Q=00000000"))q0=i;if(!strcmp(lines[i],"Q=40000000"))q1=i;}if(x!=0x1234||reads!=5||summary<0||writer<0||synthetic<0||*(uint32_t *)(fake_mmio+0x5004)!=0x40000000||*(uint32_t *)(test_buffer+3720)!=2||y<0||e<0||q0<=e||ctrl<=q0||pow<=ctrl||mid<=pow||l<=mid||q1<=l)return printf("FAIL x=%llx reads=%u markers=%d,%d,%d,%d count=%u\n",(unsigned long long)x,reads,e,q0,l,q1,count),1;puts("writer value/phase and early/power/control/middle/late, busy, wrong-thread and wrong-method skips and one-shot passed");return 0;}
