#ifndef TEST_CASES_H
#define TEST_CASES_H

#include <vector>
#include <gmpxx.h>

// Main menu and test case setup. Now takes n_bits to select parameters dynamically.
void run_test_cases(const mpz_class& p, const std::vector<mpz_class>& generators, gmp_randclass& rand_state, int n_bits);

#endif // TEST_CASES_H

