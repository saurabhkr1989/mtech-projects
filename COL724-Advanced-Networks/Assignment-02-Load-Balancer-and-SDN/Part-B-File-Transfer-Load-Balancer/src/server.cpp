#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <fstream>
#include <sstream>
#include <filesystem>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <algorithm>
#include <iomanip> 
#include <limits>  

#include "utils.hpp"
#include "nlohmann/json.hpp"

using namespace std;
using json = nlohmann::json;

struct RequestPacket;
class BaseScheduler;

struct Config {
    string ip_addr;
    int port_num;
    int server_id; 
    int thread_count;
    string file_path;
    bool path_is_dir;
    string sched_policy;
    int packet_lines = 1;
    int quantum_val = 0;
} g_config;
unique_ptr<BaseScheduler> g_scheduler;

void server_main_loop(int);
RequestPacket parse_client_request(char* buffer, int client_socket, int client_tid, int client_t_count, chrono::steady_clock::time_point lb_arrival_tp, const string& lb_algo);
void worker_routine(int id);
bool handle_get_request(RequestPacket& task);
bool handle_put_request(RequestPacket& task);

string read_line_from_socket(int fd) {
    string line;
    char buffer;
    ssize_t n_read;
    while ((n_read = read(fd, &buffer, 1)) > 0) {
        if (buffer == '\n') break;
        line += buffer;
    }
    if (n_read == 0 && !line.empty()) {
        cerr << CLR_YELLOW << "[Dispatcher] Client disconnected mid-message." << CLR_RESET << endl;
    }
    return line;
}

int main(int argc, char* argv[]) {
    cout << CLR_BOLD << "--- Server Setup ---" << CLR_RESET << endl;
    
    for (int i = 1; i < argc; ++i) {
        string arg = argv[i];
        if (arg == "--ip" && i + 1 < argc) g_config.ip_addr = argv[++i];
        else if (arg == "--port" && i + 1 < argc) g_config.port_num = stoi(argv[++i]);
        else if (arg == "--server-id" && i + 1 < argc) g_config.server_id = stoi(argv[++i]);
        else if (arg == "--threads" && i + 1 < argc) g_config.thread_count = stoi(argv[++i]);
        else if (arg == "--sched" && i + 1 < argc) g_config.sched_policy = argv[++i];
        else if (arg == "--quantum" && i + 1 < argc) try { g_config.quantum_val = stoi(argv[++i]); } catch (...) { cerr << CLR_RED << "Error: Invalid value for --quantum." << CLR_RESET << endl; return 1; }
        else if (arg == "--file" && i + 1 < argc) g_config.file_path = argv[++i];
        else if (arg == "--p" && i + 1 < argc) try { g_config.packet_lines = stoi(argv[++i]); } catch (...) { cerr << CLR_RED << "Error: Invalid value for --p." << CLR_RESET << endl; return 1; }
    }

    if (g_config.sched_policy.empty() || g_config.file_path.empty() || g_config.ip_addr.empty() || g_config.port_num == 0 || g_config.server_id == 0) {
        cerr << "This server is intended to be launched by the load balancer." << endl;
        return 1;
    }
    if (g_config.sched_policy == "rr" && g_config.quantum_val <= 0) {
        cerr << CLR_RED << "Error: --sched rr requires a positive integer for --quantum." << CLR_RESET << endl;
        return 1;
    }

    if (g_config.sched_policy == "fcfs") g_scheduler = make_unique<Scheduler_FCFS>();
    else if (g_config.sched_policy == "sjf") g_scheduler = make_unique<Scheduler_SJF>();
    else if (g_config.sched_policy == "rr") g_scheduler = make_unique<Scheduler_RR>();
    else { cerr << CLR_RED << "Error: Invalid scheduler. Must be fcfs, sjf, or rr." << CLR_RESET << endl; return 1; }

    try {
        if (filesystem::is_directory(g_config.file_path)) {
            g_config.path_is_dir = true;
            if (g_config.file_path.back() != '/') g_config.file_path += '/';
        } else if (filesystem::is_regular_file(g_config.file_path)) {
            g_config.path_is_dir = false;
        } else {
             filesystem::create_directories(g_config.file_path);
             g_config.path_is_dir = true;
        }
    } catch (const filesystem::filesystem_error& e) {
        cerr << CLR_RED << "Error accessing file path: " << e.what() << CLR_RESET << endl;
        return 1;
    }
    
    int the_main_socket = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in s_address;
    s_address.sin_family = AF_INET;
    s_address.sin_port = htons(g_config.port_num);
    s_address.sin_addr.s_addr = inet_addr(g_config.ip_addr.c_str());

    int reuse = 1;
    if (setsockopt(the_main_socket, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse)) < 0) {
        perror("setsockopt");
    }

    if (bind(the_main_socket, (struct sockaddr *)&s_address, sizeof(s_address)) < 0) {
        cerr << CLR_RED << "Error: Failed to bind to " << g_config.ip_addr << ":" << g_config.port_num << ". Address may be in use." << CLR_RESET << endl;
        return 1;
    }
    listen(the_main_socket, 128);

    cout << "\n" << CLR_BOLD << CLR_GREEN << "Server " << g_config.server_id << " is ONLINE." << CLR_RESET << endl;
    cout << "Listening on: " << g_config.ip_addr << ":" << g_config.port_num << endl;
    cout << "Serving from: " << g_config.file_path << (g_config.path_is_dir ? " (Directory Mode)" : " (Single-File Mode)") << endl;
    cout << "Mode: " << g_config.sched_policy << " | Workers: " << g_config.thread_count << endl;

    vector<thread> worker_pool;
    for(int i = 0; i < g_config.thread_count; i++) {
        worker_pool.emplace_back(worker_routine, i + 1);
    }

    server_main_loop(the_main_socket);
    
    for (auto& t : worker_pool) t.join();
    close(the_main_socket);
    return 0;
}

void server_main_loop(int server_socket) {
    cout << CLR_BLUE << "Dispatcher is now listening for incoming requests..." << CLR_RESET << endl;
    for (;;) {
        int client_connection_fd = accept(server_socket, nullptr, nullptr);
        if (client_connection_fd < 0) continue;
        
        char peek_buffer[6] = {0};
        int bytes_peeked = recv(client_connection_fd, peek_buffer, 5, MSG_PEEK);
        if (bytes_peeked > 0 && string(peek_buffer).rfind("PING", 0) == 0) {
            char drain_buffer[16];
            read(client_connection_fd, drain_buffer, sizeof(drain_buffer)); 
            send(client_connection_fd, "PONG\n", 5, 0);
            close(client_connection_fd);
            continue; 
        }

        string lb_metadata_line = read_line_from_socket(client_connection_fd);
        long long lb_arrival_ms = 0;
        string lb_algo = "unknown";
        
        stringstream meta_ss(lb_metadata_line);
        string part;
        while(meta_ss >> part) {
            if (part.rfind("LB_ARRIVAL=", 0) == 0) {
                try { lb_arrival_ms = stoll(part.substr(11)); } catch(...) {}
            } else if (part.rfind("LB_ALGO=", 0) == 0) {
                lb_algo = part.substr(8);
            }
        }
        chrono::steady_clock::time_point lb_arrival_tp{chrono::milliseconds(lb_arrival_ms)};
        
        string handshake_line = read_line_from_socket(client_connection_fd);
        int client_tid = 0, client_t_count = 0;
        stringstream ss(handshake_line);
        string token;
        while(ss >> token) {
            if (token.rfind("TID=", 0) == 0) try { client_tid = stoi(token.substr(4)); } catch(...) {}
            else if (token.rfind("T_COUNT=", 0) == 0) try { client_t_count = stoi(token.substr(8)); } catch(...) {}
        }

        if (client_tid == 0 || client_t_count == 0) {
            cerr << CLR_RED << "[Dispatcher] Invalid handshake. Closing." << CLR_RESET << endl;
            close(client_connection_fd);
            continue;
        }
        
        string command_line = read_line_from_socket(client_connection_fd);
        if (command_line.empty()) {
            cerr << CLR_RED << "[Dispatcher] Empty command. Closing." << CLR_RESET << endl;
            close(client_connection_fd);
            continue;
        }
        
        RequestPacket task = parse_client_request((char*)command_line.c_str(), client_connection_fd, client_tid, client_t_count, lb_arrival_tp, lb_algo);

        if (task.type != RequestPacket::CMD_NONE) {
            g_scheduler->add(task);
        } else {
            string error_msg = "ERROR Malformed or invalid request\n";
            send(client_connection_fd, error_msg.c_str(), error_msg.length(), 0);
            close(client_connection_fd);
        }
    }
}

RequestPacket parse_client_request(char* buffer, int client_socket, int client_tid, int client_t_count, chrono::steady_clock::time_point lb_arrival_tp, const string& lb_algo) {
    RequestPacket req;
    req.client_fd = client_socket;
    req.arrival_t_lb = lb_arrival_tp;
    req.arrival_t = chrono::steady_clock::now();
    req.type = RequestPacket::CMD_NONE;
    req.client_thread_id = client_tid;
    req.total_client_threads = client_t_count;
    req.server_id = g_config.server_id;
    req.lb_sched_policy = lb_algo;

    stringstream ss(buffer);
    string cmd_str, file_str;

    if (!(ss >> cmd_str >> file_str)) {
        cerr << CLR_RED << "[Request Parser] Malformed: Could not parse command and filename." << CLR_RESET << endl;
        return req;
    }

    size_t endpos = file_str.find_last_not_of(" \t\n\r");
    if (string::npos != endpos) file_str = file_str.substr(0, endpos + 1);
    else {
        cerr << CLR_RED << "[Request Parser] Malformed: Filename is only whitespace." << CLR_RESET << endl;
        return req;
    }

    if (file_str.empty()) {
        cerr << CLR_RED << "[Request Parser] Malformed: Filename is empty." << CLR_RESET << endl;
        return req;
    }
    
    if (file_str.length() <= 4 || file_str.substr(file_str.length() - 4) != ".txt") {
        cerr << CLR_RED << "[Request Parser] Invalid file type for '" << file_str << "'. Only .txt files are allowed." << CLR_RESET << endl;
        return req;
    }
    
    req.filename_on_server = file_str;

    if (cmd_str == "GET") {
        req.type = RequestPacket::CMD_GET;
        string fullpath = g_config.path_is_dir ? g_config.file_path + file_str : g_config.file_path;
        try {
            if (filesystem::exists(fullpath) && !filesystem::is_directory(fullpath)) req.f_size = filesystem::file_size(fullpath);
            else req.f_size = -1;
        } catch (...) { req.f_size = -1; }
    } else if (cmd_str == "PUT") {
        if (!g_config.path_is_dir) {
            cerr << CLR_RED << "[Request Parser] Invalid: Cannot PUT in single-file mode." << CLR_RESET << endl;
            return req;
        }
        
        string size_part;
        if (!(ss >> size_part) || size_part.rfind("SIZE=", 0) != 0) {
            cerr << CLR_RED << "[Request Parser] Malformed PUT: Missing SIZE parameter." << CLR_RESET << endl;
            return req;
        }

        try {
            req.f_size = stoll(size_part.substr(5));
            req.type = RequestPacket::CMD_PUT;
        } catch (...) {
            cerr << CLR_RED << "[Request Parser] Malformed PUT: Invalid file size value." << CLR_RESET << endl;
            return req;
        }
    } else {
        cerr << CLR_RED << "[Request Parser] Invalid command: '" << cmd_str << "'" << CLR_RESET << endl;
    }
    
    return req;
}

bool handle_get_request(RequestPacket& task) {
    string file_path = g_config.path_is_dir ? g_config.file_path + task.filename_on_server : g_config.file_path;
    
    if (task.f_size == -1) {
        send(task.client_fd, "ERROR File not found\n", 20, 0);
        return true;
    }
    ifstream file_to_send(file_path);
    if (!file_to_send.is_open()) {
        send(task.client_fd, "ERROR Cannot open file\n", 23, 0);
        return true;
    }
    if (task.lines_processed == 0) send(task.client_fd, "OK\n", 3, 0);
    if (task.lines_processed > 0) {
        for (int i = 0; i < task.lines_processed; ++i) file_to_send.ignore(numeric_limits<streamsize>::max(), '\n');
    }

    if (g_config.sched_policy != "rr") {
        string line, buf; int count = 0;
        while (getline(file_to_send, line)) {
            buf.append(line).append("\n"); count++;
            if (count >= g_config.packet_lines) {
                send(task.client_fd, buf.c_str(), buf.size(), 0); buf.clear(); count = 0;
            }
        }
        if (!buf.empty()) send(task.client_fd, buf.c_str(), buf.size(), 0);
        return true;
    } else {
        string line, buf; int lines_in_pkt = 0, pkts_sent = 0;
        while (getline(file_to_send, line)) {
            buf.append(line).append("\n"); lines_in_pkt++; task.lines_processed++;
            if (lines_in_pkt >= g_config.packet_lines) {
                send(task.client_fd, buf.c_str(), buf.size(), 0); buf.clear(); lines_in_pkt = 0; pkts_sent++;
                if (pkts_sent >= g_config.quantum_val) {
                    if (file_to_send.peek() == EOF) return true;
                    return false;
                }
            }
        }
        if (!buf.empty()) send(task.client_fd, buf.c_str(), buf.size(), 0);
        return true;
    }
}

bool handle_put_request(RequestPacket& task) {
    string file_path = g_config.file_path + task.filename_on_server;
    
    if (filesystem::exists(file_path)) {
        cerr << CLR_YELLOW << "  [Worker] Warning: Overwriting '" << task.filename_on_server << "'" << CLR_RESET << endl;
    }

    ofstream received_file(file_path, ios::binary);
    if (!received_file.is_open()) {
        send(task.client_fd, "ERROR Cannot create file on server\n", 35, 0);
        return true;
    }
    
    send(task.client_fd, "OK_READY\n", 9, 0);
    char recv_buffer[4096] = {0};
    int bytes_received;
    while ((bytes_received = recv(task.client_fd, recv_buffer, sizeof(recv_buffer), 0)) > 0) {
        received_file.write(recv_buffer, bytes_received);
    }
    return true;
}

void worker_routine(int id) {
    string worker_name = "Worker-" + to_string(id);
    cout << "  " << worker_name << " has started." << endl;
    for (;;) {
        RequestPacket task = g_scheduler->get_next();
        if (task.is_new_task) {
            task.start_t = chrono::steady_clock::now();
            task.is_new_task = false;
        }
        
        string action_str = (task.type == RequestPacket::CMD_GET) ? "GET" : "PUT";
        cout << CLR_YELLOW << "  [S" << g_config.server_id << "-" << worker_name << "]: Starting " << action_str << " on '" << task.filename_on_server << "'" << CLR_RESET << endl;

        bool task_finished = false;
        if (task.type == RequestPacket::CMD_GET) task_finished = handle_get_request(task);
        else if (task.type == RequestPacket::CMD_PUT) task_finished = handle_put_request(task);
        
        if (task_finished) {
            task.finish_t = chrono::steady_clock::now();
            close(task.client_fd);

            auto arrival_lb_ms = chrono::time_point_cast<chrono::milliseconds>(task.arrival_t_lb).time_since_epoch().count();
            auto arrival_server_ms = chrono::time_point_cast<chrono::milliseconds>(task.arrival_t).time_since_epoch().count();
            auto start_ms = chrono::time_point_cast<chrono::milliseconds>(task.start_t).time_since_epoch().count();
            auto finish_ms = chrono::time_point_cast<chrono::milliseconds>(task.finish_t).time_since_epoch().count();
            
            double response_time_ms = chrono::duration<double, milli>(task.finish_t - task.arrival_t_lb).count();
            double wait_time_ms = chrono::duration<double, milli>(task.start_t - task.arrival_t).count();
            double file_size_kb = (task.f_size >= 0) ? static_cast<double>(task.f_size) / 1024.0 : 0.0;

            cout << CLR_GREEN << "  [S" << g_config.server_id << "-" << worker_name << "]: Finished '" << task.filename_on_server << "'. Wait: " << wait_time_ms << "ms. Response: " << response_time_ms << "ms." << CLR_RESET << endl;

            ofstream results_file("results.csv", ios::app);
            if (results_file.is_open()) {
                results_file << "4," // NumServers
                             << g_config.thread_count << ","
                             << task.total_client_threads << ","
                             << task.server_id << ","
                             << id << ","
                             << task.client_thread_id << ","
                             << task.lb_sched_policy << ","
                             << g_config.sched_policy << ","
                             << g_config.packet_lines << ","
                             << g_config.file_path << ","
                             << task.filename_on_server << ","
                             << action_str << ","
                             << fixed << setprecision(3) << file_size_kb << ","
                             << arrival_lb_ms << ","
                             << arrival_server_ms << ","
                             << start_ms << ","
                             << finish_ms << ","
                             << fixed << setprecision(3) << response_time_ms << ","
                             << fixed << setprecision(3) << wait_time_ms << "\n";
                results_file.flush();
            }
        } else {
            cout << CLR_YELLOW << "  [S" << g_config.server_id << "-" << worker_name << "]: Quantum expired for '" << task.filename_on_server << "'. Re-queuing." << CLR_RESET << endl;
            g_scheduler->add(task);
        }
    }
}

