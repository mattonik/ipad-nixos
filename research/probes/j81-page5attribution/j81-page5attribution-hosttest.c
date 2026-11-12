#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
uint64_t test_thread=0x1234, test_pmgr[1], test_vtable[400];
unsigned char test_buffer[4096] __attribute__((aligned(16)));
const char test_format[]="test %s";
void fake_logger(const char*f,...){(void)f;}
void fake_inner(void*p,unsigned a,unsigned b,unsigned c,unsigned d){(void)p;(void)a;(void)b;(void)c;(void)d;}
uint64_t fake_read(void*self,unsigned r,unsigned off,unsigned inst){(void)self;(void)r;(void)off;(void)inst;return 0;}
uint64_t fake_other(void*p,unsigned a,unsigned b,unsigned c){(void)p;(void)a;(void)b;(void)c;return 0;}
uint64_t fake_power(void){return 0;}
uint64_t fake_provider(void*p){(void)p;return 0;}
extern uint32_t test_readsite(void*,void*,unsigned,unsigned,unsigned);
extern void test_store(void*,void*,unsigned,unsigned,unsigned,unsigned),test_bridge(void*,unsigned,unsigned,unsigned);
static unsigned char mmio[0x6000] __attribute__((aligned(16)));
#define U32(o) (*(uint32_t*)(test_buffer+(o)))
#define U64(o) (*(uint64_t*)(test_buffer+(o)))
#define CHECK(x) do { if(!(x)){printf("FAIL line %d: %s\n",__LINE__,#x);return 1;} } while(0)
int main(void){
 U64(3640)=(uintptr_t)test_pmgr; *(uint32_t*)(mmio+0x5004)=0xdeadbeef;
 CHECK(test_readsite(mmio,test_pmgr,0x5004,0,0)==0xdeadbeef);
 CHECK(U64(4000)==(uintptr_t)(mmio+0x5004));
 U32(3712)=1;
 test_store(mmio,test_pmgr,0,0x5004,0,0x12345678);
 CHECK(*(uint32_t*)(mmio+0x5004)==0x12345678 && U32(3720)==1 && U32(3744)==0x101 && U32(3748)==0x101 && U32(3752)==0x12345678 && U32(3756)==1 && U32(4008)==0);
 test_bridge(mmio,0x5004,0,0xabcdef01);
 CHECK(*(uint32_t*)(mmio+0x5004)==0xabcdef01 && U32(3720)==2 && U32(3760)==0x201 && U32(3764)==0x201 && U32(3768)==0xabcdef01 && U32(3772)==1 && U32(4012)==0 && U32(4016)==1);
 test_store(mmio,test_pmgr,0,0x5008,0,0x55);
 CHECK(*(uint32_t*)(mmio+0x5008)==0x55 && U32(3720)==2);
 U32(3720)=16; test_store(mmio,test_pmgr,0,0x5004,0,0x22);
 CHECK(U32(3724)==1 && U32(4008)==0 && *(uint32_t*)(mmio+0x5004)==0x22);
 CHECK(test_readsite(mmio+4,test_pmgr,0x5004,0,0)==0x55 && U32(4036)==1);
 puts("PASS: target lookup, both exact stores, non-target, overflow and target change"); return 0;
}
