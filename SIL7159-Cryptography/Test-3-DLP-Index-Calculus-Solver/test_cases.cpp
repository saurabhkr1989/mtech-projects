#include "test_cases.h"
#include "utils.h"
#include "factor_base.h"
#include "relation_collection.h"
#include "linear_algebra.h"
#include "dlp_computation.h"
#include <iostream>
#include <vector>
#include <gmpxx.h>
#include <mpi.h>
#include <limits>
#include <algorithm> // Needed for std::find

// This is a forward declaration. The actual implementation is in this file.
void solve_dlp(const mpz_class& p, const mpz_class& alpha, const mpz_class& beta, gmp_randclass& rand_state, int n_bits);

// Main menu and test case setup
void run_test_cases(const mpz_class& p, const std::vector<mpz_class>& generators, gmp_randclass& rand_state, int n_bits) {
    int rank;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    
    mpz_class alpha, beta;
    bool manual_beta_set = false;

    if (rank == 0) {
        print_header("Manual Problem Setup");
        std::cout << "Available generators for alpha: ";
        for(size_t i = 0; i < generators.size(); ++i) {
            std::cout << generators[i].get_str() << (i == generators.size() - 1 ? "" : ", ");
        }
        std::cout << std::endl;
        
        while(true) {
            std::cout << "1. Enter your choice for alpha from the list above: ";
            std::cin >> alpha;
            if (std::find(generators.begin(), generators.end(), alpha) != generators.end()) break;
            std::cout << "Invalid choice. Please select a generator from the provided list." << std::endl;
            std::cin.clear();
            std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
        }

        char beta_choice;
        std::cout << "2. Do you want to enter beta manually? (y/n): ";
        std::cin >> beta_choice;
        if (beta_choice == 'y' || beta_choice == 'Y') {
            std::cout << "3. Enter beta: ";
            std::cin >> beta;
            manual_beta_set = true;
        }
    }
    
    // Broadcast alpha to all worker processes
    char* alpha_str_buf = nullptr;
    int alpha_len = 0;
    if (rank == 0) {
        std::string alpha_str = alpha.get_str();
        alpha_len = alpha_str.length() + 1;
        alpha_str_buf = const_cast<char*>(alpha_str.c_str());
    }
    MPI_Bcast(&alpha_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
    if (rank != 0) alpha_str_buf = new char[alpha_len];
    MPI_Bcast(alpha_str_buf, alpha_len, MPI_CHAR, 0, MPI_COMM_WORLD);
    if (rank != 0) {
        alpha.set_str(alpha_str_buf, 10);
        delete[] alpha_str_buf;
    }

    // Broadcast the manual beta flag
    MPI_Bcast(&manual_beta_set, 1, MPI_C_BOOL, 0, MPI_COMM_WORLD);

    // If beta was set manually, broadcast it
    if(manual_beta_set) {
        char* beta_str_buf = nullptr;
        int beta_len = 0;
        if (rank == 0) {
            std::string beta_str = beta.get_str();
            beta_len = beta_str.length() + 1;
            beta_str_buf = const_cast<char*>(beta_str.c_str());
        }
        MPI_Bcast(&beta_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
        if (rank != 0) beta_str_buf = new char[beta_len];
        MPI_Bcast(beta_str_buf, beta_len, MPI_CHAR, 0, MPI_COMM_WORLD);
        if (rank != 0) {
            beta.set_str(beta_str_buf, 10);
            delete[] beta_str_buf;
        }
    }


    while(true) {
        int choice = 0;
        if (rank == 0) {
            print_header("Test Case Menu");
            if (manual_beta_set) {
                 std::cout << "0. Display DLP Instance Only (for manual solve)" << std::endl;
            }
            std::cout << "1. Small Exponent Test Case (1-2 digits)" << std::endl;
            std::cout << "2. Medium Exponent Test Case (3 digits)" << std::endl;
            std::cout << "3. Large Exponent Test Case (4 digits)" << std::endl;
            if (!manual_beta_set) std::cout << "4. Manual Entry for beta" << std::endl;
            std::cout << "5. Exit" << std::endl;
            std::cout << "Enter your choice: ";
            
            while(!(std::cin >> choice) || choice < 0 || choice > 5 || (choice == 4 && manual_beta_set) || (choice == 0 && !manual_beta_set)) {
                std::cout << "Invalid choice. Please try again." << std::endl;
                std::cin.clear();
                std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
            }
        }

        MPI_Bcast(&choice, 1, MPI_INT, 0, MPI_COMM_WORLD);

        if (choice == 5) {
            if(rank == 0) print_header("Exiting program.");
            break; 
        }

        if (choice == 0) {
            if (rank == 0) {
                print_header("DLP Instance for Manual Solution");
                print_info("p", p.get_str());
                print_info("alpha", alpha.get_str());
                print_info("beta", beta.get_str());
            }
            MPI_Barrier(MPI_COMM_WORLD);
            continue; // Go back to the menu
        }

        if (rank == 0 && !manual_beta_set) {
            mpz_class x;
            switch (choice) {
                case 1:
                    x = rand_state.get_z_range(mpz_class(100)); // 1-2 digits
                    print_info("Test Case", "Small Exponent");
                    print_info("Secret exponent x (for verification)", x.get_str());
                    break;
                case 2:
                     x = rand_state.get_z_range(mpz_class(1000)); // 3 digits
                    print_info("Test Case", "Medium Exponent");
                    print_info("Secret exponent x (for verification)", x.get_str());
                    break;
                case 3:
                    x = rand_state.get_z_range(mpz_class(10000)); // 4 digits
                    print_info("Test Case", "Large Exponent");
                    print_info("Secret exponent x (for verification)", x.get_str());
                    break;
                case 4:
                    std::cout << "Enter beta: ";
                    std::cin >> beta;
                    manual_beta_set = true; // Mark beta as manually set for this session
                    break;
            }
            if (choice >= 1 && choice <= 3) {
                mpz_powm(beta.get_mpz_t(), alpha.get_mpz_t(), x.get_mpz_t(), p.get_mpz_t());
            }
        }
        
        MPI_Bcast(&manual_beta_set, 1, MPI_C_BOOL, 0, MPI_COMM_WORLD);
        char* beta_str_buf_2 = nullptr;
        int beta_len_2 = 0;
        if (rank == 0) {
            std::string beta_str = beta.get_str();
            beta_len_2 = beta_str.length() + 1;
            beta_str_buf_2 = const_cast<char*>(beta_str.c_str());
        }
        MPI_Bcast(&beta_len_2, 1, MPI_INT, 0, MPI_COMM_WORLD);
        if (rank != 0) beta_str_buf_2 = new char[beta_len_2];
        MPI_Bcast(beta_str_buf_2, beta_len_2, MPI_CHAR, 0, MPI_COMM_WORLD);
        if (rank != 0) {
            beta.set_str(beta_str_buf_2, 10);
            delete[] beta_str_buf_2;
        }

        solve_dlp(p, alpha, beta, rand_state, n_bits);
    }
}

// This function orchestrates the main DLP solving process.
void solve_dlp(const mpz_class& p, const mpz_class& alpha, const mpz_class& beta, gmp_randclass& rand_state, int n_bits) {
    int rank, world_size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &world_size);

    if (rank == 0) {
        print_header("Solving DLP Instance");
        print_info("p", p.get_str());
        print_info("alpha", alpha.get_str());
        print_info("beta", beta.get_str());
    }
    
    // DYNAMIC PARAMETER SELECTION
    int FACTOR_BASE_SIZE;
    int required_relations;

    if (n_bits < 64) { // Heuristic for 10-13 digit primes
        FACTOR_BASE_SIZE = 20;
        required_relations = FACTOR_BASE_SIZE + 5;
    } else { // Heuristic for 30-40 digit primes
        FACTOR_BASE_SIZE = 100;
        required_relations = FACTOR_BASE_SIZE + 10;
    }


    std::vector<mpz_class> factor_base;
    MPI_Barrier(MPI_COMM_WORLD);
    if (rank == 0) {
        print_step("Generating factor base...");
        factor_base = generate_factor_base(FACTOR_BASE_SIZE);
        
        std::cout << C_BLUE << C_BOLD << "  B-Smoothness (Factor Base): {" << C_RESET;
        for(size_t i = 0; i < factor_base.size(); ++i) {
            std::cout << factor_base[i].get_str() << (i == factor_base.size() - 1 ? "" : ", ");
        }
        std::cout << C_BLUE << C_BOLD << "}" << C_RESET << std::endl << std::endl;

        int fb_size = factor_base.size();
        MPI_Bcast(&fb_size, 1, MPI_INT, 0, MPI_COMM_WORLD);
        for(const auto& prime : factor_base) {
            std::string prime_str = prime.get_str();
            int len = prime_str.length() + 1;
            MPI_Bcast(&len, 1, MPI_INT, 0, MPI_COMM_WORLD);
            MPI_Bcast(const_cast<char*>(prime_str.c_str()), len, MPI_CHAR, 0, MPI_COMM_WORLD);
        }
    } else {
        int fb_size;
        MPI_Bcast(&fb_size, 1, MPI_INT, 0, MPI_COMM_WORLD);
        factor_base.resize(fb_size);
        for(int i = 0; i < fb_size; ++i) {
            int len;
            MPI_Bcast(&len, 1, MPI_INT, 0, MPI_COMM_WORLD);
            char* buf = new char[len];
            MPI_Bcast(buf, len, MPI_CHAR, 0, MPI_COMM_WORLD);
            factor_base[i].set_str(buf, 10);
            delete[] buf;
        }
    }
    
    MPI_Barrier(MPI_COMM_WORLD);

    std::vector<Relation> relations;
    std::vector<mpz_class> logs;
    bool success = false;

    while (!success) {
        if (rank == 0) {
            print_step("Stage 1: Collecting smooth relations in parallel...");
        }
        relations = collect_relations_parallel(p, alpha, factor_base, required_relations, rank, world_size, rand_state);

        MPI_Barrier(MPI_COMM_WORLD);

        if (rank == 0) {
            print_step("Stage 2: Solving the linear system of congruences...");
            success = solve_linear_system(logs, relations, p - 1, factor_base.size());

            if (!success) {
                required_relations++; 
                std::cout << C_BOLD << C_YELLOW 
                          << "[Master] Matrix was singular. Collecting 1 more relation (" 
                          << required_relations << " total) and trying again..." 
                          << C_RESET << std::endl;
            }
        }
        MPI_Bcast(&success, 1, MPI_C_BOOL, 0, MPI_COMM_WORLD);
    }


    if (rank == 0) {
        for(size_t i = 0; i < logs.size(); ++i) {
            print_info("log_alpha(" + factor_base[i].get_str() + ")", logs[i].get_str());
        }

        print_step("Stage 3: Computing the final discrete log...");
        mpz_class x;
        compute_final_dlp(x, p, alpha, beta, factor_base, logs, rand_state);

        print_header("DLP Solution");
        print_info("Computed exponent x", x.get_str());
        
        print_step("Verifying the solution (alpha^x mod p)...");
        mpz_class verification;
        mpz_powm(verification.get_mpz_t(), alpha.get_mpz_t(), x.get_mpz_t(), p.get_mpz_t());
        print_info("alpha^x mod p", verification.get_str());
        print_info("beta", beta.get_str());
        if (verification == beta) {
            std::cout << C_BOLD << C_GREEN << "SUCCESS: Verification matches beta." << C_RESET << std::endl;
        } else {
            std::cout << C_BOLD << C_RED << "FAILURE: Verification does not match beta." << C_RESET << std::endl;
        }
    }
    
    MPI_Barrier(MPI_COMM_WORLD);
}

