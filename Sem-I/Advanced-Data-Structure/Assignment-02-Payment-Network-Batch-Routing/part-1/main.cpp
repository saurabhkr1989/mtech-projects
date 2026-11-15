#include <iostream>
#include <vector>
#include <fstream>
#include <limits>
#include <string>
#include "MinHeap.h"

using namespace std;

const int MAX_NODES = 1000, MAX_EDGES = 10000, MAX_CHECKPOINTS = 15;
const long long INF = numeric_limits<long long>::max();


struct Edge {
    int dest;
    long long delay; 
};


bool isValidInput(int N, int M, int k, int s, int t, const vector<int> &checkpoints) {
    if (N < 2 || N > MAX_NODES) return false;
    if (M < 1 || M > MAX_EDGES) return false;
    if (k < 0 || k > MAX_CHECKPOINTS) return false;
    if (s < 0 || s >= N || t < 0 || t >= N) return false;
    for (int c : checkpoints)
        if (c < 0 || c >= N) return false;
    return true;
}


long long shortestDelay(const vector<vector<Edge>> &adj, int start, int end) {
    vector<long long> dist(adj.size(), INF);
    MinHeap pq;
    dist[start] = 0;
    pq.push({0LL, start});
    while (!pq.empty()) {
        auto [currDelay, currNode] = pq.top(); pq.pop();
        if (currNode == end) return currDelay;
        if (currDelay > dist[currNode]) continue;
        for (const Edge &e : adj[currNode]) {
            if (dist[e.dest] > currDelay + e.delay) {
                dist[e.dest] = currDelay + e.delay;
                pq.push({dist[e.dest], e.dest});
            }
        }
    }
    return INF;
}


void showWelcomeScreen() {
    cout << "\n========================================\n";
    cout << " Payment Network Batch Routing Tool\n";
    cout << "========================================\n";
    cout << "Input format (all integers):\n";
    cout << "  N M               : Number of sites (2 <= N <= 1000), number of routes (1 <= M <= 10000)\n";
    cout << "  u v w (M times)   : Route from site u to v with delay w (0 <= u,v < N, 1 <= w <= 1000000000)\n";
    cout << "  k                 : Number of ordered checkpoints (0 <= k <= 15)\n";
    cout << "  c1 c2 ... ck      : (Only when k > 0) Checkpoint site IDs (each 0 <= ci < N)\n";
    cout << "  s t               : Start and target site IDs (each 0 <= id < N)\n";
    cout << "----------------------------------------\n";
    cout << "Choose input method each time:\n";
    cout << "  1 : Read from file 'input.txt'\n";
    cout << "  2 : Enter input manually\n";
    cout << "  3 : Exit\n";
    cout << "========================================\n\n";
}


bool readInput(int mode, int &N, int &M, vector<vector<Edge>> &adj, int &k, vector<int> &checkpoints, int &s, int &t) {
    std::istream* in = &cin;
    std::ifstream fin;

    if (mode == 1) {
        fin.open("input.txt");
        if (!fin.is_open()) {
            cout << "Error: Could not open 'input.txt'.\n";
            return false;
        }
        in = &fin;
        cout << "Reading input from file 'input.txt'...\n";
    }

    (*in) >> N >> M;
    if (mode == 1) cout << "N = " << N << ", M = " << M << "\n";
    if (N < 2 || N > MAX_NODES || M < 1 || M > MAX_EDGES) {
        cout << "Invalid N or M.\n";
        return false;
    }

    adj.assign(N, {});
    for (int i = 0; i < M; ++i) {
        int u, v;
        long long w;
        (*in) >> u >> v >> w;
        if (mode == 1) cout << "Edge " << i + 1 << ": u = " << u << ", v = " << v << ", w = " << w << "\n";
        if (u < 0 || u >= N || v < 0 || v >= N || w < 1 || w > 1000000000LL) {
            cout << "Invalid edge data.\n";
            return false;
        }
        adj[u].push_back({v, w});
    }

    (*in) >> k;
    if (mode == 1) cout << "Checkpoints k = " << k << "\n";
    if (k < 0 || k > MAX_CHECKPOINTS) {
        cout << "Invalid k.\n";
        return false;
    }
    checkpoints.clear();
    if (k > 0) {
        checkpoints.resize(k);
        if (mode == 1) cout << "Checkpoints IDs:";
        for (int i = 0; i < k; ++i) {
            (*in) >> checkpoints[i];
            if (mode == 1) cout << " " << checkpoints[i];
            if (checkpoints[i] < 0 || checkpoints[i] >= N) {
                cout << "\nInvalid checkpoint.\n";
                return false;
            }
        }
        if (mode == 1) cout << "\n";
    }

    (*in) >> s >> t;
    if (mode == 1) cout << "Start site s = " << s << ", target site t = " << t << "\n";
    if (s < 0 || s >= N || t < 0 || t >= N) {
        cout << "Invalid s or t.\n";
        return false;
    }

    if (!isValidInput(N, M, k, s, t, checkpoints)) {
        cout << "Input violates assignment constraints.\n";
        return false;
    }
    if (mode == 1) fin.close();
    return true;
}

int main() {
    showWelcomeScreen();
    while (true) {
        cout << "Input mode:\n";
        cout << "  [1] File input ('input.txt')\n";
        cout << "  [2] Manual entry\n";
        cout << "  [3] Exit\n";
        cout << "Choose option: ";
        int mode;
        cin >> mode;
        if (mode == 3) {
            cout << "Thank you for using the Payment Network Batch Routing Tool!\n";
            break;
        }
        if (mode != 1 && mode != 2) {
            cout << "Invalid mode selection. Try again.\n";
            continue;
        }

        int N = 0, M = 0, k = 0, s = 0, t = 0;
        vector<vector<Edge>> adj;
        vector<int> checkpoints;

        bool ok = readInput(mode, N, M, adj, k, checkpoints, s, t);

        if (!ok) {
            cout << "\nTry again with valid input.\n";
            continue; 
        }

        vector<int> itinerary; itinerary.push_back(s);
        itinerary.insert(itinerary.end(), checkpoints.begin(), checkpoints.end());
        itinerary.push_back(t);

        long long totalDelay = 0; bool possible = true;
        for (size_t i = 0; i + 1 < itinerary.size(); ++i) {
            long long segDelay = shortestDelay(adj, itinerary[i], itinerary[i + 1]);
            if (segDelay == INF) {
                possible = false;
                break;
            }
            totalDelay += segDelay;
        }

        cout << "----------------------------------------\n";
        if (possible)
            cout << "Minimum Total Delay: " << totalDelay << "\n";
        else
            cout << "Trip Impossible (-1)\n";
        cout << "----------------------------------------\n";
       
    }
    return 0;
}
