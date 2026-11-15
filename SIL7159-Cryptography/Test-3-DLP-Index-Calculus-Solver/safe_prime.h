#ifndef SAFE_PRIME_H
#define SAFE_PRIME_H

#include <gmpxx.h>

// Generates a safe prime p of at least n bits.
// A prime p is safe if (p-1)/2 is also prime.
void generate_safe_prime(mpz_class& p, int n_bits, gmp_randclass& rand_state);

#endif // SAFE_PRIME_H
