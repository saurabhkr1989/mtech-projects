/*
    JCP7181: Advanced Data Structure and Algorithms Lab
    Assignment 4, Part 2: 0/1 Knapsack Problem

    This program solves the 0/1 Knapsack problem using dynamic programming. It reads item values and weights, and a total capacity, from "input.txt". It then computes the maximum possible value that can be obtained
    without exceeding the capacity, where each item must be taken     either entirely or not at all.

    The solution is written to "output.txt".
*/

#include <iostream>     
#include <fstream>      
#include <vector>       // For dynamic arrays (std::vector)
#include <string>       // For string manipulation (std::string)
#include <stdexcept>    // For standard exceptions (std::runtime_error)
#include <iomanip>      // For output formatting (std::setw, std::fixed)
#include <numeric>      
#include <algorithm>    // For std::max

namespace colors {
    const std::string RESET = "\033[0m";
    const std::string RED = "\033[31m";
    const std::string GREEN = "\033[32m";
    const std::string YELLOW = "\033[33m";
    const std::string BLUE = "\033[34m";
    const std::string MAGENTA = "\033[35m";
    const std::string CYAN = "\033[36m";
}

//    Represents a single item. Original index is required to reconstruct the final 'selection' vector in the correct order.


struct Item {
    long long value;
    int weight;
    int originalIndex;
};


//    Function for the 0/1 Knapsack problem. Function implements a DP solution and then backtracks to find which items were selected.

void solveKnapsack(
    std::vector<Item>& itemsToProcess,
    int capacity,
    std::vector<int>& selectionVector,
    long long preAdjustedValue,
    std::ofstream& outputFile
) {
    int dpItemCount = itemsToProcess.size();

    /*
        dp[i][c] will store the maximum value obtainable using a subset of the first 'i' items (from itemsToProcess) with a total capacity of 'c'.

        Size is (dpItemCount + 1) x (capacity + 1) to handle the base cases (0 items or 0 capacity) easily.
    */
    std::vector<std::vector<long long>> dp(
        dpItemCount + 1,
        std::vector<long long>(capacity + 1, 0)
    );

    std::cout << colors::YELLOW << "Building 2D DP table ("
        << dpItemCount + 1 << " x " << capacity + 1 << ")..." << colors::RESET << std::endl;

    // Filling the DP table
    for (int i = 1; i <= dpItemCount; ++i) {
        // Get the current item. Note: itemsToProcess[i-1] corresponds to dp[i]
        const Item& item = itemsToProcess[i - 1];
        long long v = item.value;
        int w = item.weight;

        for (int c = 0; c <= capacity; ++c) {
            // Case 1: Current item cannot be selected (too heavy) 
            if (w > c) {
                dp[i][c] = dp[i - 1][c];
            }
            // Case 2: We can take the item
            else {
                /*
                    We two possibilities:
                    1. dp[i-1][c]:         We don't take the current item.
                    2. dp[i-1][c - w] + v: We take the current item.
                */
                dp[i][c] = std::max(dp[i - 1][c], dp[i - 1][c - w] + v);
            }
        }
    }
    std::cout << colors::GREEN << "DP table built." << colors::RESET << std::endl;

    // Max value from the DP-processed items is in the bottom right corner
    long long dpMaxValue = dp[dpItemCount][capacity];

    // --- Backtracking to find selected items ---
    std::cout << colors::YELLOW << "Backtracking to find selected items..." << colors::RESET << std::endl;
    int c = capacity;
    for (int i = dpItemCount; i > 0; --i) {
        
        //    We check if the value at dp[i][c] is different from dp[i-1][c]. If it is different, it means the value at dp[i][c] must have come from taking item 'i'.
        
        if (dp[i][c] != dp[i - 1][c]) {
            const Item& takenItem = itemsToProcess[i - 1];
            
            // Mark this item as taken in the original selection vector
            selectionVector[takenItem.originalIndex] = 1;

            // Reduce our remaining capacity
            c -= takenItem.weight;

            std::cout << "  - Item " << takenItem.originalIndex + 1
                << " (v=" << takenItem.value << ", w=" << takenItem.weight
                << ") was TAKEN." << std::endl;
        }
    }

    // Final total value is the value from the DP table plus any value we got from 0-weight items.
    long long finalTotalValue = dpMaxValue + preAdjustedValue;

    // --- Write the final solution to output.txt ---
    std::cout << colors::GREEN << "Writing final solution to output.txt..." << colors::RESET << std::endl;

    outputFile << "MaxValue: " << finalTotalValue << "\n";
    outputFile << "Selection: ";
    for (int i = 0; i < selectionVector.size(); ++i) {
        outputFile << selectionVector[i] << " ";
    }
    outputFile << "\n";
}



int main() {
    std::cout << colors::CYAN << "--- 0/1 Knapsack Solver (Dynamic Programming) ---" << colors::RESET << std::endl;

    std::ifstream inputFile("input.txt");
    if (!inputFile.is_open()) {
        std::cerr << colors::RED << "Fatal Error: Could not open input.txt." << colors::RESET << std::endl;
        return 1;
    }

    std::ofstream outputFile("output.txt");
    if (!outputFile.is_open()) {
        std::cerr << colors::RED << "Fatal Error: Could not open output.txt." << colors::RESET << std::endl;
        inputFile.close();
        return 1;
    }

    try {
        int itemCount;
        int capacity;
        inputFile >> itemCount >> capacity;

        if (inputFile.fail() || itemCount < 0 || capacity < 0) {
            throw std::runtime_error("Invalid or non-numeric item count or capacity.");
        }

        std::cout << "  - " << colors::CYAN << "Items: " << itemCount << colors::RESET << std::endl;
        std::cout << "  - " << colors::CYAN << "Capacity: " << capacity << colors::RESET << std::endl;

        
        //    Handle the base cases (C=0 or N=0) as per requirements.
        
        if (itemCount == 0 || capacity == 0) {
            std::cout << colors::YELLOW << "Base case (N=0 or C=0) detected. Result is 0." << colors::RESET << std::endl;
            outputFile << "MaxValue: 0\n";
            outputFile << "Selection: ";
            for (int i = 0; i < itemCount; ++i) {
                outputFile << "0";
            }
            outputFile << "\n";
            inputFile.close();
            outputFile.close();
            std::cout << colors::GREEN << "Solution complete." << colors::RESET << std::endl;
            return 0;
        }

        std::vector<Item> itemsToProcess;
        std::vector<int> selectionVector(itemCount, 0);
        long long preAdjustedValue = 0;

        std::cout << colors::YELLOW << "Reading and pre-processing items..." << colors::RESET << std::endl;

        for (int i = 0; i < itemCount; ++i) {
            long long v;
            int w;
            inputFile >> v >> w;

            if (inputFile.fail() || v < 0 || w < 0) {
                throw std::runtime_error("Invalid item data found in file.");
            }

            std::cout << "  - " << colors::CYAN << "Read Item " << (i + 1)
                << ": (v=" << v << ", w=" << w << ")" << colors::RESET << std::endl;

            /*
                Edge case : Items with 0 weight and positive value are "free" and should always be taken. Take them now and remove them from the list to be processed by the DP.
            */
            if (w == 0 && v > 0) {
                preAdjustedValue += v;
                selectionVector[i] = 1;
                std::cout << "    " << colors::MAGENTA
                    << "-> Taken (0-weight item)." << colors::RESET << std::endl;
            }
            /*
                We only add items to the DP solver if they have both positive value and positive weight. Items with 0 value or 0 weight (and 0 value) be ignored.
            */
            else if (w > 0 && v > 0) {
                itemsToProcess.push_back({v, w, i});
            }
        }

        // Pass the filtered items to the DP solver
        solveKnapsack(
            itemsToProcess,
            capacity,
            selectionVector,
            preAdjustedValue,
            outputFile
        );

    }
    catch (const std::exception& e) {
        std::cerr << colors::RED << "An error occurred: " << e.what() << colors::RESET << std::endl;
        outputFile << "Error: " << e.what() << "\n";
    }

    inputFile.close();
    outputFile.close();
    std::cout << colors::GREEN << "--- Solver Finished ---" << colors::RESET << std::endl;

    return 0;
}
