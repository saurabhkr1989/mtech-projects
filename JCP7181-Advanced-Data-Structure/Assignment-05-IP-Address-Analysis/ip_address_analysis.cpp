/*
 * JCP7181: Advanced Data Structure and Algorithms Lab
 * Assignment 5: IP Address Analysis
 *
 * Reconstructs IPv4 addresses from digit strings, groups them
 * by subnet (Trie), and finds the largest cluster (DSU).
 *
 * All data structures are manually implemented.
 */

// Standard libraries
#include <iostream>
#include <string>
#include <vector>
#include <iomanip>
#include <stdexcept>
#include <algorithm>
#include <fstream>

// ---
// SECTION 1: MANUAL IMPLEMENTATION OF DISJOINT SET UNION (DSU)
// ---

/*
 This is our DSU implementation, often called Union-Find.
 It's responsible for managing the clusters of IPs.
 We're using path compression and union-by-size for efficiency.
*/
class ClusterUnion {
private:
    int* parent; // parent[i] = i if 'i' is a set representative (leader).
    int* setSize; // Stores size of the set, only valid for leader nodes.
    int largestClusterSize; // Tracks the max cluster size found so far.
    int totalElements; // Total number of elements in the DSU.

public:
    // Constructor
    ClusterUnion(int numberOfElements) {
        // protect against bad_alloc if N=0
        if (numberOfElements <= 0) {
            this->totalElements = 0;
            this->parent = nullptr;
            this->setSize = nullptr;
            this->largestClusterSize = 0;
            return;
        }

        this->totalElements = numberOfElements;
        this->largestClusterSize = 1; // Everything starts in a cluster of 1
        
        this->parent = new int[totalElements];
        this->setSize = new int[totalElements];

        // Initialize all elements as their own parents.
        for (int i = 0; i < totalElements; ++i) {
            parent[i] = i;
            setSize[i] = 1;
        }
    }

    // Owns raw pointers (parent/setSize); copying would double-free on destruction.
    // No copy is ever made in this program, but disabling it explicitly is safer
    // than relying on that staying true if this class is reused elsewhere.
    ClusterUnion(const ClusterUnion&) = delete;
    ClusterUnion& operator=(const ClusterUnion&) = delete;

    // Destructor - cleanup
    ~ClusterUnion() {
        if (this->parent != nullptr) {
            delete[] this->parent;
        }
        if (this->setSize != nullptr) {
            delete[] this->setSize;
        }
    }

    // Finds the representative (leader) of an element's set.
    // This implements path compression.
    int findSetRepresentative(int elementIndex) {
        // Base case
        if (parent[elementIndex] == elementIndex) {
            return elementIndex;
        }

        // Recursive call + path compression.
        // This flattens the tree by setting parent directly to the root.
        parent[elementIndex] = findSetRepresentative(parent[elementIndex]);
        return parent[elementIndex];
    }

    // Merges the sets containing two elements.
    void uniteSets(int elementA, int elementB) {
        int leaderA = findSetRepresentative(elementA);
        int leaderB = findSetRepresentative(elementB);

        // Only merge if they aren't already in the same set.
        if (leaderA != leaderB) {
            /*
             Union-by-size optimization:
             Attach the smaller tree to the root of the larger tree.
             This keeps the overall tree structure flatter and avoids
             long, skinny trees, which are slow to traverse.
            */
            if (setSize[leaderA] < setSize[leaderB]) {
                parent[leaderA] = leaderB;
                setSize[leaderB] += setSize[leaderA];
                // Check if this new merged set is the biggest one yet.
                largestClusterSize = std::max(largestClusterSize, setSize[leaderB]);
            } else {
                // Attach B to A (handles A > B and A == B).
                parent[leaderB] = leaderA;
                setSize[leaderA] += setSize[leaderB];
                largestClusterSize = std::max(largestClusterSize, setSize[leaderA]);
            }
        }
    }

    // Simple getter for the final result.
    int getLargestClusterSize() const {
        if (totalElements == 0) {
            return 0;
        }
        return this->largestClusterSize;
    }
};

// ---
// SECTION 2: MANUAL IMPLEMENTATION OF SUBNET TRIE
// ---

/*
 This struct is the basic building block for our Trie.
 Since IPv4 octets are 0-255, we use a 256-child array.
 This is *not* a bit-based trie, it's octet-based, which
 works perfectly for the /8, /16, /24 requirement.
*/
struct TrieNode {
    // 0-255 for octet values
    TrieNode* children[256];

    /*
     This is the key to linking the Trie and the DSU.
     It stores the index of the *first* IP we ever saw
     for this particular subnet.
     -1 means this subnet node is "unclaimed".
    */
    int firstIpIndex;

    // Constructor for a new TrieNode.
    TrieNode() : firstIpIndex(-1) {
        for (int i = 0; i < 256; ++i) {
            children[i] = nullptr;
        }
    }

    // Owns its children via raw pointers; copying would double-free on destruction.
    // Never copied in this program, but disabled explicitly for the same reason as
    // ClusterUnion above.
    TrieNode(const TrieNode&) = delete;
    TrieNode& operator=(const TrieNode&) = delete;

    /*
     Destructor
     This will recursively delete all child nodes, which is
     crucial to avoid a massive memory leak. MUST have this.
    */
    ~TrieNode() {
        for (int i = 0; i < 256; ++i) {
            if (children[i] != nullptr) {
                delete children[i];
            }
        }
    }
};

/*
 This Trie class is specialized for IP subnets.
 Its main jobs are:
 1. Count unique subnets.
 2. Give us a "representative index" for any given IP,
    so we know which cluster to join in the DSU.
*/
class SubnetTrie {
private:
    TrieNode* root;
    int uniqueSubnetCount;

public:
    // Constructor.
    SubnetTrie() {
        root = new TrieNode();
        uniqueSubnetCount = 0;
    }

    // Destructor. Deleting the root triggers the recursive delete.
    ~SubnetTrie() {
        delete root;
    }

    /*
     This is the main workhorse function for the Trie.
     It crawls down the trie based on the prefix length (e.g., 3 levels for /24).
     If it reaches a node for a subnet it's never seen before,
     it "claims" that node with the current IP's index and
     increments the unique subnet count.
     
     It *always* returns the index of the first IP that
     ever claimed this subnet (the "leader").
    */
    int findAndSetRepresentative(const std::vector<int>& ipOctets, int subnetPrefixLength, int currentIpIndex) {
        // 8->1, 16->2, 24->3
        int octetsToInsert = subnetPrefixLength / 8;

        TrieNode* crawler = root; // Start at the root

        // "Crawl" down the Trie for each octet in the subnet.
        for (int i = 0; i < octetsToInsert; ++i) {
            int octetValue = ipOctets[i];
            
            // If the path doesn't exist, create it.
            if (crawler->children[octetValue] == nullptr) {
                crawler->children[octetValue] = new TrieNode();
            }
            
            // Move down.
            crawler = crawler->children[octetValue];
        }

        // Now, `crawler` points to the node for this exact subnet.
        // Have we seen it before?
        if (crawler->firstIpIndex == -1) {
            // No. This is a new, unique subnet.
            // Claim it with the current IP's index.
            crawler->firstIpIndex = currentIpIndex;
            // Increment our counter.
            this->uniqueSubnetCount++;
        }

        // Return the "leader" index for this subnet.
        return crawler->firstIpIndex;
    }

    // Another simple getter.
    int getUniqueSubnetCount() const {
        return this->uniqueSubnetCount;
    }
};

// ---
// SECTION 3: IP RECONSTRUCTION (Backtracking) & UTILITIES
// ---

// Namespace for helper functions
namespace utility {

    /*
     Checks 0-255.
     Also handles the "no leading zeros" rule (e.g. "01" is bad, "0" is ok).
     This is the trickiest part of the validation.
    */
    bool isValidOctet(const std::string& octetString) {
        // Reject "01", "007", etc.
        if (octetString.length() > 1 && octetString[0] == '0') {
            return false;
        }

        // Just in case.
        if (octetString.empty()) {
            return false;
        }

        // Use std::stoll for safe conversion, check range.
        long long value = 0;
        try {
            value = std::stoll(octetString);
        } catch (...) {
            return false; // Not a number
        }
        
        return value >= 0 && value <= 255;
    }

    // Simple helper to turn {255, 255, 11, 135} into "255.255.11.135".
    std::string formatIpAddress(const std::vector<int>& ipOctets) {
        std::string result = "";
        result += std::to_string(ipOctets[0]);
        result += ".";
        result += std::to_string(ipOctets[1]);
        result += ".";
        result += std::to_string(ipOctets[2]);
        result += ".";
        result += std::to_string(ipOctets[3]);
        return result;
    }
} // namespace utility


// Namespace for the core reconstruction logic
namespace core_logic {

    /*
     This is the core backtracking function.
     It recursively explores the digit string to find all
     partitions that form 4 valid octets.
     
     It works by trying to take 1, 2, or 3 digits at a time.
     If the segment is a valid octet, it recurses.
     When it returns, it "backtracks" by popping the
     octet off the list and trying a longer segment.
    */
    void reconstructAddresses(
        const std::string& originalString,
        int startIndex,
        std::vector<int>& currentOctets,
        std::vector<std::vector<int>>& allFoundAddresses
    ) {
        // --- Base Cases ---
        
        // SUCCESS: We've formed 4 octets AND used up the whole string.
        if (currentOctets.size() == 4 && startIndex == originalString.length()) {
            allFoundAddresses.push_back(currentOctets);
            return;
        }

        // FAIL: We either have 4 octets but leftover string,
        // or we ran out of string before getting 4 octets.
        if (currentOctets.size() == 4 || startIndex == originalString.length()) {
            return;
        }

        // --- Recursive Step ---
        // Try to form the next octet using 1, 2, or 3 digits.
        for (int length = 1; length <= 3; ++length) {
            
            // Don't read past the end of the string.
            if (startIndex + length > originalString.length()) {
                break;
            }

            // Get the substring.
            std::string octetString = originalString.substr(startIndex, length);

            // Check if it's a valid octet
            if (utility::isValidOctet(octetString)) {
                
                // --- Explore ---
                // It's valid, so add it to our path.
                int octetValue = std::stoi(octetString);
                currentOctets.push_back(octetValue);

                // Recurse for the *rest* of the string.
                reconstructAddresses(
                    originalString,
                    startIndex + length, // Move the index forward
                    currentOctets,
                    allFoundAddresses
                );

                // --- Backtrack ---
                // The recursive call is done, so remove the octet
                // to try the next path (e.g., "11" after trying "1").
                currentOctets.pop_back();
            }
        }
    }

} // namespace core_logic

// ---
// SECTION 4: MAIN PROGRAM
// ---

// ANSI color codes for pretty console output.
const std::string COLOR_RESET = "\033[0m";
const std::string COLOR_RED = "\033[31m";
const std::string COLOR_GREEN = "\033[32m";
const std::string COLOR_YELLOW = "\033[33m";
const std::string COLOR_CYAN = "\033[36m";


// Main entry point
int main() {
    
    std::cout << COLOR_CYAN << "Starting IP Address Analyzer..." << COLOR_RESET << "\n";

    std::ifstream fin("input.txt");
    std::ofstream fout("output.txt");

    // check input file
    if (!fin.is_open()) {
        std::cerr << COLOR_RED << "Error: Could not open input.txt." 
                  << " Please ensure the file exists in the same directory." 
                  << COLOR_RESET << "\n";
        return 1; // Exit with error
    }
    std::cout << COLOR_GREEN << "Successfully opened input.txt." << COLOR_RESET << "\n";

    // check output file
    if (!fout.is_open()) {
        std::cerr << COLOR_RED << "Error: Could not create or open output.txt."
                  << " Please check file permissions." << COLOR_RESET << "\n";
        fin.close(); 
        return 1; // Exit with error
    }
    std::cout << COLOR_GREEN << "Successfully opened output.txt for writing." << COLOR_RESET << "\n";


    // --- Read and validate the header line (N and S) ---

    int numberOfEntries = 0;
    int subnetPrefixLength = 0;
    int expectedEntries = 0; // Store the original N for a final check.

    try {
        // Read N and S, store original N
        fin >> numberOfEntries >> subnetPrefixLength;
        expectedEntries = numberOfEntries;

        // check for read failure (e.g., file was empty or "hello")
        if (fin.fail()) {
            throw std::runtime_error("Invalid input from file. Expected two numbers (N and S).");
        }

        // Validate values based on assignment constraints
        if (numberOfEntries <= 0 || numberOfEntries > 100000) {
            throw std::runtime_error("Number of entries (N) must be between 1 and 100,000.");
        }
        if (subnetPrefixLength != 8 && subnetPrefixLength != 16 && subnetPrefixLength != 24) {
            throw std::runtime_error("Subnet prefix (S) must be 8, 16, or 24.");
        }

    } catch (const std::runtime_error& e) {
        std::cerr << COLOR_RED << "Input Error: " << e.what() << COLOR_RESET << "\n";
        fin.close();
        fout.close();
        return 1;
    }

    std::cout << COLOR_CYAN << "Processing " << numberOfEntries << " log entries with /" 
              << subnetPrefixLength << " subnet..." << COLOR_RESET << "\n";

    // --- Main loop: process each log entry ---
    
    // This will hold ALL valid IPs we find, from all lines.
    std::vector<std::vector<int>> allReconstructedIPs;
    
    // This just holds the formatted strings (e.g. "1.2.3.4")
    // but only if N is small, for the optional output.
    std::vector<std::string> ipStringsForOptionalOutput;

    for (int i = 0; i < numberOfEntries; ++i) {
        std::string corruptedLogEntry;
        fin >> corruptedLogEntry;

        /*
         What if N=20 but the file only has 10 lines?
         We need to check for a premature End-of-File.
         If fin.fail() is true, we just stop the loop.
        */
        if (fin.fail()) {
            // Silently update the *actual* count of entries we read.
            numberOfEntries = i;
            break; // Stop the processing loop.
        }

        // This will hold IPs found *just from this one line*.
        std::vector<std::vector<int>> ipsFromThisEntry;
        std::vector<int> currentOctets; // "path" for backtracking

        // Start the recursive reconstruction
        core_logic::reconstructAddresses(
            corruptedLogEntry,
            0, // Start from index 0
            currentOctets,
            ipsFromThisEntry
        );

        // Add the results to our master list
        if (!ipsFromThisEntry.empty()) {
            allReconstructedIPs.insert(
                allReconstructedIPs.end(),
                ipsFromThisEntry.begin(),
                ipsFromThisEntry.end()
            );

            // This is for the optional output requirement.
            // If N <= 5, we format and save the strings.
            if (numberOfEntries <= 5) {
                for (const auto& ip : ipsFromThisEntry) {
                    ipStringsForOptionalOutput.push_back(utility::formatIpAddress(ip));
                }
            }
        }
    }

    // Done with the input file.
    fin.close();

    // Now, report if N from the header didn't match what we read.
    if (expectedEntries != numberOfEntries) {
        std::cout << COLOR_YELLOW << "Input Info: The file header specified " << expectedEntries 
                  << " entries, but only " << numberOfEntries 
                  << " entries were found and processed." << COLOR_RESET << "\n";
    }
    // --- End of main loop ---

    std::cout << COLOR_CYAN << "Reconstruction complete. Found " 
              << allReconstructedIPs.size() << " total valid IPs." << COLOR_RESET << "\n";

    // --- Analysis Phase: Populate Trie and DSU ---

    long long totalValidIPs = allReconstructedIPs.size();

    // Handle the edge case where no valid IPs were found at all.
    if (totalValidIPs == 0) {
        std::cout << COLOR_YELLOW << "No valid IPs were reconstructed. Writing zero results to output.txt." << COLOR_RESET << "\n";
        if (numberOfEntries <= 5) {
            fout << "Reconstructed Valid IP Addresses:" << "\n";
            fout << "(None found)" << "\n";
        }
        fout << "\n" << "Total Valid IPs: 0" << "\n";
        fout << "Unique Subnets: 0" << "\n";
        fout << "Largest Cluster Size: 0" << "\n";
        
        fout.close();
        return 0; // Successful execution.
    }

    std::cout << COLOR_CYAN << "Organizing and clustering subnets..." << COLOR_RESET << "\n";

    // 1. Initialize the Trie.
    SubnetTrie subnetTrie;
    
    // 2. Initialize the DSU. It needs one set for every single IP.
    ClusterUnion clusterManager(static_cast<int>(totalValidIPs));

    // Now, iterate through every IP and feed it to the Trie and DSU.
    for (int i = 0; i < totalValidIPs; ++i) {
        const auto& ip = allReconstructedIPs[i];

        /*
         This is the "handshake".
         First, ask the Trie: "What's the representative index for this IP's subnet?"
         The Trie will also count unique subnets as it goes.
        */
        int representativeIndex = subnetTrie.findAndSetRepresentative(
            ip,
            subnetPrefixLength,
            i // The current IP's unique index
        );

        /*
         Second, tell the DSU: "Merge the set for this IP (i)
         with the set for its subnet representative."
         This groups all IPs in the same subnet into one DSU component.
        */
        clusterManager.uniteSets(i, representativeIndex);
    }

    // --- Final Report Generation ---

    // Get the final numbers from our data structures.
    int uniqueSubnets = subnetTrie.getUniqueSubnetCount();
    int largestCluster = clusterManager.getLargestClusterSize();

    // Handle the optional output for small N.
    if (numberOfEntries <= 5) {
        fout << "Reconstructed Valid IP Addresses:" << "\n";
        for (const std::string& ipString : ipStringsForOptionalOutput) {
            fout << ipString << "\n";
        }
    }

    // Write the main analysis summary to output.txt.
    fout << "\n" << "Total Valid IPs: " << totalValidIPs << "\n";
    fout << "Unique Subnets: " << uniqueSubnets << "\n";
    fout << "Largest Cluster Size: " << largestCluster << "\n";

    // Done.
    fout.close();

    std::cout << COLOR_GREEN << "Analysis complete. Results written to output.txt." << COLOR_RESET << "\n";

    return 0; // Success
}