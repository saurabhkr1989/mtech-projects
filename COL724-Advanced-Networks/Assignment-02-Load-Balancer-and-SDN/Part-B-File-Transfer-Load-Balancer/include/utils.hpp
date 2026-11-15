#ifndef UTILS_HPP
#define UTILS_HPP

#include <string>
#include <vector>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <chrono>

// --- ANSI Color Codes for Logging ---
#define CLR_RESET   "\033[0m"
#define CLR_RED     "\033[1;31m"
#define CLR_GREEN   "\033[1;32m"
#define CLR_YELLOW  "\033[1;33m"
#define CLR_BLUE    "\033[1;34m"
#define CLR_BOLD    "\033[1m"

// --- Request Packet Structure ---
struct RequestPacket {
    enum CommandType { CMD_NONE, CMD_GET, CMD_PUT };
    
    CommandType type = CMD_NONE;
    int client_fd = -1;
    std::string filename_on_server;
    long long f_size = 0;
    
    // Timing information
    std::chrono::steady_clock::time_point arrival_t_lb; // Arrival time at Load Balancer
    std::chrono::steady_clock::time_point arrival_t;    // Arrival time at this Server
    std::chrono::steady_clock::time_point start_t;
    std::chrono::steady_clock::time_point finish_t;
    
    // Client and Server metadata
    int server_id = 0;
    int client_thread_id = 0;
    int total_client_threads = 0;
    std::string lb_sched_policy; // Added this field

    // For Round-Robin state
    int lines_processed = 0;
    bool is_new_task = true;
};


// --- Base Scheduler Class ---
class BaseScheduler {
public:
    virtual ~BaseScheduler() = default;
    virtual void add(RequestPacket task) = 0;
    virtual RequestPacket get_next() = 0;

protected:
    std::queue<RequestPacket> task_queue;
    std::mutex queue_mutex;
    std::condition_variable cv;
};

// --- FCFS Scheduler ---
class Scheduler_FCFS : public BaseScheduler {
public:
    void add(RequestPacket task) override {
        std::unique_lock<std::mutex> lock(queue_mutex);
        task_queue.push(task);
        lock.unlock();
        cv.notify_one();
    }

    RequestPacket get_next() override {
        std::unique_lock<std::mutex> lock(queue_mutex);
        cv.wait(lock, [this] { return !task_queue.empty(); });
        RequestPacket task = task_queue.front();
        task_queue.pop();
        return task;
    }
};

// --- SJF Scheduler ---
class Scheduler_SJF : public BaseScheduler {
private:
    std::vector<RequestPacket> task_vec;

public:
    void add(RequestPacket task) override {
        std::unique_lock<std::mutex> lock(queue_mutex);
        task_vec.push_back(task);
        lock.unlock();
        cv.notify_one();
    }

    RequestPacket get_next() override {
        std::unique_lock<std::mutex> lock(queue_mutex);
        cv.wait(lock, [this] { return !task_vec.empty(); });
        
        auto it_to_min = task_vec.begin();
        for (auto it = task_vec.begin(); it != task_vec.end(); ++it) {
            if (it->f_size < it_to_min->f_size) {
                it_to_min = it;
            }
        }
        
        RequestPacket task = *it_to_min;
        task_vec.erase(it_to_min);
        return task;
    }
};

// --- RR Scheduler ---
class Scheduler_RR : public BaseScheduler {
public:
    void add(RequestPacket task) override {
        std::unique_lock<std::mutex> lock(queue_mutex);
        task_queue.push(task);
        lock.unlock();
        cv.notify_one();
    }

    RequestPacket get_next() override {
        std::unique_lock<std::mutex> lock(queue_mutex);
        cv.wait(lock, [this] { return !task_queue.empty(); });
        RequestPacket task = task_queue.front();
        task_queue.pop();
        return task;
    }
};

#endif // UTILS_HPP

