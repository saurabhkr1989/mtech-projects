#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <iomanip>
#include <memory>
#include <limits>

using namespace std;

// Terminal colors for styled output
const string CLR_RESET = "\033[0m";
const string CLR_BOLD = "\033[1m";
const string CLR_RED = "\033[31m";
const string CLR_GREEN = "\033[32m";
const string CLR_YELLOW = "\033[33m";
const string CLR_BLUE = "\033[34m";

// A data packet representing a client's request
struct RequestPacket {
    int client_fd = -1;
    enum { CMD_GET, CMD_PUT, CMD_NONE } type;
    string filename_on_server;
    long f_size = 0;
    int client_thread_id = 0;
    int total_client_threads = 0;
    int lines_processed = 0;
    bool is_new_task = true;
    chrono::steady_clock::time_point arrival_t;
    chrono::steady_clock::time_point start_t;
    chrono::steady_clock::time_point finish_t;
    bool operator>(const RequestPacket& other) const {
        return f_size > other.f_size;
    }
};

// A simple thread-safe queue.
template <typename T>
class ConcurrentQueue {
public:
    void push_item(T item) {
        lock_guard<mutex> lock(queue_mutex);
        internal_queue.push(item);
        // UPDATED: Notify all waiting threads, not just one.
        condition.notify_all();
    }
    T pull_item() {
        unique_lock<mutex> lock(queue_mutex);
        condition.wait(lock, [this]{ return !internal_queue.empty(); });
        T item = internal_queue.front();
        internal_queue.pop();
        return item;
    }
private:
    queue<T> internal_queue;
    mutex queue_mutex;
    condition_variable condition;
};

// Base class for all schedulers
class BaseScheduler {
public:
    virtual ~BaseScheduler() = default;
    virtual void add(RequestPacket task) = 0;
    virtual RequestPacket get_next() = 0;
};

// FCFS Scheduler: Now robustly handles multiple workers.
class Scheduler_FCFS : public BaseScheduler {
    ConcurrentQueue<RequestPacket> q;
public:
    void add(RequestPacket task) override { q.push_item(task); }
    RequestPacket get_next() override { return q.pull_item(); }
};

// SJF Scheduler: Now robustly handles multiple workers.
class Scheduler_SJF : public BaseScheduler {
    priority_queue<RequestPacket, vector<RequestPacket>, greater<RequestPacket>> pq;
    mutex m;
    condition_variable cv;
public:
    void add(RequestPacket task) override {
        lock_guard<mutex> lock(m);
        pq.push(task);
        // UPDATED: Notify all waiting threads, not just one.
        cv.notify_all();
    }
    RequestPacket get_next() override {
        unique_lock<mutex> lock(m);
        cv.wait(lock, [this]{ return !pq.empty(); });
        RequestPacket task = pq.top();
        pq.pop();
        return task;
    }
};

// RR Scheduler: Now robustly handles multiple workers.
class Scheduler_RR : public BaseScheduler {
    ConcurrentQueue<RequestPacket> q;
public:
    void add(RequestPacket task) override { q.push_item(task); }
    RequestPacket get_next() override { return q.pull_item(); }
};