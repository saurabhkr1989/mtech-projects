#include "safe_prime.h"
#include "utils.h"
#include <iostream>

// Generates a safe prime p of at least n bits.
void generate_safe_prime(mpz_class& p, int n_bits, gmp_randclass& rand_state) {
    print_step("Generating safe prime of at least " + std::to_string(n_bits) + " bits...");
    mpz_class q;
    while (true) {
        // Generate a random candidate for q
        // FIX: Use the correct C++ style for random number generation
        q = rand_state.get_z_bits(n_bits - 1);

        // Find the next prime after the random number
        mpz_nextprime(q.get_mpz_t(), q.get_mpz_t());

        // Calculate p = 2q + 1
        p = 2 * q + 1;

        // Check if p is also prime
        if (mpz_probab_prime_p(p.get_mpz_t(), 25) > 0) {
            break; // Found a safe prime
        }
    }
    print_info("Generated Safe Prime p", p.get_str());
    print_info("Sophie Germain prime q", q.get_str());
}

