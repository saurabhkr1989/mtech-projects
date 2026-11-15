/*
Advance Computer Networks (COL7524)
===Mini Project : Empirical Validation & Extended Analysis of TIMELY Congestion Control Protocol===
Member 1: Lt Col Dey Sanjeetkumar, 	Entry No: 2025JCS2949
Member 2: Lt Col Saurabh Kumar Singh, 	Entry No: 2025JCS3011
*/
// timely.h
// TIMELY congestion control implementation header (SIGCOMM 2015-inspired)

#ifndef TIMELY_H
#define TIMELY_H

#include "CongestionControl.h"
#include <cmath>
#include <vector>

class TIMELY : public CongestionControl {
public:
    struct Parameters {
        long T_low_us = 50;                   // lower RTT threshold (µs)
        long T_high_us = 500;                 // upper RTT threshold (µs)
        double additive_increment_mbps = 500; // additive increment (Mbps)
        double multiplicative_decrease = 0.8; // multiplicative decrease factor
        double ewma_weight = 0.875;             // weight for RTT gradient smoothing
        double max_rate_gbps = 20.0;          // line rate cap
        double segment_size_kb = 16.0;        // approximate segment size
    };

    explicit TIMELY(const Parameters &params, long start_time);

    void onRTTUpdate(long new_rtt_us, bool ecn_marked) override;
    double getRateMbps() const override;
    void incrementPacketsSent() override;
    bool isComplete() const override;
    long getStartTime() const override;
    
    // Added reset for Exp 5
    void reset(long new_start_time) override;

private:
    Parameters params;
    double rate_mbps;         // current sending rate
    long rtt_us;              // current RTT
    long last_rtt_us;         // last RTT
    double gradient_ewma;     // smoothed RTT gradient
    long start_time_us;       // simulation start time

    void handleLowRTT();
    void handleHighRTT(long new_rtt_us);
    void computeAndApplyGradient(long rtt_diff);
};

#endif