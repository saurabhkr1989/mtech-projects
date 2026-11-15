#include <iostream>
#include <string>
#include <stdexcept>
#include <vector>
#include <gmpxx.h>
#include <mpi.h>
#include <chrono>

#include "utils.h"
#include "safe_prime.h"
#include "generators.h"
#include "test_cases.h"

int main(int argc, char* argv[]) {
    MPI_Init(&argc, &argv);

    int rank, world_size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &world_size);

    if (argc != 2) {
        if (rank == 0) {
            std::cerr << C_BOLD << C_RED << "Usage: " << argv[0] << " <n_bits>" << C_RESET << std::endl;
        }
        MPI_Finalize();
        return 1;
    }

    int n_bits;
    try {
        n_bits = std::stoi(argv[1]);
        if (n_bits < 33) { // 33 bits is roughly a 10-digit number
             if (rank == 0) std::cerr << C_BOLD << C_RED << "Error: Number of bits must be at least 33 for a 10-digit prime." << C_RESET << std::endl;
             MPI_Finalize();
             return 1;
        }
    } catch (const std::exception& e) {
        if (rank == 0) {
            std::cerr << C_BOLD << C_RED << "Invalid number of bits: " << e.what() << C_RESET << std::endl;
        }
        MPI_Finalize();
        return 1;
    }

    if (rank == 0) {
        print_header("Index Calculus Algorithm for DLP");
        print_info("Parallel processes", std::to_string(world_size));
    }
    
    unsigned long seed = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    seed += rank; 
    gmp_randclass rand_state(gmp_randinit_default);
    rand_state.seed(seed);

    mpz_class p;
    std::vector<mpz_class> generators;

    if (rank == 0) {
        generate_safe_prime(p, n_bits, rand_state);
        generators = find_generators(p, 300);
        
        std::string p_str = p.get_str();
        int p_len = p_str.length() + 1;
        MPI_Bcast(&p_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
        MPI_Bcast(const_cast<char*>(p_str.c_str()), p_len, MPI_CHAR, 0, MPI_COMM_WORLD);
        
        int num_gens = generators.size();
        MPI_Bcast(&num_gens, 1, MPI_INT, 0, MPI_COMM_WORLD);
        for(const auto& gen : generators) {
            std::string gen_str = gen.get_str();
            int gen_len = gen_str.length() + 1;
            MPI_Bcast(&gen_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
            MPI_Bcast(const_cast<char*>(gen_str.c_str()), gen_len, MPI_CHAR, 0, MPI_COMM_WORLD);
        }

    } else {
        int p_len;
        MPI_Bcast(&p_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
        char* p_buf = new char[p_len];
        MPI_Bcast(p_buf, p_len, MPI_CHAR, 0, MPI_COMM_WORLD);
        p.set_str(p_buf, 10);
        delete[] p_buf;

        int num_gens;
        MPI_Bcast(&num_gens, 1, MPI_INT, 0, MPI_COMM_WORLD);
        generators.resize(num_gens);
        for(int i = 0; i < num_gens; ++i) {
            int gen_len;
            MPI_Bcast(&gen_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
            char* gen_buf = new char[gen_len];
            MPI_Bcast(gen_buf, gen_len, MPI_CHAR, 0, MPI_COMM_WORLD);
            generators[i].set_str(gen_buf, 10);
            delete[] gen_buf;
        }
    }

    // Pass n_bits to the test cases so it can dynamically adjust parameters.
    run_test_cases(p, generators, rand_state, n_bits);


    MPI_Finalize();
    return 0;
}

