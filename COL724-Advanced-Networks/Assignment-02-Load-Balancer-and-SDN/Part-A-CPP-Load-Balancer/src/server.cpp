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
#include <iomanip> // Required for setprecision
#include <limits>  // Required for numeric_limits

#include "utils.hpp"
#include "nlohmann/json.hpp"

using namespace std;
using json = nlohmann::json;

// --- Forward Declarations for complex types ---
struct RequestPacket;
class BaseScheduler;

// --- Global Variables ---
struct Config {
    string ip_addr;
    int port_num;
    int thread_count;
    string file_path;
    bool path_is_dir;
    string sched_policy;
    int packet_lines = 1;
    int quantum_val = 0;
} g_config;
unique_ptr<BaseScheduler> g_scheduler;

// --- Forward Declarations ---
void server_main_loop(int);
RequestPacket parse_client_request(char* buffer, int client_socket, int client_tid, int client_t_count);
void worker_routine(int id);
bool handle_get_request(RequestPacket& task);
bool handle_put_request(RequestPacket& task);

// --- NEW HELPER FUNCTION ---
// Reads from a socket one byte at a time until a newline character is found.
// This is crucial for handling TCP streams reliably.
string read_line_from_socket(int fd) {
    string line;
    char buffer;
    ssize_t n_read;
    while ((n_read = read(fd, &buffer, 1)) > 0) {
        if (buffer == '\n') {
            break;
        }
        line += buffer;
    }
    // If read returns 0, it means client closed the connection.
    if (n_read == 0 && !line.empty()) {
        cerr << CLR_YELLOW << "[Dispatcher] Client disconnected mid-message." << CLR_RESET << endl;
    }
    //   cout << "[Socket Read] Read line: \"" << line << "\"" << endl;
    return line;
}

// --- Main Function ---
int main(int argc, char* argv[]) {
    // This function is correct and does not need changes.
    // It is included here for completeness.
    cout << CLR_BOLD << "--- Server Setup ---" << CLR_RESET << endl;
    //   cout << "[Main] Parsing command line arguments..." << endl;
    for (int i = 1; i < argc; ++i) {
        string arg = argv[i];
        if (arg == "--sched" && i + 1 < argc) g_config.sched_policy = argv[++i];
        else if (arg == "--quantum" && i + 1 < argc) try { g_config.quantum_val = stoi(argv[++i]); } catch (...) { cerr << CLR_RED << "Error: Invalid value for --quantum." << CLR_RESET << endl; return 1; }
        else if (arg == "--file" && i + 1 < argc) g_config.file_path = argv[++i];
        else if (arg == "--p" && i + 1 < argc) try { g_config.packet_lines = stoi(argv[++i]); } catch (...) { cerr << CLR_RED << "Error: Invalid value for --p." << CLR_RESET << endl; return 1; }
    }
    //   cout << "[Main] Sched: " << g_config.sched_policy << ", Quantum: " << g_config.quantum_val << ", File: " << g_config.file_path << ", P-lines: " << g_config.packet_lines << endl;

    if (g_config.sched_policy.empty() || g_config.file_path.empty()) {
        cerr << "Usage: ./server --sched <fcfs|sjf|rr> --file <path> [--p <lines>] [--quantum <packets>]" << endl;
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
            cerr << CLR_RED << "Error: Path '" << g_config.file_path << "' is not a valid file or directory." << CLR_RESET << endl;
            return 1;
        }
    } catch (const filesystem::filesystem_error& e) {
        cerr << CLR_RED << "Error accessing file path: " << e.what() << CLR_RESET << endl;
        return 1;
    }
    
    ifstream config_stream("config.json");
    if (!config_stream.is_open()) { cerr << CLR_RED << "Error: Could not open config.json." << CLR_RESET << endl; return 1; }
    try {
        json config_json;
        config_stream >> config_json;
        g_config.ip_addr = config_json.at("server_ip");
        g_config.port_num = config_json.at("server_port");
        g_config.thread_count = config_json.at("server_threads");
    } catch (const json::exception& e) {
        cerr << CLR_RED << "Error parsing config.json: " << e.what() << CLR_RESET << endl;
        return 1;
    }
    
    const string log_filename = "results.csv";
    if (!filesystem::exists(log_filename)) {
        ofstream results_file(log_filename);
        results_file << "ServerThreads,TotalClientThreads,ServerThreadID,ClientThreadID,SchedulingPolicy,PacketLines,Quantum,BasePath,FileName,RequestType,"
                     << "FileSizeKB,ArrivalTime_ms,StartTime_ms,FinishTime_ms,ResponseTime_ms,WaitTime_ms\n";
    }

    int the_main_socket = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in s_address;
    s_address.sin_family = AF_INET;
    s_address.sin_port = htons(g_config.port_num);
    s_address.sin_addr.s_addr = inet_addr(g_config.ip_addr.c_str());
    if (bind(the_main_socket, (struct sockaddr *)&s_address, sizeof(s_address)) < 0) {
        cerr << CLR_RED << "Error: Failed to bind to " << g_config.ip_addr << ":" << g_config.port_num << ". Address may be in use." << CLR_RESET << endl;
        return 1;
    }
    listen(the_main_socket, 128);

    cout << "\n" << CLR_BOLD << CLR_GREEN << "Server is ONLINE." << CLR_RESET << endl;
    cout << "Appending results to: " << log_filename << endl;
    cout << "Listening on: " << g_config.ip_addr << ":" << g_config.port_num << endl;
    cout << "Serving from: " << g_config.file_path << (g_config.path_is_dir ? " (Directory Mode)" : " (Single-File Mode)") << endl;
    cout << "Mode: " << g_config.sched_policy << " | Workers: " << g_config.thread_count << " | Packet Size (lines): " << g_config.packet_lines;
    if (g_config.sched_policy == "rr") cout << " | Quantum (packets): " << g_config.quantum_val;
    cout << endl;

    vector<thread> worker_pool;
    //   cout << "[Main] Creating " << g_config.thread_count << " worker threads." << endl;
    for(int i = 0; i < g_config.thread_count; i++) {
        worker_pool.emplace_back(worker_routine, i + 1);
    }

    server_main_loop(the_main_socket);
    
    //   cout << "[Main] Dispatcher loop finished. Joining worker threads." << endl;
    for (auto& t : worker_pool) t.join();
    close(the_main_socket);
    return 0;
}

// --- UPDATED: This function now correctly reads line-by-line ---
void server_main_loop(int server_socket) {
    cout << CLR_BLUE << "Dispatcher is now listening for incoming requests..." << CLR_RESET << endl;
    for (;;) {
        //   cout << "[Dispatcher] Waiting for a new client connection..." << endl;
        int client_connection_fd = accept(server_socket, nullptr, nullptr);
        if (client_connection_fd < 0) continue;
        //   cout << "[Dispatcher] Accepted new connection. FD: " << client_connection_fd << endl;
        
        // 1. Read the handshake line reliably.
        string handshake_line = read_line_from_socket(client_connection_fd);
        //   cout << "[Dispatcher] Received handshake: \"" << handshake_line << "\"" << endl;
        
        int client_tid = 0;
        int client_t_count = 0;
        stringstream ss(handshake_line);
        string token;
        while(ss >> token) {
            if (token.rfind("TID=", 0) == 0) try { client_tid = stoi(token.substr(4)); } catch(...) {}
            else if (token.rfind("T_COUNT=", 0) == 0) try { client_t_count = stoi(token.substr(8)); } catch(...) {}
        }
        //   cout << "[Dispatcher] Parsed handshake: TID=" << client_tid << ", T_COUNT=" << client_t_count << endl;

        if (client_tid == 0 || client_t_count == 0) {
            cerr << CLR_RED << "[Dispatcher] Invalid or empty handshake from client. Closing connection." << CLR_RESET << endl;
            close(client_connection_fd);
            continue;
        }
        
        // 2. Read the command line reliably.
        string command_line = read_line_from_socket(client_connection_fd);
        //   cout << "[Dispatcher] Received command: \"" << command_line << "\"" << endl;
        if (command_line.empty()) {
            cerr << CLR_RED << "[Dispatcher] Client disconnected after handshake, before sending command. Closing." << CLR_RESET << endl;
            close(client_connection_fd);
            continue;
        }
        
        // 3. Call the parser with the command line.
        RequestPacket task = parse_client_request((char*)command_line.c_str(), client_connection_fd, client_tid, client_t_count);

        if (task.type != RequestPacket::CMD_NONE) {
            //   cout << "[Dispatcher] Request parsed successfully. Adding task for '" << task.filename_on_server << "' to scheduler." << endl;
            g_scheduler->add(task);
        } else {
            //   cout << "[Dispatcher] Request parsing failed. Sending error to client and closing connection." << endl;
            string error_msg = "ERROR Malformed or invalid request\n";
            send(client_connection_fd, error_msg.c_str(), error_msg.length(), 0);
            close(client_connection_fd);
        }
    }
}

RequestPacket parse_client_request(char* buffer, int client_socket, int client_tid, int client_t_count) {
    //   cout << "[Parser] Parsing buffer: \"" << buffer << "\"" << endl;
    RequestPacket req;
    req.client_fd = client_socket;
    req.arrival_t = chrono::steady_clock::now();
    req.type = RequestPacket::CMD_NONE;
    req.client_thread_id = client_tid;
    req.total_client_threads = client_t_count;

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
        string fullpath;
        if (g_config.path_is_dir) {
            fullpath = g_config.file_path + file_str;
        } else {
            if (filesystem::path(g_config.file_path).filename() == file_str) {
                fullpath = g_config.file_path;
            } else {
                req.f_size = -1;
                return req;
            }
        }
        try {
            if (filesystem::exists(fullpath) && !filesystem::is_directory(fullpath)) req.f_size = filesystem::file_size(fullpath);
            else req.f_size = -1;
        } catch (...) { req.f_size = -1; }
        //   cout << "[Parser] Parsed GET request for '" << file_str << "'. Full path: '" << fullpath << "'. Size: " << req.f_size << endl;
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
            if (req.f_size < 0) {
                cerr << CLR_RED << "[Request Parser] Malformed PUT: Negative file size." << CLR_RESET << endl;
                return req;
            }
            req.type = RequestPacket::CMD_PUT;
        } catch (...) {
            cerr << CLR_RED << "[Request Parser] Malformed PUT: Invalid file size value." << CLR_RESET << endl;
            return req;
        }
        //   cout << "[Parser] Parsed PUT request for '" << file_str << "'. Size: " << req.f_size << endl;
    } else {
        cerr << CLR_RED << "[Request Parser] Invalid command: '" << cmd_str << "'" << CLR_RESET << endl;
    }
    
    return req;
}

bool handle_get_request(RequestPacket& task) {
    //   cout << "  [GET Handler] Handling GET for '" << task.filename_on_server << "' from client TID " << task.client_thread_id << endl;
    string file_path;
    if (g_config.path_is_dir) file_path = g_config.file_path + task.filename_on_server;
    else if (task.f_size != -1) file_path = g_config.file_path;

    if (file_path.empty() || task.f_size == -1) {
        //   cout << "  [GET Handler] File not found. Sending ERROR." << endl;
        send(task.client_fd, "ERROR File not found\n", 20, 0);
        return true;
    }
    ifstream file_to_send(file_path);
    if (!file_to_send.is_open()) {
        //   cout << "  [GET Handler] Cannot open file. Sending ERROR." << endl;
        send(task.client_fd, "ERROR Cannot open file\n", 23, 0);
        return true;
    }
    if (task.lines_processed == 0) {
        //   cout << "  [GET Handler] First chunk. Sending OK." << endl;
        send(task.client_fd, "OK\n", 3, 0);
    }
    if (task.lines_processed > 0) {
        //   cout << "  [GET Handler] Resuming download. Skipping " << task.lines_processed << " lines." << endl;
        for (int i = 0; i < task.lines_processed; ++i) file_to_send.ignore(numeric_limits<streamsize>::max(), '\n');
    }

    if (g_config.sched_policy != "rr") {
        //   cout << "  [GET Handler] Sending entire file content." << endl;
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
        //   cout << "  [GET Handler] Sending quantum of " << g_config.quantum_val << " packets." << endl;
        string line, buf; int lines_in_pkt = 0, pkts_sent = 0;
        while (getline(file_to_send, line)) {
            buf.append(line).append("\n"); lines_in_pkt++; task.lines_processed++;
            if (lines_in_pkt >= g_config.packet_lines) {
                send(task.client_fd, buf.c_str(), buf.size(), 0); buf.clear(); lines_in_pkt = 0; pkts_sent++;
                if (pkts_sent >= g_config.quantum_val) {
                    //   cout << "  [GET Handler] Quantum finished. " << task.lines_processed << " lines processed total." << endl;
                    if (file_to_send.peek() == EOF) return true;
                    return false;
                }
            }
        }
        if (!buf.empty()) send(task.client_fd, buf.c_str(), buf.size(), 0);
        //   cout << "  [GET Handler] Reached EOF before quantum finished." << endl;
        return true;
    }
}

bool handle_put_request(RequestPacket& task) {
    string file_path = g_config.file_path + task.filename_on_server;
    //   cout << "  [PUT Handler] Handling PUT for '" << task.filename_on_server << "'. Saving to '" << file_path << "'" << endl;
    
    if (filesystem::exists(file_path)) {
        cerr << CLR_YELLOW << "  [Worker] Warning: Overwriting existing file '" << task.filename_on_server << "'" << CLR_RESET << endl;
    }

    ofstream received_file(file_path, ios::binary);
    if (!received_file.is_open()) {
        //   cout << "  [PUT Handler] Could not create file on server. Sending ERROR." << endl;
        send(task.client_fd, "ERROR Cannot create file on server\n", 35, 0);
        return true;
    }
    
    //   cout << "  [PUT Handler] File opened. Sending OK_READY." << endl;
    send(task.client_fd, "OK_READY\n", 9, 0);
    char recv_buffer[4096] = {0};
    int bytes_received;
    long total_bytes_received = 0;
    while ((bytes_received = recv(task.client_fd, recv_buffer, sizeof(recv_buffer), 0)) > 0) {
        received_file.write(recv_buffer, bytes_received);
        total_bytes_received += bytes_received;
        //   cout << "  [PUT Handler] Received " << bytes_received << " bytes. Total: " << total_bytes_received << endl;
    }
    //   cout << "  [PUT Handler] Finished receiving file. Total size: " << total_bytes_received << " bytes." << endl;
    return true;
}

void worker_routine(int id) {
    string worker_name = "Worker-" + to_string(id);
    cout << "  " << worker_name << " has started." << endl;
    for (;;) {
        //   cout << "  " << worker_name << ": Waiting for a task from the scheduler." << endl;
        RequestPacket task = g_scheduler->get_next();
        //   cout << "  " << worker_name << ": Got a task for file '" << task.filename_on_server << "' from client TID " << task.client_thread_id << endl;
        if (task.is_new_task) {
            //   cout << "  " << worker_name << ": This is a new task. Recording start time." << endl;
            task.start_t = chrono::steady_clock::now();
            task.is_new_task = false;
        }
        
        string action_str = (task.type == RequestPacket::CMD_GET) ? "GET" : "PUT";
        cout << CLR_YELLOW << "  " << worker_name << ": Starting " << action_str << " on '" << task.filename_on_server << "'" << CLR_RESET << endl;

        bool task_finished = false;
        if (task.type == RequestPacket::CMD_GET) task_finished = handle_get_request(task);
        else if (task.type == RequestPacket::CMD_PUT) task_finished = handle_put_request(task);
        
        if (task_finished) {
            //   cout << "  " << worker_name << ": Task finished. Closing client FD and logging results." << endl;
            task.finish_t = chrono::steady_clock::now();
            close(task.client_fd);

            auto arrival_ms = chrono::time_point_cast<chrono::milliseconds>(task.arrival_t).time_since_epoch().count();
            auto start_ms = chrono::time_point_cast<chrono::milliseconds>(task.start_t).time_since_epoch().count();
            auto finish_ms = chrono::time_point_cast<chrono::milliseconds>(task.finish_t).time_since_epoch().count();
            double response_time_ms = chrono::duration<double, milli>(task.finish_t - task.arrival_t).count();
            double wait_time_ms = chrono::duration<double, milli>(task.start_t - task.arrival_t).count();
            double file_size_kb = (task.f_size >= 0) ? static_cast<double>(task.f_size) / 1024.0 : 0.0;

            cout << CLR_GREEN << "  " << worker_name << ": Finished '" << task.filename_on_server << "'. Wait: " << wait_time_ms << "ms. Response: " << response_time_ms << "ms." << CLR_RESET << endl;

            ofstream results_file("results.csv", ios::app);
            if (results_file.is_open()) {
                results_file << g_config.thread_count << ","
                             << task.total_client_threads << ","
                             << id << ","
                             << task.client_thread_id << ","
                             << g_config.sched_policy << ","
                             << g_config.packet_lines << ","
                             << (g_config.sched_policy == "rr" ? g_config.quantum_val : 0) << ","
                             << g_config.file_path << ","
                             << task.filename_on_server << ","
                             << action_str << ","
                             << fixed << setprecision(3) << file_size_kb << ","
                             << arrival_ms << ","
                             << start_ms << ","
                             << finish_ms << ","
                             << fixed << setprecision(3) << response_time_ms << ","
                             << fixed << setprecision(3) << wait_time_ms << "\n";
            }
        } else {
            //   cout << "  " << worker_name << ": Task NOT finished (quantum expired). Re-adding to scheduler." << endl;
            cout << CLR_YELLOW << "  " << worker_name << ": Quantum finished for '" << task.filename_on_server << "'. Re-queuing." << CLR_RESET << endl;
            g_scheduler->add(task);
        }
    }
}
