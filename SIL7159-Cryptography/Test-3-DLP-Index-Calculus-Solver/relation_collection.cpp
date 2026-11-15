#include "relation_collection.h"
#include "utils.h"
#include <iostream>
#include <thread>
#include <chrono>

// Tries to factor a number over the factor base.
bool factor_over_base(mpz_class num, const std::vector<mpz_class>& factor_base, std::vector<mpz_class>& exponents) {
    exponents.assign(factor_base.size(), 0);
    for (size_t i = 0; i < factor_base.size(); ++i) {
        if (num == 1) break;
        while (mpz_divisible_p(num.get_mpz_t(), factor_base[i].get_mpz_t())) {
            mpz_divexact(num.get_mpz_t(), num.get_mpz_t(), factor_base[i].get_mpz_t());
            exponents[i]++;
        }
    }
    return num == 1;
}

// Parallel relation collection using MPI.
std::vector<Relation> collect_relations_parallel(const mpz_class& p, const mpz_class& alpha, const std::vector<mpz_class>& factor_base, int required_relations, int rank, int world_size, gmp_randclass& rand_state) {
    std::vector<Relation> collected_relations;
    
    if (rank == 0) {
        // FIX: Add message to inform user about the long wait
        print_step("Starting parallel relation collection...");
        std::cout << C_YELLOW << "[Master] Searching for " << required_relations << " relations. This may take several minutes..." << C_RESET << std::endl;

        int relations_found = 0;
        MPI_Status status;
        
        while (relations_found < required_relations) {
            MPI_Probe(MPI_ANY_SOURCE, 1, MPI_COMM_WORLD, &status);
            int source_rank = status.MPI_SOURCE;

            int relation_len;
            MPI_Get_count(&status, MPI_CHAR, &relation_len);
            char* relation_buf = new char[relation_len];
            MPI_Recv(relation_buf, relation_len, MPI_CHAR, source_rank, 1, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            
            std::string relation_str(relation_buf);
            delete[] relation_buf;

            Relation rel;
            size_t pos = relation_str.find(';');
            rel.k.set_str(relation_str.substr(0, pos), 10);
            relation_str.erase(0, pos + 1);

            rel.exponents.resize(factor_base.size());
            for(size_t i = 0; i < factor_base.size(); ++i) {
                 pos = relation_str.find(',');
                 rel.exponents[i].set_str(relation_str.substr(0, pos), 10);
                 relation_str.erase(0, pos + 1);
            }
            
            collected_relations.push_back(rel);
            relations_found++;

            std::cout << C_CYAN << "\r[Master] Progress: " << relations_found << " / " << required_relations << " relations found..." << C_RESET << std::flush;
        }

        std::cout << std::endl; 

        // Tell all workers to stop
        for (int i = 1; i < world_size; ++i) {
            MPI_Request req;
            MPI_Isend(nullptr, 0, MPI_CHAR, i, 99, MPI_COMM_WORLD, &req);
        }

    } else { 
        bool stop = false;
        MPI_Request stop_request;
        MPI_Irecv(nullptr, 0, MPI_CHAR, 0, 99, MPI_COMM_WORLD, &stop_request);

        while (!stop) {
            mpz_class k = rand_state.get_z_range(p - 1);
            mpz_class result;
            mpz_powm(result.get_mpz_t(), alpha.get_mpz_t(), k.get_mpz_t(), p.get_mpz_t());

            std::vector<mpz_class> exponents;
            if (factor_over_base(result, factor_base, exponents)) {
                std::string relation_str = k.get_str() + ";";
                for(size_t i = 0; i < exponents.size(); ++i) {
                    relation_str += exponents[i].get_str() + ",";
                }
                MPI_Send(relation_str.c_str(), relation_str.length() + 1, MPI_CHAR, 0, 1, MPI_COMM_WORLD);
            }

            int flag = 0;
            MPI_Test(&stop_request, &flag, MPI_STATUS_IGNORE);
            if (flag) {
                stop = true;
            }
        }
    }

    return collected_relations;
}

