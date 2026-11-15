#ifndef FACTOR_BASE_H
#define FACTOR_BASE_H

#include <vector>
#include <gmpxx.h>

// Generates the factor base consisting of the first 'size' prime numbers.
std::vector<mpz_class> generate_factor_base(int size);

#endif // FACTOR_BASE_H
