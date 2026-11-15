
# Assignment 2 COL7524
# Part B : Multi-Threaded Client-Server System with Load Balancer

Project implements multi-threaded client-server architecture in C++ for file transfers with configurable load balancer & backend servers with selectable scheduling policies for simulating & measurement of performance of different load distribution & task scheduling strategies under concurrent load of multiple clients.

# `Directory Structure`
.
├─ src
│   ├─>> load_balancer.cpp       # Entry point for load balancer
│   ├─ server.cpp               # Backend server logic
│   └─> client.cpp              # Client application logic
├── include
│   ├── utils.hpp               # Shared utilities, structs, & scheduler classes
│   └─ nlohmann
│       └─ json.hpp             # JSON parsing library (dependency)
├── config.json                 # Configuration for IPs, ports & threads
├── Makefile                    # Build script for entire project
└─> commands.txt                 # Sample command file for client


# File Descriptions
***src/load_balancer.cpp:***  Starts & manages four backend server processes, performs periodic health checks & forwards incoming client connections to a backend server based on a selected algorithm (Round Robin or Least Connections)
***src/server.cpp:*** `Multi-threaded backend server` which receives requests forwarded by load balancer, processes file GET & PUT operations using a selectable scheduling policy (FCFS, SJF, or RR) & logs performance metrics for each request
***src/client.cpp:***  `Multi-threaded client application` that reads a command file to simulate concurrent users & connects to load balancer to send file transfer requests
***include/utils.hpp:***   Header file containing `shared data structures` (like RequestPacket), ANSI color codes for logging, & class definitions for FCFS, SJF, & RR schedulers.
***config.json:***  Configuration details like `network addresses` of load balancer, four backend servers and No of client threads.

***Makefile:*** `Build Script file` for compilation of all source files & making three separate executables (load_balancer, server & client).

## Getting Started

***1. Dependencies***

Ensure following are installed on Linux environment:

    C++ compiler with  C++17 support 

    make 

    nlohmann/json dependency. 

***2. Compilation***

    Run make command from root directory of project.

    make

    This will create an obj/ directory for intermediate files & place three executables (load_balancer, server, client) in root directory.

# Execution Steps

***Step 1: Prepare Client Files***

Create a commands.txt file: This file contains list of operations for client threads to execute. Each line should be in format COMMAND filename.txt.
Example commands.txt:

PUT file_1.txt
GET file_2.txt
PUT file_3.txt

Prepare files for upload: client will look for files to PUT in a directory specified by data_dir in config.json (default is ./client_data). Make sure any files you want to upload are placed in this directory.

**Step 2: Run Load Balancer ***

Open a terminal & start load balancer. You must specify load balancing algorithm, server scheduling policy, & other server configurations.

 ***Command Syntax: ***

 ***./load_balancer --algo <lb_algo> --sched <server_sched> --file <base_path> --threads <num> [--p <lines>] [--quantum <q>] ***


 ***Example 1 (Least Connections LB, FCFS Servers): ***

# LB uses Least Connections, servers use FCFS with 4 worker threads each.
# Server files will be stored in subdirectories of ./server_storage
./load_balancer --algo lc --sched fcfs --file ./server_data --threads 4


 ***Example 2 (Round Robin LB, Round Robin Servers): ***

# LB uses Round Robin, servers use RR with 2 threads & a quantum of 500 packets.
./load_balancer --algo rr --sched rr --file ./server_data --threads 2 --p 100 --quantum 500


The load balancer will start, automatically launch four backend server processes, & begin its health checks.

 ***Step 3: Run Client ***

Open a new, separate terminal & run client executable, passing path to your command file as an argument.

./client commands.txt
