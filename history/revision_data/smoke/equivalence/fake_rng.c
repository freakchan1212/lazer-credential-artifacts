
#define _GNU_SOURCE
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <dlfcn.h>
#include <sys/random.h>

static uint64_t rng_state = 0;

__attribute__((constructor))
static void init_seed(void) {
    const char *s = getenv("FAKE_RNG_SEED");
    uint64_t seed = s ? strtoull(s, NULL, 10) : 1ULL;
    rng_state = 0x9e3779b97f4a7c15ULL ^ seed;
}

static void fill_det(void *buf, size_t buflen) {
    uint8_t *p = (uint8_t *)buf;
    for (size_t i = 0; i < buflen; i++) {
        rng_state ^= rng_state >> 12;
        rng_state ^= rng_state << 25;
        rng_state ^= rng_state >> 27;
        uint64_t z = rng_state * 2685821657736338717ULL;
        p[i] = (uint8_t)((z >> ((i & 7) * 8)) & 0xff);
    }
}

ssize_t getrandom(void *buf, size_t buflen, unsigned int flags) {
    (void)flags;
    fill_det(buf, buflen);
    return (ssize_t)buflen;
}

int getentropy(void *buf, size_t buflen) {
    fill_det(buf, buflen);
    return 0;
}
