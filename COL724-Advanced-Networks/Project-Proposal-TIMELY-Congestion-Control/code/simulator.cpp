/*
Advance Computer Networks (COL7524)
===Mini Project : Empirical Validation & Extended Analysis of TIMELY Congestion Control Protocol===
Member 1: Lt Col Dey Sanjeetkumar, 	Entry No: 2025JCS2949
Member 2: Lt Col Saurabh Kumar Singh, 	Entry No: 2025JCS3011
*/

// simulator.cpp
// This file simulate packet events for Timely like algorithm.
// Based on ideas from TIMELY SIGCOMM 2015 section 4 (Evaluation).

#include "simulator.h"
#include "utils.h"
#include <iostream>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <filesystem>   
namespace fs = std::filesystem;  

using namespace std;

// ---------------------- helpers -----------------------
long Simulator::calc_transmission_delay_us(long bits) const {
    if (link_speed_bps <= 0) return 0;
    double usec = (double)bits * 1e6 / link_speed_bps;
    if (usec < 1.0) return 1;
    return (long)usec;
}

long Simulator::sample_noise_us() {
    if (rtt_noise_max_us <= 0) return 0;
    std::uniform_int_distribution<long> dist(0, rtt_noise_max_us);
    return dist(rng);
}

// ---------------------- constructor -----------------------
Simulator::Simulator(const TIMELY::Parameters& base_params,
                     int experiment_id_, long duration_s,
                     int num_senders_override,
                     CCType cca, int runs, unsigned seed)
    : sim_params(base_params),
      dctcp_params(),
      experiment_id(experiment_id_),
      current_time_us(0),
      csv_filename(""),
      cca_type(cca),
      propagation_delay_us(10),
      simulation_duration_us(duration_s * 1000000L),
      num_senders(0),
      runs_count(std::max(1, runs)),
      rng_seed(seed),
      // Fixed initialization order to match header declaration
      link_speed_bps(0),       
      rtt_noise_max_us(0),     
      nic_pacer_bps(0.0),
      rng(seed)
{
    link_speed_bps = sim_params.max_rate_gbps * 1e9;

    // make simple two switch path (like small DC fabric)
    forward_path.clear();
    reverse_path.clear();
    Switch s1, s2;
    s1.max_queue_bits = 300 * 1024 * 8;
    s2.max_queue_bits = 300 * 1024 * 8;
    s1.ecn_k_bits = 64 * 1024 * 8;
    s2.ecn_k_bits = 64 * 1024 * 8;
    forward_path.push_back(s1);
    forward_path.push_back(s2);
    reverse_path = forward_path;

    if (num_senders_override > 0) num_senders = num_senders_override;
    else num_senders = (experiment_id == 3 ? 10 : 40);

    // parameter tuning as paper hint section 5
    if (num_senders <= 10) {
        sim_params.additive_increment_mbps = 1.0;
        sim_params.ewma_weight = 0.5;
    } else {
        sim_params.additive_increment_mbps = 180.0;
        sim_params.ewma_weight = 0.25;
    }

    if (rng_seed == 0)
        rng_seed = (unsigned) chrono::system_clock::now().time_since_epoch().count();
}

// Destructor to clean up manual pointers
Simulator::~Simulator() {
    for (auto p : senders) {
        if (p) delete p;
    }
    senders.clear();
}

// ---------------------- internal init -----------------------
void Simulator::initSimulation() {
    fs::create_directories("output/csv");  
    while (!event_queue.empty()) event_queue.pop();
    
    // Clean up old pointers if any
    for(auto ptr : senders) {
        delete ptr;
    }
    senders.clear();
    fct_log.clear();
}

// log state line
void Simulator::logState(long rtt, int sender_id) {
    if (!log_file.is_open()) return;
    double rate_mbps = 0.0;
    
    // check index bounds
    if (sender_id >= 0 && sender_id < (int)senders.size())
        rate_mbps = senders[sender_id]->getRateMbps();

    long total_q_bits = 0;
    for (auto &sw : forward_path) total_q_bits += sw.queue_size_bits;

    // printf("debug: log state %ld\n", current_time_us);

    log_file << current_time_us << "," << sender_id << "," << rtt << ","
             << rate_mbps << "," << total_q_bits << "\n";
}

// schedule event
void Simulator::scheduleEvent(const Event& e) {
    event_queue.push(e);
}

// ---------------------- send/recv handlers -----------------------
void Simulator::handlePacketSent(const Event& e) {
    Packet p = e.packet;
    p.send_time_us = e.time_us;
    p.hop_index = 0;
    p.is_ack = false;
    p.nic_send_ts_us = e.time_us + sample_noise_us();

    long bits = sim_params.segment_size_kb * 1024 * 8;
    long tx_us = calc_transmission_delay_us(bits); // TODO: optimize this calc
    
    Event ev(e.time_us + tx_us + propagation_delay_us, Event::PACKET_ARRIVE_SWITCH, p);
    scheduleEvent(ev);
}

void Simulator::handlePacketArriveSwitch(const Event& e) {
    Packet p = e.packet;
    if (p.is_ack) {
        int hop = p.hop_index;
        if (hop < 0) {
            Event ack(e.time_us + propagation_delay_us, Event::ACK_ARRIVED, p);
            scheduleEvent(ack);
            return;
        }
        Switch &sw = reverse_path[hop];
        long bits = 64 * 8;
        long delay = calc_transmission_delay_us(bits);
        if (sw.has_priority_for_acks) delay = std::max(1L, delay / 4);
        sw.queue_size_bits += bits;
        Event leave(e.time_us + delay, Event::PACKET_LEAVE_SWITCH, p);
        scheduleEvent(leave);
    } else {
        int hop = p.hop_index;
        if (hop >= (int)forward_path.size()) {
            Packet ack = p;
            ack.is_ack = true;
            ack.nic_completion_ts_us = e.time_us + sample_noise_us();
            ack.hop_index = (int)reverse_path.size() - 1;
            long ack_tx = calc_transmission_delay_us(64 * 8);
            scheduleEvent(Event(e.time_us + ack_tx + propagation_delay_us,
                                Event::PACKET_ARRIVE_SWITCH, ack));
            return;
        }

        Switch &sw = forward_path[hop];
        long bits = sim_params.segment_size_kb * 1024 * 8;
        
        // check if queue is full
        if (sw.queue_size_bits + bits > sw.max_queue_bits) {
            long backoff = 2 * calc_transmission_delay_us(bits);
            scheduleEvent(Event(e.time_us + backoff, Event::PACKET_SENT, p));
            return;
        } else {
            if (sw.queue_size_bits + bits > sw.ecn_k_bits) p.ecn_marked = true;
            else p.ecn_marked = false;
            sw.queue_size_bits += bits;
        }
        long leave_delay = calc_transmission_delay_us(bits);
        if (sw.queue_size_bits > bits)
            leave_delay += (long)((double)(sw.queue_size_bits - bits) * 1e6 / link_speed_bps);
        Event leave(e.time_us + leave_delay + propagation_delay_us, Event::PACKET_LEAVE_SWITCH, p);
        scheduleEvent(leave);
    }
}

void Simulator::handlePacketLeaveSwitch(const Event& e) 
{
    Packet p = e.packet;
    if (p.is_ack) {
        int hop = p.hop_index;
        if (hop >= 0 && hop < (int)reverse_path.size()) {
            long bits = 64 * 8;
            reverse_path[hop].queue_size_bits = max(0L, reverse_path[hop].queue_size_bits - bits);
            p.hop_index = hop - 1;
            long tx = calc_transmission_delay_us(bits);
            scheduleEvent(Event(e.time_us + tx + propagation_delay_us, Event::PACKET_ARRIVE_SWITCH, p));
        } else {
            scheduleEvent(Event(e.time_us + propagation_delay_us, Event::ACK_ARRIVED, p));
        }
    } else {
        int hop = p.hop_index;
        if (hop >= 0 && hop < (int)forward_path.size()) {
            long bits = sim_params.segment_size_kb * 1024 * 8;
            forward_path[hop].queue_size_bits = max(0L, forward_path[hop].queue_size_bits - bits);
        }
        p.hop_index++;
        long tx = calc_transmission_delay_us(sim_params.segment_size_kb * 1024 * 8);
        scheduleEvent(Event(e.time_us + tx + propagation_delay_us, Event::PACKET_ARRIVE_SWITCH, p));
    }
}

void Simulator::handleAckArrived(const Event& e) {
    Packet p = e.packet;
    long comp = (p.nic_completion_ts_us > 0 && p.nic_send_ts_us > 0)
                    ? p.nic_completion_ts_us - p.nic_send_ts_us
                    : e.time_us - p.send_time_us;
    
    // Repair_this_later: check negative values
    if (comp < 0) comp = 0;

    int s = p.sender_id;
    if (s < 0 || s >= (int)senders.size()) return;
    
    senders[s]->onRTTUpdate(comp, p.ecn_marked);
    senders[s]->incrementPacketsSent();
    logState(comp, s);

    double rate = senders[s]->getRateMbps();
    long delay = 1000;
    if (rate > 0.0) {
        long bits = sim_params.segment_size_kb * 1024 * 8;
        double sec = bits / (rate * 1e6);
        delay = (long)(sec * 1e6);
        if (delay < 1) delay = 1;
    }

    if (!senders[s]->isComplete()) {
        Packet np{0, s, false, 0, 0, 0, false};
        scheduleEvent(Event(e.time_us + delay, Event::PACKET_SENT, np));
    } else {
        // log flow completion time
        fct_log.push_back(e.time_us - senders[s]->getStartTime());
        
        // === FIX for Exp 5: Regenerate Mice Flows ===
        // If this is Experiment 5 and it's a Finite (Mice) flow, restart it
        if (experiment_id == 5 && senders[s]->isFiniteFlow()) {
            // Generate random think time (e.g., 10ms - 50ms)
            long think_time_us = 10000 + (rng() % 40000);
            long new_start = e.time_us + think_time_us;
            
            // Only restart if new start time is within simulation duration
            if (new_start < simulation_duration_us) {
                senders[s]->reset(new_start);
                Packet np{0, s, false, 0, 0, 0, false};
                scheduleEvent(Event(new_start, Event::PACKET_SENT, np));
            }
        }
    }
}

void Simulator::handleRttChange(const Event&) {
    // increase delay to emulate path change or new congestion
    propagation_delay_us += 40;
    // std::cout << "Debug: RTT changed" << endl;
}

// ---------------------- runner -----------------------
void Simulator::run() {
    for (int run = 0; run < runs_count; ++run) {
        rng.seed(rng_seed + run);
        string cca_name = (cca_type == CCType::CC_TIMELY) ? "timely" : "dctcp";
        csv_filename = "output/csv/exp" + to_string(experiment_id) + "_" + cca_name + "_run" + to_string(run) + ".csv";

        initSimulation();
        log_file.open(csv_filename);
        log_file << "Time_us,SenderID,RTT_us,Rate_Mbps,QueueSize_bits\n";

        // Manual memory management here
        senders.clear();

        // using while loop instead of for loop for senders init
        int i = 0;
        while(i < num_senders) {
            long start = i * 5 + run;
            CongestionControl* cc = nullptr;

            if (cca_type == CCType::CC_TIMELY)
                cc = new TIMELY(sim_params, start);
            else
                cc = new DCTCP(dctcp_params, start);
            
            // === Experiment 5: Mixed Workload (Mice + Elephants) ===
            // Logic: First 2 senders are Elephants (Infinite), rest are Mice (Fixed size)
            if (experiment_id == 5) {
                if (i < 2) {
                    cc->setFlowSize(0); // Elephant: Infinite
                } else {
                    cc->setFlowSize(200 * 1024); // Mice: 200KB
                }
            }

            senders.push_back(cc);

            long jitter = rng() % 200;
            Packet p{0, i, false, 0, 0, 0, false};
            scheduleEvent(Event(start + jitter, Event::PACKET_SENT, p));

            i++; // increment index
        }

        if (experiment_id == 4)
            scheduleEvent(Event(simulation_duration_us/2, Event::RTT_CHANGE, Packet{}));

        current_time_us = 0;
        long last_status = 0;
        long next_qlog = 0;

        while (!event_queue.empty()) {
            Event ev = event_queue.top(); event_queue.pop();
            if (ev.time_us > simulation_duration_us) break;
            current_time_us = ev.time_us;

            switch (ev.type) {
                case Event::PACKET_SENT: handlePacketSent(ev); break;
                case Event::PACKET_ARRIVE_SWITCH: handlePacketArriveSwitch(ev); break;
                case Event::PACKET_LEAVE_SWITCH: handlePacketLeaveSwitch(ev); break;
                case Event::ACK_ARRIVED: handleAckArrived(ev); break;
                case Event::RTT_CHANGE: handleRttChange(ev); break;
            }

            if (current_time_us >= next_qlog) {
                long tq = 0;
                for (auto &sw : forward_path) tq += sw.queue_size_bits;
               log_file << current_time_us << ",-1,0,0," << tq << "\n";
                next_qlog = current_time_us + 10000;
            }

            if (current_time_us - last_status >= 500000) {
                cout << "Run " << run << " Sim Time: " << fixed << setprecision(2)
                     << current_time_us/1e6 << "s / " << simulation_duration_us/1e6 << "s\n";
                last_status = current_time_us;
            }
        }
        log_file.close();
        
        // cleanup pointers manually
        for(auto ptr : senders) {
            delete ptr;
        }
        senders.clear();
        
        cout << "Simulation run finished. CSV: " << csv_filename << "\n";
    }
    cout << "All runs complete. Use generate_graphs.py to visualize results.\n";
}

string Simulator::getCsvFilename() const { return csv_filename; }
SimResults Simulator::getResultsSummary() { SimResults r; return r; }