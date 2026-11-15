#ifndef DLP_COMPUTATION_H
#define DLP_COMPUTATION_H

#include <vector>
#include <gmpxx.h>

// Computes the discrete log of the final target element beta.
void compute_final_dlp(mpz_class& x, const mpz_class& p, const mpz_class& alpha, const mpz_class& beta, const std::vector<mpz_class>& factor_base, const std::vector<mpz_class>& logs, gmp_randclass& rand_state);

#endif // DLP_COMPUTATION_H
