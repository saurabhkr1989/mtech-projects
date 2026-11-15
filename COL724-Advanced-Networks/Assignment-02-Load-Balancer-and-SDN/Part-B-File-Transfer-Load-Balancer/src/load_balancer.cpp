#include <iostream>
#include <vector>
#include <string>
#include <thread>
#include <mutex>
#include <atomic>
#include <chrono>
#include <fstream>
#include <sstream>
#include <memory>
#include <filesystem>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <poll.h>
#include <csignal>
#include <sys/wait.h>
#include <iomanip>

#include "nlohmann/json.hpp"
#include "utils.hpp" 

using namespace std;
using json = nlohmann::json;

// --- Configuration and State Structures ---
struct BackendServer {
    int id;
    string ip;
    int port;
    atomic<bool> is_alive;
    atomic<int> active_connections;
    pid_t pid; 

    BackendServer(int i, string ip_addr, int p) : 
        id(i), ip(ip_addr), port(p), is_alive(false), active_connections(0), pid(0) {}
};

struct LBConfig {
    string lb_ip;
    int lb_port;
    string algo; 
    string server_sched_policy;
    int server_quantum_val = 0;
    string server_base_path;
    int server_packet_lines = 1;
    int server_threads = 1;
};

// --- Global Variables ---
LBConfig g_config;
vector<unique_ptr<BackendServer>> g_backend_servers;
mutex g_server_selection_mutex; 
atomic<int> g_rr_counter = 0;
vector<pid_t> g_server_pids; 
atomic<int> g_client_threads = 0; // Read from config.json

// --- Forward Declarations ---
void handle_client_connection(int client_sock);
void health_check_routine();
int select_backend_server();
void proxy_data(int client_sock, int server_sock);
void start_backend_servers();
void signal_handler(int signum);
string read_line_from_socket_lb(int fd);

// --- Main Function ---
int main(int argc, char* argv[]) {
    cout << CLR_BOLD << "--- Load Balancer Setup ---" << CLR_RESET << endl;

    for (int i = 1; i < argc; ++i) {
        string arg = argv[i];
        if (arg == "--algo" && i + 1 < argc) g_config.algo = argv[++i];
        else if (arg == "--sched" && i + 1 < argc) g_config.server_sched_policy = argv[++i];
        else if (arg == "--quantum" && i + 1 < argc) g_config.server_quantum_val = stoi(argv[++i]);
        else if (arg == "--file" && i + 1 < argc) g_config.server_base_path = argv[++i];
        else if (arg == "--p" && i + 1 < argc) g_config.server_packet_lines = stoi(argv[++i]);
        else if (arg == "--threads" && i + 1 < argc) g_config.server_threads = stoi(argv[++i]);
    }

    if (g_config.algo.empty() || (g_config.algo != "rr" && g_config.algo != "lc") || g_config.server_sched_policy.empty() || g_config.server_base_path.empty()) {
        cerr << "Usage: ./load_balancer --algo <rr|lc> --sched <fcfs|sjf|rr> --file <base_path> [--threads N] [--p N] [--quantum N]" << endl;
        return 1;
    }
    cout << "[Main] Load Balancer Algorithm: " << g_config.algo << endl;
    cout << "[Main] Backend Server Config: sched=" << g_config.server_sched_policy << ", threads=" << g_config.server_threads << endl;

    ifstream config_stream("config.json");
    if (!config_stream.is_open()) {
        cerr << CLR_RED << "Error: Could not open config.json." << CLR_RESET << endl;
        return 1;
    }
    try {
        json config_json;
        config_stream >> config_json;
        g_config.lb_ip = config_json.at("lb_ip");
        g_config.lb_port = config_json.at("lb_port");
        g_client_threads = config_json.at("client_threads");

        for (int i = 1; i <= 4; ++i) {
            string server_ip_key = "server" + to_string(i) + "_ip";
            string server_port_key = "server" + to_string(i) + "_port";
            g_backend_servers.push_back(make_unique<BackendServer>(i, config_json.at(server_ip_key), config_json.at(server_port_key)));
        }
    } catch (const json::exception& e) {
        cerr << CLR_RED << "Error parsing config.json: " << e.what() << CLR_RESET << endl;
        return 1;
    }

    const string log_filename = "results.csv";
    if (filesystem::exists(log_filename)) {
        cout << "[Main] results.csv already exists. Appending to it." << endl;
    } else {
        cout << "[Main] Creating new log file: " << log_filename << endl;
        ofstream results_file(log_filename);
        if (results_file.is_open()) {
            results_file << "NumServers,ServerThreads,ClientThreads,ServerID,ServerThreadID,ClientThreadID,SchedulingAlgoLoadBalancer,SchedulingAlgoServer,PacketLength,BasePath,FileName,RequestType,FileSizeKB,"
                         << "ArrivalTimeLB_ms,ArrivalTimeServer_ms,StartTime_ms,FinishTime_ms,ResponseTime_ms,WaitTime_ms\n";
            results_file.flush();
        } else {
            cerr << CLR_RED << "Error: Could not create log file " << log_filename << CLR_RESET << endl;
        }
    }


    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    start_backend_servers();
    cout << "[Main] Waiting for 2 seconds for servers to initialize..." << endl;
    this_thread::sleep_for(chrono::seconds(2));

    thread health_thread(health_check_routine);
    health_thread.detach(); 

    int lb_socket = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in lb_address;
    lb_address.sin_family = AF_INET;
    lb_address.sin_port = htons(g_config.lb_port);
    lb_address.sin_addr.s_addr = inet_addr(g_config.lb_ip.c_str());

    int reuse = 1;
    setsockopt(lb_socket, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

    if (bind(lb_socket, (struct sockaddr *)&lb_address, sizeof(lb_address)) < 0) {
        cerr << CLR_RED << "Error: Failed to bind to " << g_config.lb_ip << ":" << g_config.lb_port << ". Address may be in use." << CLR_RESET << endl;
        return 1;
    }
    listen(lb_socket, 128);

    cout << "\n" << CLR_BOLD << CLR_GREEN << "Load Balancer is ONLINE." << CLR_RESET << endl;
    cout << "Listening on: " << g_config.lb_ip << ":" << g_config.lb_port << endl;

    while (true) {
        int client_sock = accept(lb_socket, nullptr, nullptr);
        if (client_sock < 0) {
            perror("accept");
            continue;
        }
        thread(handle_client_connection, client_sock).detach();
    }

    return 0;
}

void signal_handler(int signum) {
    cout << "\n[Signal] " << signum << " received. Shutting down backend servers..." << endl;
    for (pid_t pid : g_server_pids) {
        if (pid > 0) {
            kill(pid, SIGTERM);
        }
    }
    for (pid_t pid : g_server_pids) {
        if (pid > 0) {
            waitpid(pid, NULL, 0);
        }
    }
    cout << "[Signal] Shutdown complete." << endl;
    exit(signum);
}

void start_backend_servers() {
    cout << "[Main] Starting 4 backend server processes..." << endl;
    for (const auto& server : g_backend_servers) {
        string server_dir = g_config.server_base_path + "/server" + to_string(server->id) + "_files";
        filesystem::create_directories(server_dir);

        pid_t pid = fork();
        if (pid == 0) { 
            vector<string> args_str;
            args_str.push_back("./server");
            args_str.push_back("--ip"); args_str.push_back(server->ip);
            args_str.push_back("--port"); args_str.push_back(to_string(server->port));
            args_str.push_back("--server-id"); args_str.push_back(to_string(server->id));
            args_str.push_back("--threads"); args_str.push_back(to_string(g_config.server_threads));
            args_str.push_back("--sched"); args_str.push_back(g_config.server_sched_policy);
            args_str.push_back("--file"); args_str.push_back(server_dir);
            args_str.push_back("--p"); args_str.push_back(to_string(g_config.server_packet_lines));
            if (g_config.server_sched_policy == "rr") {
                args_str.push_back("--quantum");
                args_str.push_back(to_string(g_config.server_quantum_val));
            }

            vector<char*> args_c;
            for(const auto& s : args_str) args_c.push_back((char*)s.c_str());
            args_c.push_back(nullptr);

            execv("./server", args_c.data());
            perror("execv"); 
            exit(EXIT_FAILURE);
        } else if (pid > 0) { 
            cout << "[Main] Launched Server " << server->id << " on PID " << pid << " (" << server->ip << ":" << server->port << ")" << endl;
            g_server_pids.push_back(pid);
        } else {
            cerr << CLR_RED << "Error: Failed to fork server process " << server->id << CLR_RESET << endl;
        }
    }
}

void health_check_routine() {
    ofstream health_log("health_checks.log", ios::app);
    time_t now = chrono::system_clock::to_time_t(chrono::system_clock::now());
    health_log << "--- Starting new health check session at " << ctime(&now);
    
    while (true) {
        this_thread::sleep_for(chrono::seconds(1));
        for (const auto& server : g_backend_servers) {
            int sock = socket(AF_INET, SOCK_STREAM, 0);
            struct sockaddr_in server_addr;
            server_addr.sin_family = AF_INET;
            server_addr.sin_port = htons(server->port);
            inet_pton(AF_INET, server->ip.c_str(), &server_addr.sin_addr);

            auto start = chrono::steady_clock::now();
            if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) == 0) {
                send(sock, "PING\n", 5, 0);
                char buffer[16] = {0};
                read(sock, buffer, sizeof(buffer) - 1); 
                auto end = chrono::steady_clock::now();
                
                if (string(buffer).rfind("PONG", 0) == 0) {
                    server->is_alive = true;
                    double rtt = chrono::duration<double, milli>(end-start).count();
                    health_log << "Server " << server->id << " (" << server->ip << ":" << server->port << ") is ALIVE. RTT: " << fixed << setprecision(3) << rtt << "ms" << endl;
                } else {
                    server->is_alive = false;
                     health_log << "Server " << server->id << " (" << server->ip << ":" << server->port << ") is DEAD (Bad Response)." << endl;
                }
            } else {
                server->is_alive = false;
                 health_log << "Server " << server->id << " (" << server->ip << ":" << server->port << ") is DEAD (Connection Failed)." << endl;
            }
            close(sock);
        }
    }
}

int select_backend_server() {
    lock_guard<mutex> lock(g_server_selection_mutex);
    vector<int> available_servers;
    for (const auto& s : g_backend_servers) {
        if (s->is_alive) {
            available_servers.push_back(s->id);
        }
    }

    if (available_servers.empty()) {
        return -1; 
    }

    if (g_config.algo == "rr") {
        int server_id = available_servers[g_rr_counter % available_servers.size()];
        g_rr_counter++;
        return server_id;
    }
    
    if (g_config.algo == "lc") {
        int min_connections = -1;
        for (int id : available_servers) {
            if (min_connections == -1 || g_backend_servers[id-1]->active_connections < min_connections) {
                min_connections = g_backend_servers[id-1]->active_connections;
            }
        }
        
        vector<int> tied_servers;
        for (int id : available_servers) {
            if (g_backend_servers[id-1]->active_connections == min_connections) {
                tied_servers.push_back(id);
            }
        }
        
        int best_server_id = tied_servers[g_rr_counter % tied_servers.size()];
        g_rr_counter++;
        return best_server_id;
    }

    return -1; 
}

void handle_client_connection(int client_sock) {
    cout << "[LB] New client connection received." << endl;
    
    // --- CAPTURE ARRIVAL TIME AT LB ---
    auto lb_arrival_time = chrono::steady_clock::now();

    // --- READ CLIENT HANDSHAKE AND COMMAND ---
    string client_handshake = read_line_from_socket_lb(client_sock);
    string client_command = read_line_from_socket_lb(client_sock);

    if (client_handshake.empty() || client_command.empty()) {
        cerr << CLR_RED << "[LB] Client disconnected before sending full request." << CLR_RESET << endl;
        close(client_sock);
        return;
    }

    int server_id = select_backend_server();
    if (server_id == -1) {
        cout << CLR_RED << "[LB] No backend servers available. Closing connection." << CLR_RESET << endl;
        send(client_sock, "ERROR No servers available\n", 26, 0);
        close(client_sock);
        return;
    }

    BackendServer* selected_server = g_backend_servers[server_id - 1].get();
    selected_server->active_connections++;
    cout << "[LB] Routing client to Server " << server_id << ". Active connections: " << selected_server->active_connections << endl;

    int server_sock = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(selected_server->port);
    inet_pton(AF_INET, selected_server->ip.c_str(), &server_addr.sin_addr);

    if (connect(server_sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        cerr << CLR_RED << "[LB] Failed to connect to backend Server " << server_id << CLR_RESET << endl;
        send(client_sock, "ERROR Could not connect to backend\n", 34, 0);
        close(client_sock);
        selected_server->active_connections--;
        return;
    }
    cout << "[LB] Connection to Server " << server_id << " successful." << endl;
    
    // --- FORWARD METADATA AND ORIGINAL REQUEST ---
    long long lb_arrival_ms = chrono::time_point_cast<chrono::milliseconds>(lb_arrival_time).time_since_epoch().count();
    
    string lb_metadata = "LB_ARRIVAL=" + to_string(lb_arrival_ms) + " LB_ALGO=" + g_config.algo + "\n";
    
    send(server_sock, lb_metadata.c_str(), lb_metadata.length(), 0);
    send(server_sock, (client_handshake + "\n").c_str(), client_handshake.length() + 1, 0);
    send(server_sock, (client_command + "\n").c_str(), client_command.length() + 1, 0);
    
    // --- PROXY REMAINING DATA (FILE CONTENT) ---
    proxy_data(client_sock, server_sock);

    close(client_sock);
    close(server_sock);
    selected_server->active_connections--;
    cout << "[LB] Connection finished with Server " << server_id << ". Active connections: " << selected_server->active_connections << endl;
}

void proxy_data(int client_sock, int server_sock) {
    char buffer[4096];
    struct pollfd fds[2];
    
    fds[0].fd = client_sock; fds[0].events = POLLIN;
    fds[1].fd = server_sock; fds[1].events = POLLIN;

    while (true) {
        int ret = poll(fds, 2, 60000); 
        if (ret <= 0) break;

        if (fds[0].revents & POLLIN) {
            int bytes_read = read(client_sock, buffer, sizeof(buffer));
            if (bytes_read <= 0) break;
            if (write(server_sock, buffer, bytes_read) <= 0) break;
        }

        if (fds[1].revents & POLLIN) {
            int bytes_read = read(server_sock, buffer, sizeof(buffer));
            if (bytes_read <= 0) break;
            if (write(client_sock, buffer, bytes_read) <= 0) break;
        }
        
        if ((fds[0].revents & (POLLHUP | POLLERR)) || (fds[1].revents & (POLLHUP | POLLERR))) break;
    }
}

string read_line_from_socket_lb(int fd) {
    string line;
    char buffer;
    ssize_t n_read;
    while ((n_read = read(fd, &buffer, 1)) > 0) {
        if (buffer == '\n') break;
        line += buffer;
    }
    return line;
}

