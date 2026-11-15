#include "generators.h"
#include "utils.h"
#include <iostream>

// Power function for mpz_class (modular exponentiation)
void power(mpz_class& result, const mpz_class& base, const mpz_class& exp, const mpz_class& mod) {
    mpz_powm(result.get_mpz_t(), base.get_mpz_t(), exp.get_mpz_t(), mod.get_mpz_t());
}

// Finds and lists up to 'count' generators of Z*_p for a given safe prime p.
std::vector<mpz_class> find_generators(const mpz_class& p, int count) {
    std::vector<mpz_class> generators;
    mpz_class p_minus_1 = p - 1;
    mpz_class q = (p - 1) / 2;

    // The prime factors of p-1 are 2 and q for a safe prime.
    std::vector<mpz_class> factors;
    factors.push_back(2);
    factors.push_back(q);

    size_t required_count = static_cast<size_t>(count);

    for (mpz_class g = 2; g < p && generators.size() < required_count; ++g) {
        bool is_generator = true;
        for (const auto& factor : factors) {
            mpz_class result;
            power(result, g, p_minus_1 / factor, p);
            if (result == 1) {
                is_generator = false;
                break;
            }
        }
        if (is_generator) {
            generators.push_back(g);
        }
    }
    
    // FIX: Print generators horizontally
    print_info("Found generators", "");
    std::cout << C_BLUE << "  ";
    for(size_t i = 0; i < generators.size(); ++i) {
        std::cout << generators[i].get_str() << (i == generators.size() - 1 ? "" : ", ");
    }
    std::cout << C_RESET << std::endl;


    return generators;
}

