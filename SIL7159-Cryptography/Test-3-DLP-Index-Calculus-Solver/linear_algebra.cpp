#include "linear_algebra.h"
#include "utils.h"
#include <iostream>
#include <vector>

// Function to compute the modular inverse of a w.r.t. m
bool modular_inverse(mpz_class& result, const mpz_class& a, const mpz_class& m) {
    int ret = mpz_invert(result.get_mpz_t(), a.get_mpz_t(), m.get_mpz_t());
    return ret != 0;
}

// Solves a system of linear congruences Ax = b (mod m) using Gaussian elimination.
bool solve_linear_system(std::vector<mpz_class>& logs, const std::vector<Relation>& relations, const mpz_class& p_minus_1, int fb_size) {
    
    // FIX: Cast fb_size to size_t to resolve signed/unsigned comparison warning.
    size_t required_relations = static_cast<size_t>(fb_size);

    if (relations.size() < required_relations) {
        return false; // Not enough relations to form a square matrix
    }

    // We need a square matrix, so we take the first fb_size relations
    size_t n = fb_size;
    std::vector<std::vector<mpz_class>> matrix(n, std::vector<mpz_class>(n));
    std::vector<mpz_class> b(n);

    for (size_t i = 0; i < n; ++i) {
        for (size_t j = 0; j < n; ++j) {
            matrix[i][j] = relations[i].exponents[j];
        }
        b[i] = relations[i].k;
    }

    // Gaussian elimination
    for (size_t i = 0; i < n; ++i) {
        // Find a pivot
        size_t pivot = i;
        while (pivot < n) {
            mpz_class inv;
            if (modular_inverse(inv, matrix[pivot][i], p_minus_1)) {
                break; // Found an invertible element
            }
            pivot++;
        }

        if (pivot == n) {
            return false; // No pivot found, matrix is singular
        }
        std::swap(matrix[i], matrix[pivot]);
        std::swap(b[i], b[pivot]);

        // Normalize the pivot row
        mpz_class inv;
        modular_inverse(inv, matrix[i][i], p_minus_1);
        for (size_t j = i; j < n; ++j) {
            matrix[i][j] = (matrix[i][j] * inv) % p_minus_1;
        }
        b[i] = (b[i] * inv) % p_minus_1;

        // Eliminate other rows
        for (size_t k = 0; k < n; ++k) {
            if (i != k) {
                mpz_class factor = matrix[k][i];
                for (size_t j = i; j < n; ++j) {
                    matrix[k][j] = (matrix[k][j] - factor * matrix[i][j]) % p_minus_1;
                }
                b[k] = (b[k] - factor * b[i]) % p_minus_1;
            }
        }
    }
    
    logs.resize(n);
    for(size_t i = 0; i < n; ++i) {
        logs[i] = (b[i] % p_minus_1 + p_minus_1) % p_minus_1; // Ensure positive result
    }

    return true;
}

