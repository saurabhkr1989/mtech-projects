# Assignment 2 COL724/7524
# Part A: Link Scheduling

This is a multithreaded client-server system, built to compare job scheduling policies.

## Features

***Multithreaded Server:** Uses a dispatcher/worker model to handle multiple clients.
***Interactive Setup:** A simple console menu to configure the server when it starts.
***Selectable Schedulers:** Choose between First-Come, First-Served (FCFS) and Shortest Job First (SJF).
***File Transfers:** Supports `GET` (download from server) and `PUT` (upload to server) operations.
***Performance Logging:** Automatically logs detailed timing metrics for each request to `results.csv`.
***Real-time Console UI:** Color-coded output to monitor server and client activity.

##nlohmann

External library of nlohmann has been used for parsing the inputs from config.json

##Folder Structure
Project_Folder/
├── Makefile
├── config.json
├── missions.txt
├── data/server_files/<files>.txt           	<-- Server's root directory. GET requests of clients will be served from here.
├── data/            					<-- Client's  data directory. PUT requests of clients will be uploaded from here to data/server_files.
│   └── <files>.txt
└── src/
    ├── server.cpp
    └── client.cpp
└── include/
    ├── utils.hpp
    └── nlohmann/
        └── json.hpp

## How to Build

A `Makefile` is included. To compile the `server` and `client` executables, simply run `make` from your terminal in the project's root directory.

#bash
make

## How to run Server
./build/server --sched <policy> --file <server_data_directory> [options]

##To run with FCFS

./build/server --sched fcfs --file ./data_server/ --p 10

##To run with SJF

./build/server --sched sjf --file ./data_server/ --p 10

##To run with Round Robin

./build/server --sched rr --file ./data_server/ --p 10 --quantum 5


## How to run client
./build/client commands.txt

# Upload a file that exists in the data directory
PUT file_to_upload.txt

# Download the file  that exists in the data/server_files directory
GET file_to_upload.txt

##Output

## Performance data for every completed request is logged to results.csv. The file contains the following columns, making it easy to analyze the performance of the different schedulers.


***ServerThreads	The total number of worker threads the server was configured to use for this run.
***TotalClientThreads	The total number of concurrent threads the client application was running for this run.
***ServerThreadID	The specific ID of the server worker thread that processed this individual request.
***ClientThreadID	The specific ID of the client thread that sent this individual request.
***SchedulingPolicy	The scheduling algorithm (fcfs, sjf, rr) active on the server for this request.
***PacketLines	The number of lines grouped into a single network packet for GET requests (--p value).
***Quantum	The number of packets a worker could send in one turn under the Round Robin policy.
***BasePath	The root directory path the server was configured to serve files from.
***FileName	The name of the text file involved in the GET or PUT operation.
***RequestType	The type of operation performed, either GET (download) or PUT (upload).
***FileSizeKB	The size of the requested file, measured in Kilobytes (KB).
***ArrivalTime_ms	The timestamp in milliseconds when the request was first received by the server.
***StartTime_ms	The timestamp in milliseconds when a worker thread actually began processing the request.
***FinishTime_ms	The timestamp in milliseconds when the worker thread finished processing the request.
***ResponseTime_ms	The total duration (FinishTime - ArrivalTime) in milliseconds for the request to be fully serviced.
***WaitTime_ms	The duration (StartTime - ArrivalTime) in milliseconds the request spent waiting in the queue.