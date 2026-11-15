/**
 * @file 2025JCS3011_2.cpp
 * @brief Huffman Coding Compression and Decompression System
 *
 * This program implements a complete text compression and decompression utility
 * using the Huffman coding algorithm. It can operate in two modes:
 * 1. ENCODE: Reads a text string, builds an optimal Huffman tree based on
 * character frequencies, and outputs the compressed bitstring along with the
 * character-to-code mappings.
 * 2. DECODE: Reads a compressed bitstring and its corresponding code mappings,
 * and reconstructs the original text.
 *
 * The implementation is self-contained and uses standard C++ libraries.
 */

#include <iostream>
#include <string>
#include <queue>
#include <unordered_map>
#include <vector>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <memory>

// Define a character to represent internal nodes. Using a high ASCII value
// ensures it has low priority in the min-heap's tie-breaking.
const char INTERNAL_NODE_CHAR = (char)128;

// --- Huffman Tree Node Structure ---

/**
 * @struct HuffmanNode
 * @brief A node in the Huffman Tree.
 *
 * This structure represents a single node, which can either be a leaf node
 * (containing a character) or an internal node (connecting other nodes).
 */
struct HuffmanNode {
    char data; // The character stored in this node.
    unsigned freq; // The frequency of the character.
    HuffmanNode *left, *right; // Pointers to left and right children.

    // Constructor for a new node.
    HuffmanNode(char data, unsigned freq) : data(data), freq(freq), left(nullptr), right(nullptr) {}
};

// --- Comparator for the Priority Queue ---

/**
 * @struct CompareNodes
 * @brief A comparison utility for the min-heap.
 *
 * This is used by the priority_queue to order the nodes. It ensures that
 * the node with the lowest frequency has the highest priority. If frequencies
 * are tied, it uses the character's ASCII value as a tie-breaker.
 */
struct CompareNodes {
    bool operator()(HuffmanNode* l, HuffmanNode* r) {
        // Primary sort: The node with the lower frequency has higher priority.
        if (l->freq != r->freq) {
            return l->freq > r->freq;
        }
        // Secondary sort (tie-breaker): The node with the smaller character
        // value (lower ASCII) has higher priority.
        return l->data > r->data;
    }
};

// --- Main Huffman Coder Class ---

/**
 * @class HuffmanCoder
 * @brief Encapsulates the entire Huffman coding logic.
 *
 * This class provides two main functionalities: encoding (compressing) a
 * string and decoding (decompressing) a bitstring.
 */
class HuffmanCoder {
public:
    /**
     * @brief Main function to handle the encoding process.
     * @param inFile An input file stream to read the text from.
     * @param outFile An output file stream to write the compressed data to.
     */
    void encode(std::ifstream& inFile, std::ofstream& outFile) {
        std::cout << "--- Starting ENCODE process ---" << std::endl;
        // 1. Read the input string.
        std::string text;
        std::getline(inFile, text);
        std::cout << "1. Reading input text: \"" << text << "\"" << std::endl;

        // --- Input Validation Step ---
        std::cout << "2. Validating characters..." << std::endl;
        for (char c : text) {
            if (!is_allowed(c)) {
                std::cerr << "Error: Input string contains a disallowed character: '" << c << "'. Aborting encode." << std::endl;
                return;
            }
        }

        // 3. Count the frequency of each character.
        std::cout << "3. Calculating character frequencies..." << std::endl;
        std::unordered_map<char, unsigned> freqMap;
        for (char c : text) {
            freqMap[c]++;
        }
        for (auto const& [key, val] : freqMap) {
            std::cout << "   -> '" << key << "' : " << val << std::endl;
        }
        
        // Handle edge case of empty or single-character string
        if (freqMap.empty()) {
            std::cout << "   -> Input string is empty. Writing empty output." << std::endl;
            outFile << 0 << std::endl;
            outFile << "" << std::endl;
            return;
        }

        // 4. Build the Huffman Tree.
        std::cout << "4. Building Huffman Tree..." << std::endl;
        HuffmanNode* root = buildTree(freqMap);

        // 5. Generate Huffman codes by traversing the tree.
        std::cout << "5. Generating Huffman codes..." << std::endl;
        std::unordered_map<char, std::string> codes;
        generateCodes(root, "", codes);
         for (auto const& [key, val] : codes) {
            std::cout << "   -> '" << key << "' = " << val << std::endl;
        }

        // 6. Build the final encoded bitstring.
        std::cout << "6. Creating final encoded bitstring..." << std::endl;
        std::string encodedString = "";
        for (char c : text) {
            encodedString += codes[c];
        }

        // 7. Write the results to the output file.
        std::cout << "7. Writing compressed data to output.txt..." << std::endl;
        outFile << encodedString.length() << std::endl;
        outFile << encodedString << std::endl;

        // --- Sort the codes by character before printing ---
        std::vector<std::pair<char, std::string>> sortedCodes(codes.begin(), codes.end());
        std::sort(sortedCodes.begin(), sortedCodes.end());

        for (const auto& pair : sortedCodes) {
            outFile << pair.first << "=" << pair.second << std::endl;
        }
        
        // --- Improvement: Clean up the allocated memory for the tree. ---
        deleteTree(root);
        
        std::cout << "--- ENCODE process complete ---" << std::endl << std::endl;
    }

    /**
     * @brief Main function to handle the decoding process.
     * @param inFile An input file stream to read the compressed data from.
     * @param outFile An output file stream to write the original text to.
     */
    void decode(std::ifstream& inFile, std::ofstream& outFile) {
        std::cout << "--- Starting DECODE process ---" << std::endl;
        // 1. Read the compressed data: size, bitstring, and code mappings.
        std::cout << "1. Reading compressed data from input.txt..." << std::endl;
        long long size;
        std::string line, encodedString;
        
        inFile >> size;
        inFile >> encodedString;
        std::cout << "   -> Size in bits: " << size << std::endl;
        std::cout << "   -> Encoded string: " << encodedString.substr(0, 50) << "..." << std::endl; // Print first 50 chars
        
        std::cout << "   -> Reading code mappings..." << std::endl;
        std::unordered_map<std::string, char> codeToCharMap;
        while (std::getline(inFile, line)) {
            // Trim any trailing carriage returns or newlines from the line to prevent
            // parsing errors, especially with files created on Windows.
            while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) {
                line.pop_back();
            }

            if (line.find('=') != std::string::npos && line.length() > 1) {
                std::string code = line.substr(line.find('=') + 1);
                char character = line[0];
                codeToCharMap[code] = character;
                std::cout << "      '" << character << "' <- \"" << code << "\"" << std::endl;
            }
        }

        // 2. Decode the bitstring.
        std::cout << "2. Decoding bitstring..." << std::endl;
        std::string decodedString = "";
        std::string currentCode = "";
        for (char bit : encodedString) {
            currentCode += bit;
            if (codeToCharMap.count(currentCode)) {
                decodedString += codeToCharMap[currentCode];
                currentCode = "";
            }
        }
        
        // --- Improvement: Add robustness check for corrupted input. ---
        if (!currentCode.empty()) {
            std::cerr << "Warning: Corrupted data detected. Trailing bits did not form a valid code." << std::endl;
        }

        // 3. Write the reconstructed text to the output file.
        std::cout << "3. Writing decoded text to output.txt..." << std::endl;
        outFile << decodedString << std::endl;
        std::cout << "--- DECODE process complete ---" << std::endl << std::endl;
    }

private:
    /**
     * @brief Checks if a character is allowed by the assignment's rules.
     * @param c The character to check.
     * @return True if the character is allowed, false otherwise.
     */
    bool is_allowed(char c) {
        return (c >= 'a' && c <= 'z') ||
               (c >= 'A' && c <= 'Z') ||
               (c >= '0' && c <= '9') ||
               c == '_' || c == '-' || c == '.' || c == '(' || c == ')' || c == ',';
    }

    /**
     * @brief Builds the Huffman Tree from character frequencies.
     * @param freqMap A map of characters to their frequencies.
     * @return A pointer to the root node of the Huffman Tree.
     */
    HuffmanNode* buildTree(const std::unordered_map<char, unsigned>& freqMap) {
        // Create a min-priority queue to store the nodes.
        std::priority_queue<HuffmanNode*, std::vector<HuffmanNode*>, CompareNodes> minHeap;

        // Create a leaf node for each character and add it to the min-heap.
        for (auto const& [key, val] : freqMap) {
            minHeap.push(new HuffmanNode(key, val));
        }
        
        // Special case: If there's only one unique character, the loop won't run.
        // We need to create a simple tree manually.
        if (minHeap.size() == 1) {
            HuffmanNode* root = new HuffmanNode(INTERNAL_NODE_CHAR, minHeap.top()->freq);
            root->left = minHeap.top();
            minHeap.pop();
            minHeap.push(root);
        }

        // The main loop to build the tree.
        // It runs until only one node (the root) is left in the heap.
        while (minHeap.size() > 1) {
            // Extract the two nodes with the lowest frequencies.
            HuffmanNode* node1 = minHeap.top();
            minHeap.pop();
            HuffmanNode* node2 = minHeap.top();
            minHeap.pop();

            // Create a new internal node.
            HuffmanNode* top = new HuffmanNode(INTERNAL_NODE_CHAR, node1->freq + node2->freq);

            // To create a canonical (consistent) tree, we must enforce a strict
            // order for left and right children. The node with the overall "lesser"
            // value (lower frequency, or lower ASCII in a tie) MUST be the left child.
            CompareNodes comparator;
            if (comparator(node1, node2)) { // This means node1 has a "greater" value (lower priority).
                top->left = node2;
                top->right = node1;
            } else { // This means node1 has a "lesser" or equal value (higher priority).
                top->left = node1;
                top->right = node2;
            }

            // Add the new internal node back into the min-heap.
            minHeap.push(top);
        }
        
        // The last remaining node is the root of the tree.
        return minHeap.top();
    }

    /**
     * @brief Recursively traverses the Huffman tree to generate codes.
     * @param root The current node in the tree.
     * @param currentCode The bitstring code generated so far.
     * @param codes A reference to the map where codes are stored.
     */
    void generateCodes(HuffmanNode* root, std::string currentCode, std::unordered_map<char, std::string>& codes) {
        if (!root) {
            return;
        }

        // If we've reached a leaf node, we have found a code for a character.
        if (root->data != INTERNAL_NODE_CHAR) {
            // Handle the edge case of a single-character tree, which needs a code.
            if (currentCode.empty()) {
                codes[root->data] = "0";
            } else {
                codes[root->data] = currentCode;
            }
        }

        // For internal nodes, recursively call for left and right children.
        // Append '0' for the left path and '1' for the right path.
        generateCodes(root->left, currentCode + "0", codes);
        generateCodes(root->right, currentCode + "1", codes);
    }
    
    /**
     * @brief Recursively deletes the Huffman tree to prevent memory leaks.
     * @param node The current node to delete.
     */
    void deleteTree(HuffmanNode* node) {
        if (!node) {
            return;
        }
        deleteTree(node->left);
        deleteTree(node->right);
        delete node;
    }
};

/**
 * @brief Main entry point of the program.
 *
 * Reads the input file to determine the operation (ENCODE/DECODE) and
 * delegates the task to the HuffmanCoder class.
 */
int main() {
    std::cout << "--- Huffman Coder Initializing ---" << std::endl;
    std::ifstream inFile("input.txt");
    std::ofstream outFile("output.txt");

    if (!inFile.is_open()) {
        std::cerr << "Error: Could not open input.txt" << std::endl;
        return 1;
    }

    std::string mode;
    std::getline(inFile, mode); // Read the first line to get the mode.

    // --- FIX: Trim trailing whitespace/carriage returns from the mode string ---
    while (!mode.empty() && (mode.back() == '\r' || mode.back() == '\n')) {
        mode.pop_back();
    }
    
    std::cout << "Mode detected: " << mode << std::endl << std::endl;

    HuffmanCoder coder;

    if (mode == "ENCODE") {
        coder.encode(inFile, outFile);
    } else if (mode == "DECODE") {
        coder.decode(inFile, outFile);
    } else {
        std::cerr << "Error: Invalid mode specified in input.txt. Must be ENCODE or DECODE." << std::endl;
        return 1;
    }
    
    std::cout << "--- Program Terminated ---" << std::endl;
    return 0;
}

