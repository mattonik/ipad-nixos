#include "kpf.h"
#include <string.h>
extern uint32_t j81_page5dual_start[],j81_page5dual_end[],j81_page5dual_clock[],j81_page5dual_write[],j81_page5dual_decision[],j81_page5dual_decision_resume[],j81_page5dual_aggregate[],j81_page5dual_aggregate_resume[],j81_page5dual_count[],j81_page5dual_count_resume[],j81_page5dual_choice[],j81_page5dual_choice_resume[],j81_page5dual_pm_poll[],j81_page5dual_pm_resume[],j81_page5dual_gpc_poll[],j81_page5dual_gpc_loop[],j81_page5dual_gpc_resume[],j81_page5dual_identity[],j81_page5dual_identity_resume[],j81_page5dual_buffer[],j81_page5dual_format[],j81_page5dual_logger[];
enum {CLOCK,WRITER,DECISION,AGGREGATE,COUNT,CHOICE,PMPOLL,GPCPOLL,IDENTITY,NUM};
static const uint32_t expected[NUM][10]={
 {0x52800036,0x52800021,0x52800002,0xd63f0100,0xf9400360},
 {0x51000748,0xb8685b02,0xb87a5b03,0xf94002a8,0xf944cd08,0xaa1503e0,0xaa1403e1,0xaa1303e4,0xd63f0100,0x91000739},
 {0x8b090108,0x39400118,0x6b16031f,0x54001860,0x39000116,0x340000f6},
 {0x6b19035f,0x54000b20,0x394382e8,0x36100568,0xaa1703e0,0xaa1403e1},
 {0x97ffc473,0xb9403ff8,0x34001518,0x321e02c8,0x7100111f},
 {0x6b15033f,0x54ffe4c2,0xf9002be0,0x52935608,0x72a00028,0x8b08027a,0x91001375},
 {0xd63f0100,0x0a150008,0x6b16011f,0x54000240,0x940074e3,0xeb00035f},
 {0x52800228,0xb9100008,0xb9500008,0x3727ffe8,0x52800140,0x9400b575},
 {0xf9468808,0xb9402109,0xb9401908,0x12101d2a,0x7141c15f}};
static const unsigned lengths[NUM]={5,10,6,6,5,7,6,6,5};static uint32_t *sites[NUM],*cave;static unsigned counts[NUM];static struct mach_header_64 *kernel;static bool armed;
#define CB(name,idx) static bool name(xnu_pf_patch_t *p,uint32_t *x){(void)p;counts[idx]++;sites[idx]=x;return true;}
CB(f_clock,CLOCK) CB(f_write,WRITER) CB(f_decision,DECISION) CB(f_aggregate,AGGREGATE) CB(f_count,COUNT) CB(f_choice,CHOICE) CB(f_pmpoll,PMPOLL) CB(f_gpcpoll,GPCPOLL) CB(f_identity,IDENTITY)
static void add(xnu_pf_patchset_t *set,unsigned i,char *name,void *cb){uint64_t v[10],m[10];for(unsigned k=0;k<lengths[i];k++){v[k]=expected[i][k];m[k]=0xffffffff;}xnu_pf_maskmatch(set,name,v,m,lengths[i],false,cb);}
static void clock_p(xnu_pf_patchset_t *s){add(s,CLOCK,"j81_page5dual_clock",(void*)f_clock);}static void write_p(xnu_pf_patchset_t *s){add(s,WRITER,"j81_page5dual_writer",(void*)f_write);}static void dec_p(xnu_pf_patchset_t *s){add(s,DECISION,"j81_page5dual_decision",(void*)f_decision);}static void agg_p(xnu_pf_patchset_t *s){add(s,AGGREGATE,"j81_page5dual_aggregate",(void*)f_aggregate);}static void count_p(xnu_pf_patchset_t *s){add(s,COUNT,"j81_page5dual_count",(void*)f_count);}
static void choice_p(xnu_pf_patchset_t*s){add(s,CHOICE,"j81_page5dual_choice",(void*)f_choice);}
static void pmpoll_p(xnu_pf_patchset_t*s){add(s,PMPOLL,"j81_page5dual_pmpoll",(void*)f_pmpoll);}
static void gpcpoll_p(xnu_pf_patchset_t*s){add(s,GPCPOLL,"j81_page5dual_gpcpoll",(void*)f_gpcpoll);}
static void identity_p(xnu_pf_patchset_t*s){add(s,IDENTITY,"j81_page5dual_identity",(void*)f_identity);}
static void init(struct mach_header_64 *h,xnu_pf_range_t *s){(void)s;kernel=h;}
static bool uuid_ok(struct mach_header_64 *h){static const unsigned char u[]={0xcc,0x26,0xbe,0x6a,0x29,0x2b,0x37,0x59,0x9e,0xd0,0x29,0x0b,0xcf,0x18,0xb0,0x90};uint8_t *p=(uint8_t *)(h+1),*end=p+h->sizeofcmds;for(uint32_t i=0;i<h->ncmds&&(size_t)(end-p)>=sizeof(struct load_command);i++){struct load_command*c=(struct load_command*)p;if(c->cmdsize<sizeof(*c)||c->cmdsize>(size_t)(end-p))return false;if(c->cmd==LC_UUID&&c->cmdsize>=sizeof(struct uuid_command))return !memcmp(((struct uuid_command*)c)->uuid,u,sizeof(u));p+=c->cmdsize;}return false;}
static bool target_ok(struct mach_header_64 *h){if(!uuid_ok(h)||gKernelVersion.darwinMajor!=21||gKernelVersion.darwinMinor!=6||gKernelVersion.xnuMajor!=8020||gKernelVersion.xnuMinor!=241||gKernelVersion.xnuPatch!=42||gKernelVersion.xnuRun!=8)return false;for(unsigned i=0;i<NUM;i++)if(counts[i]!=1||!sites[i]||memcmp(sites[i],expected[i],lengths[i]*4))return false;return true;}
static bool branch(uint64_t from,uint64_t to,bool link,uint32_t*out){int64_t off=(int64_t)(to-from);if((off&3)||off< -0x8000000LL||off>0x7fffffcLL)return false;*out=(link?0x94000000U:0x14000000U)|((uint32_t)(off>>2)&0x03ffffffU);return true;}
static bool branches(uint32_t*out){return branch(xnu_ptr_to_va(sites[CLOCK]+3),xnu_ptr_to_va(cave+(j81_page5dual_clock-j81_page5dual_start)),true,&out[0])&&branch(xnu_ptr_to_va(sites[WRITER]+8),xnu_ptr_to_va(cave+(j81_page5dual_write-j81_page5dual_start)),true,&out[1])&&branch(xnu_ptr_to_va(sites[DECISION]+2),xnu_ptr_to_va(cave+(j81_page5dual_decision-j81_page5dual_start)),false,&out[2])&&branch(xnu_ptr_to_va(cave+(j81_page5dual_decision_resume-j81_page5dual_start)),xnu_ptr_to_va(sites[DECISION]+3),false,&out[3])&&branch(xnu_ptr_to_va(sites[AGGREGATE]),xnu_ptr_to_va(cave+(j81_page5dual_aggregate-j81_page5dual_start)),false,&out[4])&&branch(xnu_ptr_to_va(cave+(j81_page5dual_aggregate_resume-j81_page5dual_start)),xnu_ptr_to_va(sites[AGGREGATE]+1),false,&out[5])&&branch(xnu_ptr_to_va(sites[COUNT]+1),xnu_ptr_to_va(cave+(j81_page5dual_count-j81_page5dual_start)),false,&out[6])&&branch(xnu_ptr_to_va(cave+(j81_page5dual_count_resume-j81_page5dual_start)),xnu_ptr_to_va(sites[COUNT]+2),false,&out[7])&&branch(xnu_ptr_to_va(sites[CHOICE]),xnu_ptr_to_va(cave+(j81_page5dual_choice-j81_page5dual_start)),false,&out[8])&&branch(xnu_ptr_to_va(cave+(j81_page5dual_choice_resume-j81_page5dual_start)),xnu_ptr_to_va(sites[CHOICE]+1),false,&out[9])
 &&branch(xnu_ptr_to_va(sites[PMPOLL]+1),xnu_ptr_to_va(cave+(j81_page5dual_pm_poll-j81_page5dual_start)),false,&out[10])
 &&branch(xnu_ptr_to_va(cave+(j81_page5dual_pm_resume-j81_page5dual_start)),xnu_ptr_to_va(sites[PMPOLL]+2),false,&out[11])
 &&branch(xnu_ptr_to_va(sites[GPCPOLL]+3),xnu_ptr_to_va(cave+(j81_page5dual_gpc_poll-j81_page5dual_start)),false,&out[12])
 &&branch(xnu_ptr_to_va(cave+(j81_page5dual_gpc_loop-j81_page5dual_start)),xnu_ptr_to_va(sites[GPCPOLL]+2),false,&out[13])
 &&branch(xnu_ptr_to_va(cave+(j81_page5dual_gpc_resume-j81_page5dual_start)),xnu_ptr_to_va(sites[GPCPOLL]+4),false,&out[14])
 &&branch(xnu_ptr_to_va(sites[IDENTITY]+3),xnu_ptr_to_va(cave+(j81_page5dual_identity-j81_page5dual_start)),false,&out[15])
 &&branch(xnu_ptr_to_va(cave+(j81_page5dual_identity_resume-j81_page5dual_start)),xnu_ptr_to_va(sites[IDENTITY]+4),false,&out[16]);}
static uint32_t size(void){return (uint32_t)(j81_page5dual_end-j81_page5dual_start);}
static uint32_t emit(uint32_t*area){cave=area;uint32_t b[17];if(!target_ok(kernel)||!branches(b)){printf("J81_PAGE5DUAL_EMIT prepared=0 matches=%u,%u,%u,%u,%u,%u,%u,%u,%u\n",counts[0],counts[1],counts[2],counts[3],counts[4],counts[5],counts[6],counts[7],counts[8]);return 0;}void*buf=alloc_static(4096);if(!buf){printf("J81_PAGE5DUAL_EMIT allocation_failed\n");return 0;}memset(buf,0,4096);*(uint32_t*)buf=1;memcpy(area,j81_page5dual_start,(size_t)size()*4);uint64_t slide=xnu_slide_value(kernel),buffer=xnu_ptr_to_va(buf),format=0xfffffff0057c4eddULL+slide,logger=0xfffffff0066b0ff4ULL+slide;memcpy(area+(j81_page5dual_buffer-j81_page5dual_start),&buffer,8);memcpy(area+(j81_page5dual_format-j81_page5dual_start),&format,8);memcpy(area+(j81_page5dual_logger-j81_page5dual_start),&logger,8);armed=true;printf("J81_PAGE5DUAL_EMIT prepared=1 words=%u\n",size());return size();}
static void finish(struct mach_header_64*h){uint32_t b[17];bool ok=armed&&target_ok(h)&&branches(b);
#if defined(KPF_TEST) || defined(J81_PAGE5DUAL_DEVICE_BUILD)
 if(ok){cave[j81_page5dual_decision_resume-j81_page5dual_start]=b[3];cave[j81_page5dual_aggregate_resume-j81_page5dual_start]=b[5];cave[j81_page5dual_count_resume-j81_page5dual_start]=b[7];cave[j81_page5dual_choice_resume-j81_page5dual_start]=b[9];
 cave[j81_page5dual_pm_resume-j81_page5dual_start]=b[11];cave[j81_page5dual_gpc_loop-j81_page5dual_start]=b[13];cave[j81_page5dual_gpc_resume-j81_page5dual_start]=b[14];cave[j81_page5dual_identity_resume-j81_page5dual_start]=b[16];
 sites[PMPOLL][1]=b[10];sites[GPCPOLL][3]=b[12];sites[IDENTITY][3]=b[15];sites[CHOICE][0]=b[8];sites[DECISION][2]=b[2];sites[AGGREGATE][0]=b[4];sites[COUNT][1]=b[6];sites[CLOCK][3]=b[0];sites[WRITER][8]=b[1];printf("J81_PAGE5DUAL_PATCH applied=1\n");}else printf("J81_PAGE5DUAL_PATCH applied=0\n");
#else
 (void)ok;
#endif
}
kpf_component_t j81_page5dual_capture={.init=init,.finish=finish,.shc_size=size,.shc_emit=emit,.patches={{"com.apple.AGXG4G","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,clock_p},{"com.apple.driver.ApplePMGR","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,write_p},{"com.apple.driver.ApplePMGR","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,dec_p},{"com.apple.driver.ApplePMGR","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,agg_p},{"com.apple.driver.ApplePMGR","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,count_p},{"com.apple.driver.ApplePMGR","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,choice_p},{"com.apple.driver.ApplePMGR","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,pmpoll_p},{"com.apple.AGXG4G","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,gpcpoll_p},{"com.apple.AGXG4G","__TEXT_EXEC","__text",XNU_PF_ACCESS_32BIT,identity_p},{}}};
