#include "factor_base.h"
#include "utils.h"
#include <iostream>
#include <string>

// Generates the factor base: the first 'size' primes.
std::vector<mpz_class> generate_factor_base(int size) {
    print_step("Generating factor base...");
    std::vector<mpz_class> factor_base;
    mpz_class p = 2;

    // Cast size to size_t to resolve signed/unsigned comparison warning.
    size_t required_size = static_cast<size_t>(size);

    while (factor_base.size() < required_size) {
        factor_base.push_back(p);
        mpz_nextprime(p.get_mpz_t(), p.get_mpz_t());
    }
    
    std::string fb_str = "";
    for(size_t i = 0; i < factor_base.size(); ++i) {
        fb_str += factor_base[i].get_str();
        if (i < factor_base.size() - 1) fb_str += ", ";
    }
    print_info("B-Smoothness (Factor Base)", "{" + fb_str + "}");
    return factor_base;
}


