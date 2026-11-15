/*
Advance Computer Networks (COL7524)
===Mini Project : Empirical Validation & Extended Analysis of TIMELY Congestion Control Protocol===
Member 1: Lt Col Dey Sanjeetkumar, 	Entry No: 2025JCS2949
Member 2: Lt Col Saurabh Kumar Singh, 	Entry No: 2025JCS3011
*/
// main.cpp
// TIMELY Simulator - Interactive launcher + summary printer

#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <filesystem>
#include <limits>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <map>
#include <cmath>
#include <algorithm>

#include "simulator.h"
#include "timely.h"
#include "utils.h"

namespace fs = std::filesystem;

// ---------- Terminal colors & formatting ----------
#define CLR_YELLOW "\033[1;33m"
#define CLR_GREEN  "\033[1;32m"
#define CLR_RESET  "\033[0m"
#define BOLD_ON    "\033[1m"
#define BOLD_OFF   "\033[0m"

// ---------- Small helpers to parse and compute simple stats from CSVs ----------
static std::vector<std::string> find_csv_files_with_prefix(const std::string &prefix) {
    std::vector<std::string> out;
    const std::string dir = "output/csv";
    if (!fs::exists(dir)) return out;
    for (auto &p : fs::directory_iterator(dir)) {
        if (!p.is_regular_file()) continue;
        std::string name = p.path().filename().string();
        if (name.rfind(prefix, 0) == 0 && name.size() > prefix.size() && name.substr(name.size()-4) == ".csv") {
            out.push_back(p.path().string());
        }
    }
    std::sort(out.begin(), out.end());
    return out;
}

// parse CSV rows: expected header Time_us,SenderID,RTT_us,Rate_Mbps,QueueSize_bits
struct CsvSummary {
    double avg_rtt_us = 0.0;
    double p99_rtt_us = 0.0;
    double avg_throughput_gbps = 0.0;
    double avg_queue_kb = 0.0;
    double jain_index = 0.0;
    long samples = 0;
};

static CsvSummary compute_summary_from_files(const std::vector<std::string>& files) {
    CsvSummary S;
    std::vector<double> all_rtts;
    double total_rate_mbps = 0.0;
    long rate_count = 0;
    double total_queue_bits = 0.0;
    long queue_samples = 0;

    // per-sender accumulation for Jain
    std::map<int, std::vector<double>> per_sender_rates;

    for (auto &f : files) {
        std::ifstream in(f);
        if (!in.is_open()) continue;
        std::string line;
        // header
        if (!std::getline(in, line)) continue;
        while (std::getline(in, line)) {
            if (line.empty()) continue;
            std::stringstream ss(line);
            std::string tok;
            std::vector<std::string> cols;
            while (std::getline(ss, tok, ',')) cols.push_back(tok);
            if (cols.size() < 5) continue;
            
            // safe parse
            // double time_us = atof(cols[0].c_str()); // Removed unused variable
            int sender = atoi(cols[1].c_str());
            double rtt = atof(cols[2].c_str());
            double rate = atof(cols[3].c_str()); // Mbps
            double qbits = atof(cols[4].c_str());

            all_rtts.push_back(rtt);
            total_rate_mbps += rate;
            rate_count++;
            total_queue_bits += qbits;
            queue_samples++;

            per_sender_rates[sender].push_back(rate);
        }
        in.close();
    }

    if (!all_rtts.empty()) {
        double sum = 0.0;
        for (double v : all_rtts) sum += v;
        S.avg_rtt_us = sum / all_rtts.size();
        std::sort(all_rtts.begin(), all_rtts.end());
        size_t idx = (size_t)std::ceil(0.99 * all_rtts.size()) - 1;
        if (idx >= all_rtts.size()) idx = all_rtts.size() - 1;
        S.p99_rtt_us = all_rtts[idx];
    }

    if (rate_count > 0) {
        // total throughput in Gbps approximated as mean of rates * num_senders / 1000
        // Actually rates are per-sender instantaneous and  we report average per-sender and convert
        double mean_rate_per_sender_mbps = total_rate_mbps / rate_count;
        S.avg_throughput_gbps = (mean_rate_per_sender_mbps / 1000.0) * (double)per_sender_rates.size();
    }

    if (queue_samples > 0) {
        S.avg_queue_kb = (total_queue_bits / queue_samples) / 8.0 / 1024.0;
    }

    // Jain's fairness: compute average per sender throughput (Mbps) and jain index
    std::vector<double> avg_per_sender;
    for (auto &kv : per_sender_rates) {
        double sum = 0.0;
        for (double r : kv.second) sum += r;
        if (kv.second.empty()) continue;
        avg_per_sender.push_back(sum / kv.second.size());
    }
    if (!avg_per_sender.empty()) {
        double s1 = 0.0, s2 = 0.0;
        for (double v : avg_per_sender) { s1 += v; s2 += v*v; }
        S.jain_index = (s1*s1) / ((double)avg_per_sender.size() * s2);
    }

    S.samples = rate_count;
    return S;
}

// ---------- UI helpers ----------
void print_bold_yellow(const std::string &s) {
    std::cout << BOLD_ON << CLR_YELLOW << s << CLR_RESET << BOLD_OFF << std::endl;
}
void print_bold_green(const std::string &s) {
    std::cout << BOLD_ON << CLR_GREEN << s << CLR_RESET << BOLD_OFF << std::endl;
}

void showMenu() {
    print_bold_yellow("====== TIMELY Congestion Control Simulator ======");
    std::cout << "Select an experiment to perform:\n";
    std::cout << "  1. TIMELY Throughput vs. Latency (High Load, 40 Senders)\n";
    std::cout << "  2. TIMELY vs. DCTCP Incast (High Load, 40 Senders)\n";
    std::cout << "  3. TIMELY Fairness (Low Load, 10 Senders)\n";
    std::cout << "  4. TIMELY vs. DCTCP Dynamic RTT (High Load, 40 Senders)\n";
    std::cout << "  5. TIMELY vs. DCTCP Mixed Workload (Mice & Elephant)\n";
    std::cout << "  6. TIMELY vs. DCTCP Queue Analysis\n";
    std::cout << "  7. Clear all output data and graphs\n";
    std::cout << "  8. Exit\n";
    print_bold_yellow("==================================================");
}

// Displays the complete experiment setup (entered + defaults)
void display_setup_summary(int choice, const TIMELY::Parameters &params, int repeats, unsigned seed, long nic_noise, char ackprio, int num_senders, long duration) {
    print_bold_green("\n*** EXPERIMENT SETUP SUMMARY ***");
    std::cout << "Experiment ID             : " << choice << "\n";
    std::cout << "Duration (s)              : " << duration << "\n";
    std::cout << "Num Senders               : " << num_senders << "\n";
    std::cout << "Repeats                   : " << repeats << "\n";
    std::cout << "RNG Seed                  : " << seed << "\n";
    std::cout << "NIC timestamp noise (us)  : " << nic_noise << "\n";
    std::cout << "ACK prioritization        : " << (ackprio == 'y' ? "Enabled" : "Disabled") << "\n";
    std::cout << "Segment size (KB)         : " << params.segment_size_kb << "   (TIMELY paper uses segment size approx similar)\n";
    std::cout << "T_low (us)                : " << params.T_low_us << "   (paper: T_low used as lower threshold) \n";
    std::cout << "T_high (us)               : " << params.T_high_us << "   (paper: used as high thresh )\n";
    std::cout << "Additive inc (Mbps)       : " << params.additive_increment_mbps << "\n";
    std::cout << "EWMA weight               : " << params.ewma_weight << "\n";
    std::cout << "Max link rate (Gbps)      : " << params.max_rate_gbps << "\n";
    print_bold_green("*** End of Setup Summary ***\n");
    // debug: // std::cerr << "DBG: Setup printed" << std::endl;
    // debug: // std::cout << "DBG: params.T_low " << params.T_low_us << std::endl;
}

int main() {
    std::vector<std::string> fig_refs = {"15","14","13","16","17","18"};
    bool running = true;

    while (running) {
        showMenu();
        int choice;
        std::cout << "\nEnter your choice (1–8)                                   : ";
        std::cin >> choice;
        if (std::cin.fail()) { std::cin.clear(); std::cin.ignore(10000,'\n'); continue; }

        if (choice >=1 && choice <=6) {
            long duration = 5;
            std::cout << "Enter simulation duration in seconds [Recommended 5]      : ";
            std::string tline; std::getline(std::cin >> std::ws, tline);
            if (!tline.empty()) { try { duration = std::stol(tline); } catch(...) {} }

            int num_senders_override = 0;
            if (choice == 3) {
                std::cout << "Enter number of senders [Recommended 10]                  : ";
            } else {
                std::cout << "\nEnter number of senders [Recommended 40]                  : ";
            }
            std::string tmp; std::getline(std::cin >> std::ws, tmp);
            if (!tmp.empty()) num_senders_override = std::stoi(tmp);

            char param_choice = 'd';
            std::cout << "Use [d]efault tuned parameters or [m]anual input? (d/m)   : ";
            std::cin >> param_choice;

            TIMELY::Parameters params; // defaults (paper-inspired)
            if (param_choice == 'm' || param_choice == 'M') {
                // manual prompts - keep simple
                std::cout << "Segment size (KB) [Recommended 16]            : "; std::cin >> params.segment_size_kb;
                std::cout << "T_low (us) [Recommended 50]                   : "; std::cin >> params.T_low_us;
                std::cout << "T_high (us) [Recommended 500]                 : "; std::cin >> params.T_high_us;
                std::cout << "Additive increment (Mbps) [Recommended 200]   : "; std::cin >> params.additive_increment_mbps;
                std::cout << "EWMA weight [Recommended 0.25]                : "; std::cin >> params.ewma_weight;
                std::cout << "Max link rate (Gbps) [Recommended 20]         : "; std::cin >> params.max_rate_gbps;
            } else {
                // default tuned values (paper like)
                params.segment_size_kb = 16;
                params.T_low_us = 50;
                params.T_high_us = 500;
                params.additive_increment_mbps = 200;
                params.ewma_weight = 0.25;
                params.max_rate_gbps = 20.0;
                //params.use_HAI = true;
            }

            int repeats = 3;
            std::cout << "Enter number of repeats for statistics [Recommended 3]    : ";
            std::string rep_line; std::getline(std::cin >> std::ws, rep_line);
            if (!rep_line.empty()) repeats = std::stoi(rep_line);

            unsigned seed = 0;
            std::cout << "Enter RNG seed (0=time-based) [Recommended 0]             : ";
            std::string seed_line; std::getline(std::cin >> std::ws, seed_line);
            if (!seed_line.empty()) seed = std::stoul(seed_line);

            long nic_noise = 0;
            std::cout << "Add host/NIC timestamp noise (max us) [Recommended 0]     : ";
            std::string noise_line; std::getline(std::cin >> std::ws, noise_line);
            if (!noise_line.empty()) nic_noise = std::stol(noise_line);

            char ackprio = 'n';
            std::cout << "Enable ACK prioritization in switches? (y/n)              : ";
            std::cin >> ackprio;

            int num_senders = (num_senders_override > 0) ? num_senders_override : (choice==3 ? 10 : 40);

            // Print the full setup summary to console (requirement 1)
            display_setup_summary(choice, params, repeats, seed, nic_noise, ackprio, num_senders, duration);

            // Now run the experiment(s)
            const std::string fig_ref = fig_refs.at(choice-1);
            std::string python_command;

            if (choice == 2 || choice == 4 || choice == 5 || choice == 6) {
                print_bold_yellow("\n>>> Running TIMELY Simulation ...");
                Simulator sim_timely(params, choice, duration, num_senders, CCType::CC_TIMELY, repeats, seed);
                sim_timely.setRttNoise(nic_noise);
                sim_timely.enableAckPriority(ackprio == 'y');
                sim_timely.run();  // run all repeats

                print_bold_yellow("\n>>> Running DCTCP Simulation ...");
                Simulator sim_dctcp(params, choice, duration, num_senders, CCType::CC_DCTCP, repeats, seed + 1000);
                sim_dctcp.setRttNoise(nic_noise);
                sim_dctcp.enableAckPriority(ackprio == 'y');
                sim_dctcp.run();

                // generate graphs
                python_command = "python3 generate_graphs.py "
                                 "\"output/csv/exp" + std::to_string(choice) + "_timely_run*.csv\" "
                                 "\"output/csv/exp" + std::to_string(choice) + "_dctcp_run*.csv\" "
                                 + std::to_string(choice) + " " + fig_ref + " \"paper-table\"";
            } else {
                print_bold_yellow("\n>>> Running TIMELY Simulation ...");
                Simulator sim(params, choice, duration, num_senders, CCType::CC_TIMELY, repeats, seed);
                sim.setRttNoise(nic_noise);
                sim.enableAckPriority(ackprio == 'y');
                sim.run();

                python_command = "python3 generate_graphs.py "
                                 "\"output/csv/exp" + std::to_string(choice) + "_timely_run*.csv\" "
                                 "\"\" " + std::to_string(choice) + " " + fig_ref + " \"paper-table\"";
            }

            // call plotting script (keeps previous behaviour)
            // note: ignoring return value intentionally; script prints graph messages
            // debug: // std::cerr << "DBG: Running python command: " << python_command << std::endl;
            if(system(python_command.c_str()) != 0) {
                // Suppress warning, but handle if needed
            }

            // ========= Post-run: Compute quick summary and print (requirement 3)
            print_bold_green("\n*** EXPERIMENT RESULTS SUMMARY ***");

            // TIMELY summary
            std::string timely_prefix = "exp" + std::to_string(choice) + "_timely_run";
            auto timely_files = find_csv_files_with_prefix(timely_prefix);
            if (!timely_files.empty()) {
                CsvSummary s_t = compute_summary_from_files(timely_files);
                print_bold_green("\n*** TIMELY *** \n");
                std::cout << "TIMELY (avg RTT us)           : " << std::fixed << std::setprecision(2) << s_t.avg_rtt_us << " us\n";
                std::cout << "TIMELY (p99 RTT us)           : " << s_t.p99_rtt_us << " us\n";
                std::cout << "TIMELY (avg throughput)       : " << s_t.avg_throughput_gbps << " Gbps\n";
                std::cout << "TIMELY (avg queue)            : " << s_t.avg_queue_kb << " KB\n";
                std::cout << "TIMELY (Jain fairness)        : " << s_t.jain_index << "\n";
            } else {
                std::cout << "TIMELY: No CSV files found to summarise.\n";
            }

            // DCTCP summary if exists
            std::string dctcp_prefix = "exp" + std::to_string(choice) + "_dctcp_run";
            auto dctcp_files = find_csv_files_with_prefix(dctcp_prefix);
            if (!dctcp_files.empty()) {
                CsvSummary s_d = compute_summary_from_files(dctcp_files);
                print_bold_green("\n*** DCTCP *** \n");
                std::cout << "DCTCP (avg RTT us)           : " << s_d.avg_rtt_us << " us\n";
                std::cout << "DCTCP (p99 RTT us)           : " << s_d.p99_rtt_us << " us\n";
                std::cout << "DCTCP (avg throughput)       : " << s_d.avg_throughput_gbps << " Gbps\n";
                std::cout << "DCTCP (avg queue)            : " << s_d.avg_queue_kb << " KB\n";
                std::cout << "DCTCP (Jain fairness)        : " << s_d.jain_index << "\n";
            } else {
                std::cout << "DCTCP: No CSV files found to summarise or not run for this exp.\n";
            }

            print_bold_green("*** End Results Summary ***\n");
            // debug: // std::cout << "DBG: Summary computed and printed\n";
            // debug: // std::cerr << "DBG: timely_files count " << timely_files.size() << std::endl;

        } else if (choice == 7) {
            print_bold_yellow("Clearing output data and graphs...");
            if (fs::exists("output")) fs::remove_all("output");
            std::cout << "Done.\n";
        } else if (choice == 8) {
            print_bold_yellow("Exiting. Bye.");
            running = false;
        } else {
            std::cout << "Invalid choice. Try again.\n";
        }
    }

    return 0;
}