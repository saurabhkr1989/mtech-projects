#ifndef RELATION_COLLECTION_H
#define RELATION_COLLECTION_H

#include <vector>
#include <gmpxx.h>
#include <mpi.h>

// A structure to hold a found relation
struct Relation {
    mpz_class k;
    std::vector<mpz_class> exponents;
};

// Tries to factor a number over the factor base.
// Returns true if successful, storing exponents in the vector.
bool factor_over_base(mpz_class num, const std::vector<mpz_class>& factor_base, std::vector<mpz_class>& exponents);

// Parallel relation collection using MPI.
std::vector<Relation> collect_relations_parallel(const mpz_class& p, const mpz_class& alpha, const std::vector<mpz_class>& factor_base, int required_relations, int rank, int world_size, gmp_randclass& rand_state);


#endif // RELATION_COLLECTION_H
