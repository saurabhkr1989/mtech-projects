/*
Advance Computer Networks (COL7524)
===Mini Project : Empirical Validation & Extended Analysis of TIMELY Congestion Control Protocol===
Member 1: Lt Col Dey Sanjeetkumar, 	Entry No: 2025JCS2949
Member 2: Lt Col Saurabh Kumar Singh, 	Entry No: 2025JCS3011
*/
// dctcp.h
// Simplified DCTCP congestion control implementation

#ifndef DCTCP_H
#define DCTCP_H

#include "CongestionControl.h"
#include <cmath>
#include <random>

class DCTCP : public CongestionControl {
public:
    struct Parameters {
        double alpha_gain = 0.0625;  // g factor
        double cwnd_gain = 1.0;      // cwnd adjustment scaling
        double max_rate_gbps = 20.0; // link capacity
        double segment_size_kb = 16.0;
        double os_stack_delay_mean_us = 60.0;  // mean OS+stack delay (µs)
        double os_stack_delay_jitter_us = 10.0; // uniform ± jitter
    };

    explicit DCTCP(const Parameters& p, long start_time);

    void onRTTUpdate(long new_rtt_us, bool ecn_marked) override;
    double getRateMbps() const override;
    void incrementPacketsSent() override;
    bool isComplete() const override;
    long getStartTime() const override;
    
    // Added reset for Exp 5
    void reset(long new_start_time) override;

private:
    Parameters params;
    double rate_mbps;
    double alpha;
    long last_rtt_us;
    long start_time_us;

    std::mt19937_64 rng;
    std::uniform_real_distribution<double> noise_dist;

    long applyOsStackDelay(long raw_rtt_us);
};

#endif