#ifndef BASELINE_HOOKS_H
#define BASELINE_HOOKS_H
#include <stdint.h>
#include <string.h>
static __thread uint64_t baseline_counts[64];
void baseline_reset_counters(void) { memset(baseline_counts,0,sizeof baseline_counts); }
uint64_t baseline_get_counter(unsigned int i) { return i<64?baseline_counts[i]:0; }
void baseline_count_falcon_attempt(void) { baseline_counts[7]++; }
#endif
