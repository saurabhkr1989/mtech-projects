#ifndef LINEAR_ALGEBRA_H
#define LINEAR_ALGEBRA_H

#include <vector>
#include <gmpxx.h>
#include "relation_collection.h"

// Solves the system of linear congruences to find the discrete logs of the factor base elements.
bool solve_linear_system(std::vector<mpz_class>& logs, const std::vector<Relation>& relations, const mpz_class& p_minus_1, int fb_size);

#endif // LINEAR_ALGEBRA_H
