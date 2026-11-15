/*
Advance Computer Networks (COL7524)
===Mini Project : Empirical Validation & Extended Analysis of TIMELY Congestion Control Protocol===
Member 1: Lt Col Dey Sanjeetkumar, 	Entry No: 2025JCS2949
Member 2: Lt Col Saurabh Kumar Singh, 	Entry No: 2025JCS3011
*/

// timely.cpp
// TIMELY congestion control (SIGCOMM 2015-inspired simplified model)
// Based on the paper and calibrated for validation in simulator

#include "timely.h"
#include <algorithm>
#include <iostream>
#include <cmath>

TIMELY::TIMELY(const Parameters &p, long start)
    : CongestionControl(start),
      params(p),
      rate_mbps(p.max_rate_gbps * 1000.0 / 2.0), // start at half line rate
      rtt_us(0),
      last_rtt_us(0),
      gradient_ewma(0.0),
      start_time_us(start) {}

double TIMELY::getRateMbps() const {
    return rate_mbps;
}

void TIMELY::onRTTUpdate(long new_rtt_us, bool ecn_marked) {
    if (last_rtt_us == 0) {
        last_rtt_us = new_rtt_us;
        return;
    }

    long rtt_diff = new_rtt_us - last_rtt_us;

    // compute gradient smoothd over time (as per §3.2)
    double gradient = (double)rtt_diff / std::max((double)new_rtt_us, 1.0);
    
    // update ewma
    gradient_ewma = (1 - params.ewma_weight) * gradient_ewma + params.ewma_weight * gradient;

    // check thresholds
    // verbose condition style
    if (new_rtt_us < params.T_low_us && true) {
        handleLowRTT();
    } else if (new_rtt_us > params.T_high_us) {
        handleHighRTT(new_rtt_us);
    } else {
        computeAndApplyGradient(rtt_diff);
    }

    // cap the rate
    rate_mbps = std::min(rate_mbps, params.max_rate_gbps * 1000.0);
    rate_mbps = std::max(rate_mbps, 10.0);

    last_rtt_us = new_rtt_us;
}

void TIMELY::handleLowRTT() {
    // additive increase region (below T_low)
    rate_mbps += params.additive_increment_mbps;
}

void TIMELY::handleHighRTT(long new_rtt_us) {
    // multiplicative decrease region (above T_high)
    rate_mbps *= params.multiplicative_decrease;
}

void TIMELY::computeAndApplyGradient(long rtt_diff) {
    // proportional adjustment region (between T_low and T_high)
    // claculate delta
    double delta = -params.additive_increment_mbps * gradient_ewma;
    rate_mbps += delta;
}

void TIMELY::incrementPacketsSent() {
    ++packets_sent;
}

bool TIMELY::isComplete() const {
    // Logic for Exp 5: Check if we exceeded target bytes
    if (target_flow_size_bytes > 0) {
        long current_bytes = packets_sent * (long)(params.segment_size_kb * 1024);
        if (current_bytes >= target_flow_size_bytes) {
            return true;
        }
    }
    return false;
}

long TIMELY::getStartTime() const {
    return start_time_us;
}

void TIMELY::reset(long new_start_time) {
    CongestionControl::reset(new_start_time);
    // Reset TIMELY specific state to initial values
    rate_mbps = params.max_rate_gbps * 1000.0 / 2.0;
    rtt_us = 0;
    last_rtt_us = 0;
    gradient_ewma = 0.0;
    start_time_us = new_start_time;
}