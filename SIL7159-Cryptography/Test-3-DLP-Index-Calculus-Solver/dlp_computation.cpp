#include "dlp_computation.h"
#include "relation_collection.h" // For factor_over_base
#include "utils.h"
#include <iostream>
#include <vector>
#include <gmpxx.h>

void compute_final_dlp(mpz_class& x, const mpz_class& p, const mpz_class& alpha, const mpz_class& beta, const std::vector<mpz_class>& factor_base, const std::vector<mpz_class>& logs, gmp_randclass& rand_state) {
    print_step("Computing the final discrete logarithm for beta...");
    mpz_class p_minus_1 = p - 1;

    while (true) {
        // 1. Select a random integer k, 0 <= k < p-1
        mpz_class k = rand_state.get_z_range(p_minus_1);

        // 2. Compute beta * alpha^k (mod p)
        mpz_class temp_alpha_k;
        mpz_powm(temp_alpha_k.get_mpz_t(), alpha.get_mpz_t(), k.get_mpz_t(), p.get_mpz_t());
        
        mpz_class target = (beta * temp_alpha_k) % p;

        // 3. Try to factorize the result over the factor base
        std::vector<mpz_class> exponents;
        if (factor_over_base(target, factor_base, exponents)) {
            // If successful, we have:
            // beta * alpha^k = PRODUCT(factor_base[i] ^ exponents[i])
            // log(beta) + k = SUM(exponents[i] * log(factor_base[i])) (mod p-1)
            
            print_info("Found a smooth value for beta*alpha^k with k", k.get_str());

            mpz_class sum = 0;
            for (size_t i = 0; i < exponents.size(); ++i) {
                sum = (sum + exponents[i] * logs[i]) % p_minus_1;
            }

            // log(beta) = sum - k (mod p-1)
            x = (sum - k + p_minus_1) % p_minus_1;
            
            print_info("Calculation", "log(beta) = (SUM(e_i * log(p_i)) - k) mod (p-1)");
            break; // Exit the loop
        }
        // If not successful, the loop continues with a new random k.
    }
}

