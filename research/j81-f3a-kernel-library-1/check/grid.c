/* Prints the encoder grid of j81_kernel_library.py's `grid` command from Orchard's C encoders (A8 mode). */
#include <stdio.h>
#include "g9p_isa.h"   /* OrchardLinux/mesa 7df85604e5 src/imagination/g9p/g9p_isa.h */
bool g5p_usc_g4p = true;
static struct g9p_code C;
static void start(void) { C.n = 0; C.error = NULL; C.fragment = false; C.a9_stack = true; }
static void show(const char *name, const char *arg) {
   printf("%s %s", name, arg);
   for (unsigned i = 0; i < C.n; i++) printf(" %04x", C.w[i]);
   printf("%s\n", C.error ? " ERROR" : "");
}
int main(void) {
   char a[64];
   unsigned sts[] = {3, 4, 6, 7};
   for (int i = 0; i < 4; i++) {
      unsigned st = sts[i]; snprintf(a, sizeof a, "%u", st);
      start(); g9p_push_init(&C, st); show("push_init", a);
      start(); g9p_pop(&C, st); show("pop", a);
      start(); g9p_pop_levels(&C, st, 1); show("pop_levels1", a);
      start(); g9p_pop_levels(&C, st, 2); show("pop_levels2", a);
      start(); g9p_push_if(&C, st, false); show("push_if", a);
      start(); g9p_else(&C, st); show("else", a);
      start(); g9p_loop_begin(&C, st); show("loop_begin", a);
      start(); g9p_loop_break(&C, st, false); show("loop_break0", a);
   }
   uint32_t imms[] = {0, 1, 3, 5, 0x2a, 0x203100, 0xcafe0001, 0xffffffff, 0xc0ffee01, 0x01008000};
   for (int i = 0; i < 10; i++) { snprintf(a, sizeof a, "%u", imms[i]); start(); g9p_mov_imm(&C, 2, imms[i]); show("mov_imm2", a); }
   unsigned sh[][3] = {{1,0,2},{2,1,2},{1,1,5},{1,1,2},{1,1,6}};
   for (int i = 0; i < 5; i++) { snprintf(a, sizeof a, "%u,%u,%u", sh[i][0], sh[i][1], sh[i][2]); start(); g9p_shift_imm(&C, sh[i][0], sh[i][1], sh[i][2], false); show("shl", a); }
   unsigned ad[][3] = {{2,0,1},{2,2,1},{4,0,2},{4,2,2},{4,4,2}};
   for (int i = 0; i < 5; i++) { snprintf(a, sizeof a, "%u,%u,%u", ad[i][0], ad[i][1], ad[i][2]); start(); g9p_addr(&C, ad[i][0], ad[i][1], ad[i][2], 0, false); show("addr", a); }
   struct { bool s; unsigned r, p; } m[] = {{1,0,2},{1,2,0},{1,3,4},{0,4,2},{0,3,4},{0,6,4},{1,4,2},{1,1,4},{1,5,2}};
   for (int i = 0; i < 9; i++) { snprintf(a, sizeof a, "%s,%u,%u", m[i].s ? "True" : "False", m[i].r, m[i].p); start(); g9p_mem_at(&C, m[i].s, G9P_SIZE_U32, m[i].r, m[i].p); show("mem", a); }
   start(); g9p_tg_load(&C, 1, 0); show("tg_load", "1");
   start(); g9p_add_imm(&C, 4, 4, 0x2a); show("add_imm", "4,4,42");
   start(); g9p_add_imm(&C, 5, 5, 1); show("add_imm", "5,5,1");
   start(); g9p_add_imm(&C, 4, 4, 1); show("add_imm", "4,4,1");
   start(); g9p_alu2(&C, G9P_IADD, 1, 1, 0, false); show("alu2", "iadd 1 1 0");
   start(); g9p_alu2(&C, G9P_IADD, 4, 4, 5, true); show("alu2", "iadd 4 4 5 k");
   start(); g9p_alu2(&C, G9P_IADD, 3, 3, 6, true); show("alu2", "iadd 3 3 6 k");
   start(); g9p_alu2(&C, G9P_IADD, 4, 4, 6, false); show("alu2", "iadd 4 4 6");
   start(); g9p_alu2(&C, G9P_AND, 4, 0, 4, false); show("alu2", "and 4 0 4");
   start(); g9p_cmp_imm(&C, G9P_UGT, 4, 0); show("cmp_imm", "ugt 4 0");
   start(); g9p_cmp_imm(&C, G9P_EQ, 4, 1); show("cmp_imm", "eq 4 1");
   start(); g9p_prologue(&C, 4, false); show("prologue", "1 0");
   start(); g9p_prologue(&C, 4, true); show("prologue", "1 1");
   start(); g9p_prologue(&C, 8, false); show("prologue", "2 0");
   start(); g9p_prologue(&C, 12, false); show("prologue", "3 0");
   start(); g9p_prologue(&C, 12, true); show("prologue", "3 1");
   return 0;
}
