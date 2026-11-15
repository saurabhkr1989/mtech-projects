#include <iostream>
#include <vector>
#include <string>
#include <thread>
#include <fstream>
#include <sstream>
#include <filesystem>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <algorithm>
#include <chrono>

#include "nlohmann/json.hpp"
#include "utils.hpp"

using namespace std;
using json = nlohmann::json;

struct Mission {
    string command;
    string filename;
};

void run_mission(int thread_id, int total_threads, const string& data_dir, const vector<Mission>& missions, const string& ip, int port) {
    for (const auto& m : missions) {
        int sock = socket(AF_INET, SOCK_STREAM, 0);
        struct sockaddr_in server_addr;
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(port);
        inet_pton(AF_INET, ip.c_str(), &server_addr.sin_addr);

        if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
            cerr << CLR_RED << "Thread " << thread_id << ": Connection to load balancer " << ip << ":" << port << " failed." << CLR_RESET << endl;
            close(sock);
            continue;
        }

        // --- SEND HANDSHAKE AND COMMAND AS TWO SEPARATE LINES ---
        string handshake_msg = "TID=" + to_string(thread_id) + " T_COUNT=" + to_string(total_threads) + "\n";
        write(sock, handshake_msg.c_str(), handshake_msg.length());

        cout << "Thread " << thread_id << " is performing a " << m.command << " request for " << m.filename << endl;
        auto start_time = chrono::steady_clock::now();
        
        if (m.command == "GET") {
            string request = "GET " + m.filename + "\n";
            write(sock, request.c_str(), request.length());
            
            char response_header[256] = {0};
            read(sock, response_header, 255);

            if (string(response_header).rfind("OK", 0) == 0) {
                string local_path = data_dir + "/" + m.filename;
                ofstream file(local_path, ios::binary);
                
                char buffer[4096];
                int bytes_read;
                while ((bytes_read = read(sock, buffer, sizeof(buffer))) > 0) {
                    file.write(buffer, bytes_read);
                }
            } else {
                string error_str(response_header);
                error_str.erase(std::remove(error_str.begin(), error_str.end(), '\n'), error_str.end());
                cerr << CLR_RED << "Thread " << thread_id << " (GET " << m.filename << ") received error: " << error_str << CLR_RESET << endl;
            }
        } else if (m.command == "PUT") {
            string local_path = data_dir + "/" + m.filename;
            long f_size = 0;
            try {
                f_size = filesystem::file_size(local_path);
            } catch(...) {
                cerr << CLR_RED << "Thread " << thread_id << ": Cannot find local file to PUT: '" << local_path << "'. Skipping." << CLR_RESET << endl;
                close(sock);
                continue;
            }
            
            string request = "PUT " + m.filename + " SIZE=" + to_string(f_size) + "\n";
            write(sock, request.c_str(), request.length());

            char response_header[256] = {0};
            read(sock, response_header, 255);
            
            if (string(response_header).rfind("OK_READY", 0) == 0) {
                ifstream file_to_send(local_path, ios::binary);
                if (file_to_send.is_open()) {
                    vector<char> file_data((istreambuf_iterator<char>(file_to_send)), istreambuf_iterator<char>());
                    write(sock, file_data.data(), file_data.size());
                } else {
                     cerr << CLR_RED << "Thread " << thread_id << ": Error opening local file for reading: '" << local_path << "'" << CLR_RESET << endl;
                }
            } else {
                string error_str(response_header);
                error_str.erase(std::remove(error_str.begin(), error_str.end(), '\n'), error_str.end());
                cerr << CLR_RED << "Thread " << thread_id << " (PUT " << m.filename << ") received error: " << error_str << CLR_RESET << endl;
            }
        }
        
        auto end_time = chrono::steady_clock::now();
        auto duration = chrono::duration_cast<chrono::milliseconds>(end_time - start_time).count();
        cout << CLR_GREEN << "Thread " << thread_id << ": Finished " << m.command << " for " << m.filename 
             << ". Took " << duration << " ms." << CLR_RESET << endl;
        
        shutdown(sock, SHUT_WR);
        close(sock);
    }
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        cerr << "Usage: ./client <command_file_path>" << endl;
        return 1;
    }
    string command_file = argv[1];

    json config;
    ifstream config_stream("config.json");
    if (!config_stream.is_open()) {
        cerr << CLR_RED << "Fatal Error: Could not open config.json." << CLR_RESET << endl;
        return 1;
    }
    
    try {
        config_stream >> config;
    } catch(const json::exception& e) {
        cerr << CLR_RED << "Fatal Error: Could not parse config.json. Details: " << e.what() << CLR_RESET << endl;
        return 1;
    }

    int num_client_threads; string lb_ip; int lb_port; string data_dir;
    try {
        num_client_threads = config.at("client_threads");
        lb_ip = config.at("lb_ip");
        lb_port = config.at("lb_port");
        data_dir = config.at("data_dir");
    } catch(const json::exception& e) {
        cerr << CLR_RED << "Fatal Error: config.json is missing required fields. Details: " << e.what() << CLR_RESET << endl;
        return 1;
    }

    try {
        filesystem::create_directory(data_dir);
    } catch(const filesystem::filesystem_error& e) {
        cerr << CLR_RED << "Fatal Error: Could not create data directory '" << data_dir << "'. Details: " << e.what() << CLR_RESET << endl;
        return 1;
    }

    vector<Mission> all_missions;
    ifstream mission_file(command_file);
    if (!mission_file.is_open()) {
        cerr << CLR_RED << "Fatal Error: Could not open command file '" << command_file << "'." << CLR_RESET << endl;
        return 1;
    }

    string line; int line_num = 0;
    while (getline(mission_file, line)) {
        line_num++;
        if (line.empty() || line[0] == '#') continue;
        
        stringstream ss(line);
        Mission m;
        
        if (ss >> m.command >> m.filename) {
            all_missions.push_back(m);
        } else {
            cerr << CLR_YELLOW << "Warning: Skipping malformed command on line " << line_num << ": \"" << line << "\"" << CLR_RESET << endl;
        }
    }

    cout << "Dispatching " << all_missions.size() << " valid missions across " << num_client_threads << " threads." << endl;

    vector<thread> thread_list;
    vector<vector<Mission>> mission_lists(num_client_threads);
    for (size_t i = 0; i < all_missions.size(); i++) {
        mission_lists[i % num_client_threads].push_back(all_missions[i]);
    }
    
    for (int i = 0; i < num_client_threads; i++) {
        if (!mission_lists[i].empty()) {
            thread_list.emplace_back(run_mission, i + 1, num_client_threads, data_dir, mission_lists[i], lb_ip, lb_port);
        }
    }
    
    for (auto& t : thread_list) {
        t.join();
    }

    cout << "All missions complete." << endl;
    return 0;
}

