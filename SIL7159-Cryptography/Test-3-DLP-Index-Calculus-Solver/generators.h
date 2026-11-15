#ifndef GENERATORS_H
#define GENERATORS_H

#include <vector>
#include <gmpxx.h>

// Finds and lists up to 10 generators of Z*_p for a given safe prime p.
std::vector<mpz_class> find_generators(const mpz_class& p, int count);

#endif // GENERATORS_H
