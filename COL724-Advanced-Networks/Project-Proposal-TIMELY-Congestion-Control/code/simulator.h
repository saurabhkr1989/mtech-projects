/*
Advance Computer Networks (COL7524)
===Mini Project : Empirical Validation & Extended Analysis of TIMELY Congestion Control Protocol===
Member 1: Lt Col Dey Sanjeetkumar, 	Entry No: 2025JCS2949
Member 2: Lt Col Saurabh Kumar Singh, 	Entry No: 2025JCS3011
*/

#ifndef SIMULATOR_H
#define SIMULATOR_H

#include <vector>
#include <queue>
#include <string>
#include <fstream>
#include <memory>
#include <random>
#include "timely.h"
#include "dctcp.h"
#include "CongestionControl.h"

enum CCType { CC_TIMELY, CC_DCTCP };

// Structure to hold simulation results
struct SimResults {
    double aggregate_throughput_gbps = 0.0;
    double avg_rtt_us = 0.0;
    double p99_rtt_us = 0.0;
    double avg_queue_kb = 0.0;
    double jain_index = -1.0;
    double avg_mice_fct_us = -1.0;
    double p99_mice_fct_us = -1.0;
    long completed_mice_flows = 0;
    bool steady_state_reached = true;
};

// Basic packet structure
struct Packet {
    long send_time_us;
    int sender_id;
    bool ecn_marked;
    int hop_index;
    long nic_send_ts_us;
    long nic_completion_ts_us;
    bool is_ack;
};

// Event structure
struct Event {
    long time_us;
    enum Type { PACKET_SENT, PACKET_ARRIVE_SWITCH, PACKET_LEAVE_SWITCH, ACK_ARRIVED, RTT_CHANGE };
    Type type;
    Packet packet;
    Event(long t, Type T, Packet p) : time_us(t), type(T), packet(p) {}
    bool operator>(const Event& other) const { return time_us > other.time_us; }
};

// Switch representation
struct Switch {
    long queue_size_bits = 0;
    long max_queue_bits = 1000 * 1024 * 8;
    long ecn_k_bits = 80 * 1024 * 8;
    bool has_priority_for_acks = false;
};

// ================================================================
// Simulator Class Definition
// ================================================================
class Simulator {
public:
    Simulator(const TIMELY::Parameters& params, int experiment_id, long duration_s,
              int num_senders_override = 0, CCType cca = CCType::CC_TIMELY,
              int runs = 1, unsigned seed = 0);
    ~Simulator(); // Destructor declaration

    void run();
    std::string getCsvFilename() const;
    SimResults getResultsSummary();

    // ======== Accessors & Mutators (Fix for Private Access) ========

    void setRttNoise(long noise_us) { rtt_noise_max_us = noise_us; }
    long getRttNoise() const { return rtt_noise_max_us; }

    void enableAckPriority(bool enable) {
        for (auto &sw : forward_path) sw.has_priority_for_acks = enable;
        for (auto &sw : reverse_path) sw.has_priority_for_acks = enable;
    }

    const std::vector<Switch>& getForwardPath() const { return forward_path; }
    const std::vector<Switch>& getReversePath() const { return reverse_path; }

private:
    TIMELY::Parameters sim_params;
    DCTCP::Parameters dctcp_params;
    int experiment_id;
    long current_time_us;
    std::string csv_filename;
    std::ofstream log_file;
    CCType cca_type;

    // Network topology
    std::vector<Switch> forward_path;
    std::vector<Switch> reverse_path;

    double link_speed_bps;
    std::priority_queue<Event, std::vector<Event>, std::greater<Event>> event_queue;
    
    // Changed to raw pointers to match manual memory management in .cpp
    std::vector<CongestionControl*> senders;
    std::vector<long> fct_log;

    long propagation_delay_us;
    long simulation_duration_us;
    int num_senders;

    // Random and noise controls
    int runs_count;
    unsigned rng_seed;
    std::mt19937_64 rng;

    long rtt_noise_max_us = 0; // noise amplitude
    double nic_pacer_bps = 0.0;

    // Internal simulation helpers
    void scheduleEvent(const Event& event);
    void initSimulation();
    void logState(long rtt, int sender_id);
    void handlePacketSent(const Event& event);
    void handlePacketArriveSwitch(const Event& event);
    void handlePacketLeaveSwitch(const Event& event);
    void handleAckArrived(const Event& event);
    void handleRttChange(const Event& event);
    long calc_transmission_delay_us(long bits) const;
    long sample_noise_us();
};

#endif // SIMULATOR_H