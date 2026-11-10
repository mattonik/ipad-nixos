#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
uint64_t test_thread=0x1234; unsigned char test_buffer[4096] __attribute__((aligned(16))), pmgr[0x3000] __attribute__((aligned(16)));
const char test_format[]="test %s";
static char lines[80][256]; static unsigned line_count, calls; static uint64_t flags;
void fake_logger(const char*f,...){(void)f;va_list v;va_start(v,f);const char*s=va_arg(v,const char*);if(line_count<80)snprintf(lines[line_count++],256,"%s",s);va_end(v);}
void fake_inner(void*p,unsigned s,unsigned o,unsigned v,unsigned st){(void)p;(void)s;(void)o;(void)v;(void)st;calls++;}
extern void test_write(void*,unsigned,unsigned,unsigned,unsigned); extern uint64_t test_decision(unsigned,unsigned),test_aggregate(unsigned,unsigned),test_count(unsigned),test_choice(void*,unsigned,unsigned),test_entry(unsigned char*);
uint64_t fake_provider(void*p){test_decision(0,15);test_aggregate(0,15);test_count(1);flags=test_choice(pmgr,15,15);for(unsigned i=0;i<150;i++)test_write(p,i<33?9:10,0x100+i,0x9000+i,15);test_thread=0x9999;test_write(p,8,1,2,15);test_thread=0x1234;test_write(p,9,1,2,4);return 0x1234;}
int main(void){unsigned char v[32]; *(unsigned*)(pmgr+0x2684)=1;test_buffer[0]=1;test_write(0,9,0x55,0x66,15);uint64_t r=test_entry(v);if(r!=0x1234||line_count!=64||calls!=153||(flags&0xf0000000)!=0x60000000)return printf("bad counts %llu %u %u %llx\n",(unsigned long long)r,line_count,calls,(unsigned long long)flags),1;for(unsigned i=0;i<line_count;i++)if(!strstr(lines[i],"N1:00000001 L000f007c X1:0000000f>0000000f M00000001 W00000098 "))return printf("bad header %s\n",lines[i]),1;for(unsigned i=0;i<127;i++){char e[40];snprintf(e,sizeof(e),"P1T1:%08x/0000000f:%08x=%08x;",i<33?9:10,0x100+i,0x9000+i);int seen=0;for(unsigned j=0;j<line_count;j++)if(strstr(lines[j],e))seen++;if(seen!=1)return printf("missing %u\n",i),1;}if(strncmp(lines[0],"B1 ",3))return puts("missing overflow flag"),1; if(!strstr(lines[0],"P0T0:00000009/0000000f:00000055=00000066;"))return puts("missing prewindow"),1;  puts("same and different thread labels, phases and batching passed");return 0;}
