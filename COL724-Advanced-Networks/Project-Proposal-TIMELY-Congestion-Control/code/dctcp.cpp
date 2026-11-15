/*
Advance Computer Networks (COL7524)
===Mini Project : Empirical Validation & Extended Analysis of TIMELY Congestion Control Protocol===
Member 1: Lt Col Dey Sanjeetkumar, 	Entry No: 2025JCS2949
Member 2: Lt Col Saurabh Kumar Singh, 	Entry No: 2025JCS3011
*/

// dctcp.cpp
// DCTCP congestion control with simulated OS and stack delays

#include "dctcp.h"
#include <algorithm>
#include <iostream>

DCTCP::DCTCP(const Parameters& p, long start)
    : CongestionControl(start),
      params(p),
      rate_mbps(p.max_rate_gbps * 1000.0 / 2.0),  // start half line rate
      alpha(0.0),
      last_rtt_us(0),
      start_time_us(start),
      rng(std::random_device{}()),
      noise_dist(-p.os_stack_delay_jitter_us, p.os_stack_delay_jitter_us) {}


long DCTCP::applyOsStackDelay(long raw_rtt_us) {
    // Apply a constant + jitter delay
    double delay = params.os_stack_delay_mean_us + noise_dist(rng);
    return std::max(1L, raw_rtt_us + static_cast<long>(delay));
}

void DCTCP::onRTTUpdate(long new_rtt_us, bool ecn_marked) 
{

    // Apply artificial OS + stack delay
    new_rtt_us = applyOsStackDelay(new_rtt_us);

    // --- 1. Standard DCTCP Alpha Update ---
    // (Eq. 1 from DCTCP paper)
    double F = ecn_marked ? 1.0 : 0.0;
    alpha = (1.0 - params.alpha_gain) * alpha + params.alpha_gain * F;

    // --- 2. Multiplicative Decrease (Proportional) ---
    // Cut rate based on alpha. 
    double reduction = 1.0 - (alpha / 2.0);
    rate_mbps *= std::clamp(reduction, 0.5, 1.0);

    // --- 3. Additive Increase ---
    // Rate += (MSS / RTT) / Window_in_Segments
    
    double rtt_seconds = new_rtt_us / 1e6;
    
    // safety check
    if (rtt_seconds < 1e-6) rtt_seconds = 1e-6; 

    // Calculate current window size in bits
    double current_window_bits = (rate_mbps * 1e6) * rtt_seconds;
    double segment_bits = params.segment_size_kb * 1024 * 8;
    
    double cwnd_segments = current_window_bits / segment_bits;
    if (cwnd_segments < 1.0) cwnd_segments = 1.0;

    // Increase window
    double increase_bits = segment_bits / cwnd_segments;
    double increase_rate_mbps = (increase_bits / rtt_seconds) / 1e6;
    
    rate_mbps += increase_rate_mbps * params.cwnd_gain;

    // --- 4. Enforce Limits ---
    rate_mbps = std::min(rate_mbps, params.max_rate_gbps * 1000.0);
    rate_mbps = std::max(rate_mbps, 10.0);


    last_rtt_us = new_rtt_us;
}

double DCTCP::getRateMbps() const {
    return rate_mbps;
}

void DCTCP::incrementPacketsSent() {
    ++packets_sent;
}

bool DCTCP::isComplete() const {
    // Logic for Exp 5: Check flow limit
    if (target_flow_size_bytes > 0) {
        long current_bytes = packets_sent * (long)(params.segment_size_kb * 1024);
        if (current_bytes >= target_flow_size_bytes) {
            return true;
        }
    }
    return false;
}

long DCTCP::getStartTime() const {
    return start_time_us;
}

void DCTCP::reset(long new_start_time) {
    CongestionControl::reset(new_start_time);
    // Reset DCTCP state
    rate_mbps = params.max_rate_gbps * 1000.0 / 2.0;
    alpha = 0.0;
    last_rtt_us = 0;
    start_time_us = new_start_time;
}