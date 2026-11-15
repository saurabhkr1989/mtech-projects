#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <gmp.h> // For big ints
#include <ctime>
#include <chrono> // timing
#include <thread> // small waits, currently unused
#include <mpi.h>  // parallel

// --- ANSI Color Codes for quick ui ---
#define BOLD_YELLOW "\033[1;33m"
#define RESET_COLOR "\033[0m"

// Vector over GF(q) represented as pointers to mpz_t
using VectorGFq = std::vector<mpz_ptr>;

// --- Data Structure for a single relation ---
// stores k and exponent vector
struct Relation {
    mpz_t k;
    std::vector<long> exponents;
    Relation() { mpz_init(k); }
    ~Relation() { mpz_clear(k); }
    Relation(const Relation& other) { mpz_init_set(k, other.k); exponents = other.exponents; }
    Relation& operator=(const Relation& other) { if (this != &other) { mpz_set(k, other.k); exponents = other.exponents; } return *this; }
};

// --- Helper to free matrix memory ---
// free matrix of mpz_ptr, used in solve and in relation building
void clear_and_free_matrix(std::vector<std::vector<mpz_ptr>>& M) {
    for (auto& row : M) {
        for (auto& ptr : row) {
            mpz_clear(ptr);
            delete[] ptr;
        }
    }
}

// --- Utility Functions for Vector Memory Management (Moved from block_wiedemann.cpp) ---
VectorGFq create_and_init_vector(size_t size) {
    VectorGFq vec(size);
    for (size_t i = 0; i < size; ++i) {
        vec[i] = new __mpz_struct[1];
        mpz_init(vec[i]);
    }
    return vec;
}

void clear_and_free_vector(VectorGFq& vec) {
    for (mpz_ptr ptr : vec) {
        mpz_clear(ptr);
        delete[] ptr;
    }
    vec.clear();
}

// --- Primality Testing and Setup Functions ---
// Miller-Rabin like test
bool is_prime(const mpz_t n, int reps) {
    if (mpz_cmp_ui(n, 2) < 0) return false;
    if (mpz_cmp_ui(n, 2) == 0) return true;
    if (mpz_even_p(n)) return false;

    mpz_t d, n_minus_1, a, x; mpz_inits(d, n_minus_1, a, x, NULL);
    mpz_sub_ui(n_minus_1, n, 1); mpz_set(d, n_minus_1);
    while (mpz_even_p(d)) { mpz_divexact_ui(d, d, 2); }
    gmp_randstate_t state; gmp_randinit_default(state); gmp_randseed_ui(state, time(NULL));
    for (int i = 0; i < reps; ++i) {
        mpz_urandomm(a, state, n_minus_1); mpz_add_ui(a, a, 2);
        mpz_powm(x, a, d, n);
        if (mpz_cmp_ui(x, 1) == 0 || mpz_cmp(x, n_minus_1) == 0) continue;
        mpz_t d_temp; mpz_init_set(d_temp, d);
        while (mpz_cmp(d_temp, n_minus_1) != 0) {
            mpz_powm_ui(x, x, 2, n);
            if (mpz_cmp_ui(x, 1) == 0) { mpz_clears(d, n_minus_1, a, x, d_temp, NULL); gmp_randclear(state); return false; }
            if (mpz_cmp(x, n_minus_1) == 0) break;
            mpz_mul_ui(d_temp, d_temp, 2);
        }
        mpz_clear(d_temp);
        if (mpz_cmp(x, n_minus_1) != 0) { mpz_clears(d, n_minus_1, a, x, NULL); gmp_randclear(state); return false; }
    }
    mpz_clears(d, n_minus_1, a, x, NULL); gmp_randclear(state); return true;
}

// ////////////////////////////////////////////////////////////////////////////
// MODULE: Safe Prime Generation
// ////////////////////////////////////////////////////////////////////////////
void generate_safe_prime(mpz_t p, mpz_t q, int n_bits) {
    gmp_randstate_t state; gmp_randinit_default(state); gmp_randseed_ui(state, time(NULL));
    while (true) {
        mpz_urandomb(q, state, n_bits - 1); mpz_setbit(q, n_bits - 2); mpz_nextprime(q, q);
        mpz_mul_ui(p, q, 2); mpz_add_ui(p, p, 1);
        if (is_prime(p, 40)) break;
    }
    gmp_randclear(state);
}

// ////////////////////////////////////////////////////////////////////////////
// MODULE: Finding Generators of Z_p*
// ////////////////////////////////////////////////////////////////////////////
bool is_generator(const mpz_t g, const mpz_t p, const mpz_t q) {
    if (mpz_cmp_ui(g, 1) <= 0) return false;
    mpz_t res; mpz_init(res);
    mpz_powm_ui(res, g, 2, p);
    if (mpz_cmp_ui(res, 1) == 0) { mpz_clear(res); return false; }
    mpz_powm(res, g, q, p);
    if (mpz_cmp_ui(res, 1) == 0) { mpz_clear(res); return false; }
    mpz_clear(res);
    return true;
}

void find_and_print_generators(mpz_t first_g, const mpz_t p, const mpz_t q) {
    std::vector<std::string> generators; mpz_t g; mpz_init(g); bool first_found = false;
    for (mpz_set_ui(g, 2); mpz_cmp(g, p) < 0; mpz_add_ui(g, g, 1)) {
        if (is_generator(g, p, q)) {
            if (!first_found) { mpz_set(first_g, g); first_found = true; }
            if (generators.size() < 10) { char* g_str = mpz_get_str(NULL, 10, g); generators.push_back(g_str); free(g_str); } else { break; }
        }
    }
    mpz_t gen_count; mpz_init_set(gen_count, q); mpz_sub_ui(gen_count, gen_count, 1);
    gmp_printf("   - Found a total of %Zd generators.\n", gen_count);
    std::cout << "   - Listing first " << generators.size() << " found: { ";
    for(size_t i = 0; i < generators.size(); ++i) { std::cout << generators[i] << (i == generators.size() - 1 ? "" : ", "); }
    std::cout << " }" << std::endl; mpz_clears(g, gen_count, NULL);
}

// ////////////////////////////////////////////////////////////////////////////
// MODULE: Factor Base Generation
// ////////////////////////////////////////////////////////////////////////////
std::vector<long> generate_factor_base(long B) {
    std::vector<long> primes;
    std::vector<bool> is_prime(B + 1, true);
    is_prime[0] = is_prime[1] = false;
    for (long p_sieve = 2; p_sieve * p_sieve <= B; ++p_sieve) {
        if (is_prime[p_sieve]) {
            for (long i = p_sieve * p_sieve; i <= B; i += p_sieve)
                is_prime[i] = false;
        }
    }
    for (long p_sieve = 2; p_sieve <= B; ++p_sieve) {
        if (is_prime[p_sieve])
            primes.push_back(p_sieve);
    }
    return primes;
}

// --- Functions for Relation Finding ---
// trial division using factor base
bool trial_division_gmp(mpz_t n, const std::vector<long>& factor_base, std::vector<long>& exponents) {
    exponents.assign(factor_base.size(), 0); mpz_t temp_n; mpz_init_set(temp_n, n);
    for (size_t i = 0; i < factor_base.size(); ++i) {
        long p_fb = factor_base[i]; while (mpz_divisible_ui_p(temp_n, p_fb)) { exponents[i]++; mpz_divexact_ui(temp_n, temp_n, p_fb); }
    }
    bool is_smooth = (mpz_cmp_ui(temp_n, 1) == 0); mpz_clear(temp_n); return is_smooth;
}

// ////////////////////////////////////////////////////////////////////////////
// MODULE: Parallel Relation Collection
// ////////////////////////////////////////////////////////////////////////////
std::vector<Relation> find_relations_parallel(const mpz_t p, const mpz_t q, const mpz_t alpha, const std::vector<long>& factor_base) {
    int world_rank, world_size;
    MPI_Comm_rank(MPI_COMM_WORLD, &world_rank);
    MPI_Comm_size(MPI_COMM_WORLD, &world_size);

    size_t n = factor_base.size();

    // --- WORKER PROCESS LOGIC ---
    if (world_rank != 0) {
        const int K_STR_TAG = 1;
        const int EXP_VEC_TAG = 2;
        gmp_randstate_t state;
        gmp_randinit_default(state);
        gmp_randseed_ui(state, time(NULL) ^ world_rank);

        mpz_t k, gamma;
        mpz_inits(k, gamma, NULL);

        int stop_flag = 0;
        MPI_Request stop_req;
        MPI_Irecv(&stop_flag, 1, MPI_INT, 0, 0, MPI_COMM_WORLD, &stop_req);

        while (!stop_flag) {
            mpz_urandomm(k, state, q);
            if (mpz_sgn(k) == 0) mpz_add_ui(k, k, 1);
            mpz_powm(gamma, alpha, k, p);
            std::vector<long> exponents;
            if (trial_division_gmp(gamma, factor_base, exponents)) {
                // DEBUG 1: Loggin a successfull relation discovery from worker node, prior to MPI transmittion.
                // gmp_fprintf(stderr, "[DEBUG Worker %d] Found smooth relation for k = %Zd\n", world_rank, k);

                char* k_str = mpz_get_str(NULL, 10, k);
                MPI_Send(k_str, strlen(k_str) + 1, MPI_CHAR, 0, K_STR_TAG, MPI_COMM_WORLD);
                MPI_Send(exponents.data(), n, MPI_LONG, 0, EXP_VEC_TAG, MPI_COMM_WORLD);
                free(k_str);
            }

            int flag_test = 0;
            MPI_Test(&stop_req, &flag_test, MPI_STATUS_IGNORE);
            if (flag_test) {
                stop_flag = 1;
            }
        }
        mpz_clears(k, gamma, NULL);
        gmp_randclear(state);
        return {}; // Workers return empty vector (master collects)
    }

    // --- MASTER (rank 0) / SINGLE-PROCESS LOGIC ---
    std::vector<Relation> all_relations;
    size_t total_needed = n; // need n independent relations

    if (world_size > 1) {
        printf("   - [Master] Waiting for %zu relations...", total_needed);
        fflush(stdout);
    } else {
        std::cout << "   - Running in single-process mode." << std::endl;
    }

    // M stores basis of exponent vectors in row-echolon form
    std::vector<std::vector<mpz_ptr>> M(total_needed);
    std::vector<size_t> pivot_cols(total_needed, -1);
    for(size_t i=0; i<total_needed; ++i) {
        M[i].resize(n);
        for(size_t j=0; j<n; ++j) { M[i][j] = new __mpz_struct[1]; mpz_init(M[i][j]); }
    }

    gmp_randstate_t serial_state;
    if (world_size == 1) {
        gmp_randinit_default(serial_state);
        gmp_randseed_ui(serial_state, time(NULL));
    }

    while(all_relations.size() < total_needed) {
        Relation current_relation;

        if (world_size > 1) {
            // blocking probe to wait for worker
            MPI_Status status;
            MPI_Probe(MPI_ANY_SOURCE, 1, MPI_COMM_WORLD, &status);

            int k_len;
            MPI_Get_count(&status, MPI_CHAR, &k_len);
            char* k_str = new char[k_len];
            MPI_Recv(k_str, k_len, MPI_CHAR, status.MPI_SOURCE, 1, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            mpz_set_str(current_relation.k, k_str, 10);
            delete[] k_str;

            // DEBUG 2: Master has receive a new relation data from one worker, it will be procesed.
            // gmp_fprintf(stderr, "[DEBUG Master] Received relation from worker %d for k = %Zd\n", status.MPI_SOURCE, current_relation.k);

            current_relation.exponents.resize(n);
            MPI_Recv(current_relation.exponents.data(), n, MPI_LONG, status.MPI_SOURCE, 2, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        } else { // single process relation generation
            mpz_t gamma; mpz_init(gamma);
            bool smooth = false;
            while(!smooth) {
                mpz_urandomm(current_relation.k, serial_state, q);
                if (mpz_sgn(current_relation.k) == 0) mpz_add_ui(current_relation.k, current_relation.k, 1);
                mpz_powm(gamma, alpha, current_relation.k, p);
                smooth = trial_division_gmp(gamma, factor_base, current_relation.exponents);
            }
            mpz_clear(gamma);
        }

        size_t rank = all_relations.size();
        VectorGFq new_row = create_and_init_vector(n);
        for(size_t j=0; j<n; ++j) { mpz_init_set_si(new_row[j], current_relation.exponents[j]); }

        // reduce new row by existing basis in M
        for(size_t i=0; i<rank; ++i) {
            size_t p_col = pivot_cols[i];
            if (p_col < n && mpz_sgn(new_row[p_col]) != 0) {
                mpz_t inv, factor;
                mpz_inits(inv, factor, NULL);
                mpz_invert(inv, M[i][p_col], q);
                mpz_mul(factor, new_row[p_col], inv);
                mpz_mod(factor, factor, q);

                for (size_t j = p_col; j < n; ++j) {
                    mpz_t term;
                    mpz_init(term);
                    mpz_mul(term, M[i][j], factor);
                    mpz_sub(new_row[j], new_row[j], term);
                    mpz_mod(new_row[j], new_row[j], q);
                    mpz_clear(term);
                }
                mpz_clears(inv, factor, NULL);
            }
        }

        size_t new_pivot = 0;
        while(new_pivot < n && mpz_sgn(new_row[new_pivot]) == 0) new_pivot++;

        if (new_pivot < n) {
            pivot_cols[rank] = new_pivot;

            mpz_t inv; mpz_init(inv);
            mpz_invert(inv, new_row[new_pivot], q);
            for(size_t j = new_pivot; j < n; ++j) {
                mpz_mul(new_row[j], new_row[j], inv);
                mpz_mod(new_row[j], new_row[j], q);
            }
            mpz_clear(inv);

            for(size_t j = 0; j < n; ++j) mpz_set(M[rank][j], new_row[j]);

            all_relations.push_back(current_relation);
            printf("\r   - [Master] Relations found: %zu / %zu", all_relations.size(), total_needed);
            fflush(stdout);
        }
        clear_and_free_vector(new_row);
    }

    printf("\n   - Relation collection complete.              \n");

    if (world_size > 1) {
        int stop_flag = 1;
        for (int i = 1; i < world_size; ++i) {
            MPI_Send(&stop_flag, 1, MPI_INT, i, 0, MPI_COMM_WORLD);
        }
    }

    clear_and_free_matrix(M);
    return all_relations;
}

// ////////////////////////////////////////////////////////////////////////////
// MODULE: Linear Algebra Solution
// ////////////////////////////////////////////////////////////////////////////
std::vector<mpz_t> solve_linear_system(const std::vector<Relation>& relations, const mpz_t q, size_t fb_size) {
    size_t n = fb_size;
    if (relations.size() < n) {
        std::cerr << "   - ERROR: Not enough relations for Gaussian elimination." << std::endl;
        return {};
    }

    std::vector<std::vector<mpz_ptr>> M(n);
    for(size_t i=0; i<n; ++i) {
        M[i].resize(n + 1);
        for(size_t j=0; j<=n; ++j) {
            M[i][j] = new __mpz_struct[1];
            mpz_init(M[i][j]);
        }
    }

    for(size_t i=0; i<n; ++i) {
        const auto& rel = relations[i];
        for(size_t j=0; j<n; ++j) mpz_set_si(M[i][j], rel.exponents[j]);
        mpz_set(M[i][n], rel.k);
    }

    const char spinner[] = "|/-\\";
    int spinner_idx = 0;

    // Forward elimination
    for (size_t k = 0; k < n; ++k) {
        size_t pivot_row = k;
        while (pivot_row < n && mpz_sgn(M[pivot_row][k]) == 0) pivot_row++;
        if (pivot_row == n) {
            fprintf(stderr, "\n   - ERROR: Matrix is singular. Cannot solve the system.\n");
            clear_and_free_matrix(M);
            return {};
        }
        std::swap(M[k], M[pivot_row]);

        // DEBUG 3: Pivoting operation for the matrix now useing row k as pivot element.
        // fprintf(stderr, "\n[DEBUG LINALG] Pivot selected: row %zu for column %zu\n", pivot_row, k);

        mpz_t inv; mpz_init(inv);
        if (mpz_invert(inv, M[k][k], q) == 0) {
            fprintf(stderr, "\n   - ERROR: mpz_invert failed. Matrix is singular.\n");
            gmp_fprintf(stderr, "     (Failed to invert %Zd mod %Zd)\n", M[k][k], q);
            mpz_clear(inv);
            clear_and_free_matrix(M);
            return {};
        }

        for (size_t j = k; j <= n; ++j) {
            mpz_mul(M[k][j], M[k][j], inv);
            mpz_mod(M[k][j], M[k][j], q);
        }

        for (size_t i = 0; i < n; ++i) {
            if (i != k) {
                mpz_t factor; mpz_init_set(factor, M[i][k]);
                for (size_t j = k; j <= n; ++j) {
                    mpz_t term; mpz_init(term);
                    mpz_mul(term, factor, M[k][j]);
                    mpz_sub(M[i][j], M[i][j], term);
                    mpz_mod(M[i][j], M[i][j], q);
                    mpz_clear(term);
                }
                mpz_clear(factor);
            }
        }
        mpz_clear(inv);

        printf("\r   - Solving system... Step %zu / %zu %c ", k + 1, n, spinner[spinner_idx]);
        fflush(stdout);
        spinner_idx = (spinner_idx + 1) % 4;
    }

    std::vector<mpz_t> log_vector(n);
    for (size_t i = 0; i < n; i++) {
        mpz_init_set(log_vector[i], M[i][n]);
    }

    clear_and_free_matrix(M);
    printf("\n   - Gaussian elimination successful.         \n");
    return log_vector;
}

// ////////////////////////////////////////////////////////////////////////////
// MODULE: Final DLP Computation
// ////////////////////////////////////////////////////////////////////////////
void compute_final_logarithm(mpz_t final_x, const mpz_t beta, const mpz_t alpha, const mpz_t p, const mpz_t q,
                             const std::vector<long>& factor_base, const std::vector<mpz_t>& log_vector) {
    if (log_vector.empty()) { mpz_set_ui(final_x, 0); return; }
    mpz_t s, temp_beta, rhs;
    mpz_inits(s, temp_beta, rhs, NULL);
    gmp_randstate_t state; gmp_randinit_default(state); gmp_randseed_ui(state, time(NULL));

    std::cout << "\n   - Searching for a smooth value of beta * alpha^s..." << std::endl;
    std::vector<long> f_exponents;
    while (true) {
        mpz_urandomm(s, state, q);
        mpz_powm(temp_beta, alpha, s, p); mpz_mul(temp_beta, temp_beta, beta); mpz_mod(temp_beta, temp_beta, p);
        if(trial_division_gmp(temp_beta, factor_base, f_exponents)) {
            gmp_printf("   - Success! Found smooth value with s = %Zd\n", s);
            // DEBUG 4: Intermediate value of s and exponents vector has been finded, proceeding to final calculation.
            // gmp_fprintf(stderr, "[DEBUG Final DLP] Smoothness achieved with s = %Zd\n", s);
            break;
        }
    }

    mpz_set_ui(rhs, 0);
    for (size_t i = 0; i < factor_base.size(); ++i) {
        if (f_exponents[i] != 0) {
            mpz_t term; mpz_init(term);
            mpz_mul_si(term, log_vector[i], f_exponents[i]);
            mpz_add(rhs, rhs, term); mpz_clear(term);
        }
    }
    mpz_mod(rhs, rhs, q);

    mpz_sub(final_x, rhs, s); mpz_mod(final_x, final_x, q);
    mpz_clears(s, temp_beta, rhs, NULL);
}

// verify alpha^x == beta mod p
bool do_verification(const mpz_t alpha, const mpz_t beta, const mpz_t p, const mpz_t x, const std::vector<mpz_t>& log_vector) {
    if (log_vector.empty() || (mpz_sgn(x) == 0 && mpz_cmp_ui(beta, 1) != 0)) {
        return false;
    }
    mpz_t check;
    mpz_init(check);
    mpz_powm(check, alpha, x, p);
    bool success = (mpz_cmp(check, beta) == 0);
    mpz_clear(check);
    return success;
}


int main(int argc, char* argv[]) {
    MPI_Init(&argc, &argv);
    int world_rank, world_size;
    MPI_Comm_rank(MPI_COMM_WORLD, &world_rank);
    MPI_Comm_size(MPI_COMM_WORLD, &world_size);

    bool use_hardcoded = false;
    if (argc > 1 && std::string(argv[1]) == "test") {
        use_hardcoded = true;
    } else if (argc != 2) {
        if(world_rank == 0) std::cerr << "Usage: mpirun -np <num_procs> " << argv[0] << " <n_bits | test>" << std::endl;
        MPI_Finalize();
        return 1;
    }

    int n_bits = use_hardcoded ? 20 : std::stoi(argv[1]);
    if (n_bits < 16 && !use_hardcoded) {
        if(world_rank == 0) std::cerr << "Error: Number of bits must be at least 16." << std::endl;
        MPI_Finalize();
        return 1;
    }

    using clock = std::chrono::high_resolution_clock;
    auto process_start_time = clock::now();

    mpz_t p, q, alpha, suggested_alpha, beta, exponent, final_x;
    mpz_inits(p, q, alpha, suggested_alpha, beta, exponent, final_x, NULL);
    std::vector<long> factor_base;
    long B = 0;

    double setup_time = 0.0;
    std::vector<mpz_t> log_vector;
    bool verification_passed = false;

    if (world_rank == 0) {
        auto start_time = clock::now();
        if (use_hardcoded) {
            std::cout << BOLD_YELLOW << "--- DEBUG MODE: Using hardcoded test case ---" << RESET_COLOR << std::endl;
            mpz_set_ui(p, 23); // small safe prime p = 2*11 + 1
            mpz_set_ui(q, 11); // group order
            mpz_set_ui(alpha, 5); // generator
            mpz_set_ui(beta, 3);  // want x: 5^x = 3 mod 23
            mpz_set_ui(exponent, 16); // known answer
            B = 10; // factor base bound
            factor_base = generate_factor_base(B);
        } else {
            std::cout << BOLD_YELLOW << "--- Discrete Logarithm Problem Solver (Parallel) ---" << RESET_COLOR << std::endl;
            std::cout << BOLD_YELLOW << "\nStep 1: Generating a safe prime..." << RESET_COLOR << std::endl;
            generate_safe_prime(p, q, n_bits);
            gmp_printf("   - Generated Safe Prime p: %Zd\n", p);
            gmp_printf("   - Sophie German Prime q = (p-1)/2: %Zd\n", q);

            std::cout << BOLD_YELLOW << "\nStep 2: Finding generators and setting up problem..." << RESET_COLOR << std::endl;
            find_and_print_generators(suggested_alpha, p, q);

            char choice;
            gmp_printf("\n   The suggested generator is alpha = %Zd.\n", suggested_alpha);
            std::cout << "   Use this generator (y) or manually enter another one (n)? ";
            std::cin >> choice;
            if (choice == 'n' || choice == 'N') {
                char alpha_str[1024];
                while (true) {
                    std::cout << "   - Enter your chosen generator alpha: ";
                    std::cin >> alpha_str;
                    mpz_set_str(alpha, alpha_str, 10);
                    if (is_generator(alpha, p, q)) {
                        std::cout << "   - Alpha validated." << std::endl;
                        break;
                    } else {
                        gmp_printf("   - Error: %Zd is NOT a valid generator.\n", alpha);
                    }
                }
            } else {
                mpz_set(alpha, suggested_alpha);
            }

            std::cout << "\n   Set target Beta (for Beta = alpha^x mod p) automatically (a) or manually (m)? ";
            std::cin >> choice;
            if (choice == 'm' || choice == 'M') {
                char beta_str[1024];
                while (true) {
                    gmp_printf("   - Enter Beta (between 1 and p-1): ");
                    std::cin >> beta_str;
                    mpz_set_str(beta, beta_str, 10);
                    if (mpz_cmp_ui(beta, 1) > 0 && mpz_cmp(beta, p) < 0) {
                        std::cout << "   - Beta validated." << std::endl;
                        break;
                    } else {
                        gmp_printf("   - Error: Beta must be between 1 and p-1.\n");
                    }
                }
                mpz_set_ui(exponent, 0); // exponent unknown if manual

            } else {
                gmp_randstate_t state; gmp_randinit_default(state); gmp_randseed_ui(state, time(NULL));
                mpz_urandomm(exponent, state, q); if (mpz_sgn(exponent) == 0) mpz_add_ui(exponent, exponent, 1);
                mpz_powm(beta, alpha, exponent, p); gmp_randclear(state);
                std::cout << "   - Automatically selected Beta and a secret exponent." << std::endl;
                gmp_printf("   - Secret Exponent is: %Zd\n", exponent);
            }

            std::cout << BOLD_YELLOW << "\nStep 3: Generating the Factor Base..." << RESET_COLOR << std::endl;
            double log_p = mpz_sizeinbase(p, 2) * log(2.0); double log_log_p = log(log_p);
            B = static_cast<long>(exp(0.5 * sqrt(log_p * log_log_p)));
            factor_base = generate_factor_base(B);
            printf("   - Smoothness Bound B (exp(0.5*sqrt(log(p)*log(log(p))))): %ld\n", B);
            std::cout << "   - Factor Base Size: " << factor_base.size() << " primes" << std::endl;

            /*std::cout << "   - Factor Base Primes: { ";
            for(size_t i = 0; i < factor_base.size(); ++i) {
                std::cout << factor_base[i] << (i == factor_base.size() - 1 ? "" : ", ");
            }
            std::cout << " }" << std::endl;*/
        }
        auto end_time = clock::now();
        setup_time = std::chrono::duration<double>(end_time - start_time).count();
    }

    // --- BROADCAST Data to all processes ---
    MPI_Bcast(&B, 1, MPI_LONG, 0, MPI_COMM_WORLD);
    char *p_str = NULL, *q_str = NULL, *alpha_str = NULL;
    int p_len=0, q_len=0, alpha_len=0;
    size_t fb_size=0;
    if(world_rank == 0) {
        p_str = mpz_get_str(NULL, 10, p); p_len = strlen(p_str) + 1;
        q_str = mpz_get_str(NULL, 10, q); q_len = strlen(q_str) + 1;
        alpha_str = mpz_get_str(NULL, 10, alpha); alpha_len = strlen(alpha_str) + 1;
        fb_size = factor_base.size();
    }
    MPI_Bcast(&p_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
    MPI_Bcast(&q_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
    MPI_Bcast(&alpha_len, 1, MPI_INT, 0, MPI_COMM_WORLD);
    if(world_rank != 0) { p_str = new char[p_len]; q_str = new char[q_len]; alpha_str = new char[alpha_len]; }
    MPI_Bcast(p_str, p_len, MPI_CHAR, 0, MPI_COMM_WORLD);
    MPI_Bcast(q_str, q_len, MPI_CHAR, 0, MPI_COMM_WORLD);
    MPI_Bcast(alpha_str, alpha_len, MPI_CHAR, 0, MPI_COMM_WORLD);
    if(world_rank != 0) { mpz_set_str(p, p_str, 10); mpz_set_str(q, q_str, 10); mpz_set_str(alpha, alpha_str, 10); }

    MPI_Bcast(&fb_size, 1, MPI_INT, 0, MPI_COMM_WORLD);
    if(world_rank != 0) factor_base.resize(fb_size);
    MPI_Bcast(factor_base.data(), fb_size, MPI_LONG, 0, MPI_COMM_WORLD);
    if(world_rank==0) { free(p_str); free(q_str); free(alpha_str); } else { delete[] p_str; delete[] q_str; delete[] alpha_str; }

    if (world_rank != 0) {
        // DEBUG 5: Worker validation, printing the prime p receivd from master node for ensure correct MPI_Bcast.
        // gmp_fprintf(stderr, "[DEBUG Worker %d] Broadcast received. Prime p is %Zd\n", world_rank, p);
    }


    // --- Step 4. PARALLEL Relation Finding ---
    if(world_rank == 0) std::cout << BOLD_YELLOW << "\nStep 4: Finding relations (parallel)..." << RESET_COLOR << std::endl;
    auto rel_start_time = clock::now();
    std::vector<Relation> relations = find_relations_parallel(p, q, alpha, factor_base);
    auto rel_end_time = clock::now();
    double rel_time = std::chrono::duration<double>(rel_end_time - rel_start_time).count();

    double linalg_time = 0.0, final_sol_time = 0.0;
    if (world_rank == 0) {
        auto linalg_start_time = clock::now();
        std::cout << BOLD_YELLOW << "\nStep 5: Solving the Linear System of Congruences..." << RESET_COLOR << std::endl;
        log_vector = solve_linear_system(relations, q, factor_base.size());
        auto linalg_end_time = clock::now();
        linalg_time = std::chrono::duration<double>(linalg_end_time - linalg_start_time).count();

        auto final_sol_start_time = clock::now();
        compute_final_logarithm(final_x, beta, alpha, p, q, factor_base, log_vector);
        auto final_sol_end_time = clock::now();
        final_sol_time = std::chrono::duration<double>(final_sol_end_time - final_sol_start_time).count();

        verification_passed = do_verification(alpha, beta, p, final_x, log_vector);

        auto process_end_time = clock::now();
        double total_time = std::chrono::duration<double>(process_end_time - process_start_time).count();

        std::cout << "\n\n" << BOLD_YELLOW << "--- EXECUTION SUMMARY ---" << RESET_COLOR << std::endl;
        std::cout << "-------------------------------------------" << std::endl;
        std::cout << BOLD_YELLOW << "I. Problem Parameters:" << RESET_COLOR << std::endl;
        std::cout << "   - Bit Length: " << n_bits << ", Parallel Processes: " << world_size << std::endl;
        gmp_printf("   - Safe Prime p: %Zd\n", p);
        gmp_printf("   - Group Order q = (p-1)/2: %Zd\n", q);
        gmp_printf("   - Generator alpha: %Zd\n", alpha);
        gmp_printf("   - Target beta: %Zd\n", beta);
        std::cout << BOLD_YELLOW << "\nII. Algorithm Parameters:" << RESET_COLOR << std::endl;
        std::cout << "   - Factor Base Size: " << factor_base.size() << " primes" << std::endl;
        std::cout << "   - Relations Found: " << relations.size() << std::endl;

        std::cout << BOLD_YELLOW << "\nIII. Solution:" << RESET_COLOR << std::endl;
        if(mpz_sgn(exponent) > 0) gmp_printf("   - Original Secret Exponent: %Zd\n", exponent);
        gmp_printf("   - Computed Exponent x: %Zd\n", final_x);

        // --- Verification Details ---
        std::cout << BOLD_YELLOW << "\n   --- Verification of Solution ---" << RESET_COLOR << std::endl;
        if (log_vector.empty() || (mpz_sgn(final_x) == 0 && mpz_cmp_ui(beta, 1) != 0)) {
            std::cout << "   - Verification skipped: No valid solution for x was found." << std::endl;
        } else {
            mpz_t check;
            mpz_init(check);
            mpz_powm(check, alpha, final_x, p);
            gmp_printf("   - Verifying if alpha^x (mod p) == beta\n");
            gmp_printf("   - alpha^x = %Zd^%Zd = %Zd (mod %Zd)\n", alpha, final_x, check, p);
            gmp_printf("   - beta    = %Zd\n", beta);
            printf("   - Status: %s\n", verification_passed ? "SUCCESS" : "FAILURE");
            mpz_clear(check);
        }

        std::cout << BOLD_YELLOW << "\nIV. Performance Metrics (Timings):" << RESET_COLOR << std::endl;
        printf("   - Steps 1-3 (Problem Setup): %.4f seconds\n", setup_time);
        printf("   - Step 4 (Relation Finding): %.4f seconds\n", rel_time);
        printf("   - Step 5 (Linear Algebra):   %.4f seconds\n", linalg_time);
        printf("   - Step 6 (Final Solution):   %.4f seconds\n", final_sol_time);
        printf("   ----------------------------------------\n");
        printf("   - Total Execution Time:    %.4f seconds\n", total_time);
        std::cout << "-------------------------------------------" << std::endl;
    }

    // --- Cleanup ---
    for(auto& log_val : log_vector) mpz_clear(log_val);
    mpz_clears(p, q, alpha, beta, exponent, suggested_alpha, final_x, NULL);
    MPI_Finalize();
    return 0;
}