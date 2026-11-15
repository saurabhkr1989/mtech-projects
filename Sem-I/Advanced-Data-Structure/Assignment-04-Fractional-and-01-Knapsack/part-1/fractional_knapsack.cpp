/*
JCP7181 - Assignment 4, Part 1: Fractional Knapsack

Solves the fractional knapsack problem using a greedy algorithm. The core logic is to sort items by their value-per-weight (density) and pick the most valuable items first until the capacity is full.

This includes a manual implementation of Merge Sort.

Input:  Reads N (item count) and C (capacity) from input.txt, followed by N lines of item (value weight).
Output: Writes the max value and the fraction of each item taken to output.txt, in the original input order.
*/

#include <iostream>  
#include <fstream>   
#include <vector>    // To hold our list of items
#include <algorithm> 
#include <iomanip>   // For formatting our output (setprecision, fixed)
#include <limits>    // Used for numeric limits
#include <string>    // Used for our color strings

namespace colors {
    const char* const RESET = "\033[0m";
    const char* const RED = "\033[31m";
    const char* const GREEN = "\033[32m";
    const char* const YELLOW = "\033[33m";
    const char* const CYAN = "\033[36m";
    const char* const MAGENTA = "\033[35m";
    const char* const GREY = "\033[90m"; 
} 


/*
Represents a single item for the knapsack. Store its value, weight, and calculated density (valuePerWeight).
The inputOrderIndex is critical for final output which must be in the same order as the items were read from the input file.
*/
struct Item {
    double value;           
    double weight;          
    double valuePerWeight;  
    int inputOrderIndex;    
};

/*
Comparison function for sorting. Implements greedy strategy: To sort items in descending order of their valuePerWeight (density).
Returns true if 'a' is "better" than 'b'.

Tie-breaking: If densities are equal, prefer the item with the higher value making the sort deterministic.
*/
bool isItemBetter(const Item& a, const Item& b) {
    if (a.valuePerWeight > b.valuePerWeight) {
        return true;
    }
    if (a.valuePerWeight < b.valuePerWeight) {
        return false;
    }
    
    // Densities are equal, apply tie-breaker.
    // Prefer the item with the higher absolute value.
    return a.value > b.value;
}

// Merge Sort Implementation  
void merge(std::vector<Item>& items, int left, int middle, int right) {
    int n1 = middle - left + 1; 
    int n2 = right - middle;    

    // Temporary vectors to hold the data
    std::vector<Item> leftHalf(n1);
    std::vector<Item> rightHalf(n2);

    // Copy data from the main vector to our temp vectors
    for (int i = 0; i < n1; ++i) {
        leftHalf[i] = items[left + i];
    }
    for (int j = 0; j < n2; ++j) {
        rightHalf[j] = items[middle + 1 + j];
    }

    // Pointers for merging
    int i = 0; // Initial index of leftHalf
    int j = 0; // Initial index of rightHalf
    int k = left; // Initial index of the merged subarray (in 'items' vector)

    // Merge the temp vectors back into items[left...right]
    while (i < n1 && j < n2) {
        if (isItemBetter(leftHalf[i], rightHalf[j])) {
            items[k] = leftHalf[i];
            i++;
        } else {
            items[k] = rightHalf[j];
            j++;
        }
        k++;
    }

    // Copy any remaining elements from leftHalf
    while (i < n1) {
        items[k] = leftHalf[i];
        i++;
        k++;
    }

    // Copy any remaining elements from rightHalf
    while (j < n2) {
        items[k] = rightHalf[j];
        j++;
        k++;
    }
}

void mergeSort(std::vector<Item>& items, int left, int right) {
    // Base case: if the subarray has 0 or 1 elements.
    if (left >= right) {
        return;
    }

    // Middle point to divide the array
    int middle = left + (right - left) / 2;

    // Recursively sort the first and second halves
    mergeSort(items, left, middle);
    mergeSort(items, middle + 1, right);

    // Merge the two sorted halves
    merge(items, left, middle, right);
}



//Function for the fractional knapsack problem. It implements the greedy algorithm, sorts the items, fills the knapsack and writes the final results to the output file stream.
void solveFractionalKnapsack(int itemCount, double truckCapacity, std::vector<Item>& allItems, std::ofstream& outputFile) {

    /* Edge cases: no items or no capacity. */
    if (itemCount <= 0 || truckCapacity <= 0.0) {
        std::cout << colors::YELLOW << "Edge case: No items or no capacity. Setting value to 0." << colors::RESET << std::endl;
        outputFile << "MaxValue: 0.00" << std::endl;
        outputFile << "Fractions: ";
        for (int i = 0; i < itemCount; ++i) {
            outputFile << "0.0" << (i == itemCount - 1 ? "" : " ");
        }
        outputFile << std::endl;
        return; 
    }

    std::cout << colors::MAGENTA << "Sorting items by value-per-weight (using Merge Sort)..." << colors::RESET << std::endl;
    mergeSort(allItems, 0, itemCount - 1);
    std::vector<double> fractionOfEachItem(itemCount, 0.0);

    double maxTotalValue = 0.0;
    double currentRemainingCapacity = truckCapacity;

    std::cout << colors::MAGENTA << "Filling the knapsack..." << colors::RESET << std::endl;
    /* Loop through the sorted items (best to worst) and fill the knapsack. */
    for (const auto& item : allItems) {
        
        if (currentRemainingCapacity == 0.0) {
            std::cout << colors::GREY << "  Knapsack is full. Stopping." << colors::RESET << std::endl;
            break;
        }

        int itemLabel = item.inputOrderIndex + 1;

        if (item.weight <= currentRemainingCapacity) {
            std::cout << colors::GREEN << "  Taking 100% of Item " << itemLabel
                      << " (Weight: " << item.weight << ")" << colors::RESET << std::endl;
            currentRemainingCapacity -= item.weight;
            maxTotalValue += item.value;
            
            fractionOfEachItem[item.inputOrderIndex] = 1.0;
        } else {
            double fractionToTake = currentRemainingCapacity / item.weight;
            
            std::cout << colors::YELLOW << "  Taking " << (fractionToTake * 100.0) << "% of Item " << itemLabel
                      << " (Weight: " << currentRemainingCapacity << ")" << colors::RESET << std::endl;

            maxTotalValue += item.value * fractionToTake;
            fractionOfEachItem[item.inputOrderIndex] = fractionToTake;

            currentRemainingCapacity = 0.0;
        }
    }

    std::cout << colors::MAGENTA << "Final calculated value: " << maxTotalValue << colors::RESET << std::endl;

    outputFile << std::fixed << std::setprecision(2);
    outputFile << "MaxValue: " << maxTotalValue << std::endl;

    outputFile << std::fixed << std::setprecision(8);
    outputFile << "Fractions: ";
    for (int i = 0; i < itemCount; ++i) {
        outputFile << fractionOfEachItem[i] << (i == itemCount - 1 ? "" : " ");
    }
    outputFile << std::endl;
}

int main() {
    std::cout << colors::CYAN << "--- Fractional Knapsack Solver (with Logging) ---" << colors::RESET << std::endl;
    
    /* Attempt to open the input file. */
    std::ifstream inputFile("input.txt");
    if (!inputFile.is_open()) {
        std::cerr << colors::RED << "Error: Could not open input.txt" << colors::RESET << std::endl;
        return 1; 
    }
    std::cout << colors::GREEN << "Successfully opened " << colors::YELLOW << "input.txt" << colors::RESET << std::endl;

    /* Attempt to open the output file. */
    std::ofstream outputFile("output.txt");
    if (!outputFile.is_open()) {
        std::cerr << colors::RED << "Error: Could not open output.txt" << colors::RESET << std::endl;
        inputFile.close();
        return 1;
    }
    std::cout << colors::GREEN << "Successfully opened " << colors::YELLOW << "output.txt" << colors::RESET << std::endl;


    int itemCount;
    double truckCapacity;

    /* Read item count (N) and truck capacity (C). */
    if (!(inputFile >> itemCount >> truckCapacity)) {
        std::cerr << colors::RED << "Error: Failed to read item count and capacity from input.txt." << colors::RESET << std::endl;
        inputFile.close();
        outputFile.close();
        return 1;
    }

    // Log the parameters just read.
    std::cout << colors::MAGENTA << "Reading problem parameters..." << colors::RESET << std::endl;
    std::cout << "  - Number of items (N): " << colors::CYAN << itemCount << colors::RESET << std::endl;
    std::cout << "  - Truck Capacity (C):  " << colors::CYAN << truckCapacity << colors::RESET << std::endl;

    /* Validate the parameters. */
    if (itemCount < 0) {
        std::cerr << colors::RED << "Error: Number of items cannot be negative." << colors::RESET << std::endl;
        inputFile.close();
        outputFile.close();
        return 1;
    }
    if (truckCapacity < 0.0) {
        std::cerr << colors::RED << "Error: Truck capacity cannot be negative." << colors::RESET << std::endl;
        inputFile.close();
        outputFile.close();
        return 1;
    }

    std::vector<Item> allItems;
    
    std::cout << colors::MAGENTA << "Reading items..." << colors::RESET << std::endl;
    for (int i = 0; i < itemCount; ++i) {
        double v, w;
        
        if (!(inputFile >> v >> w)) {
            std::cerr << colors::RED << "Error: Failed to read data for item " << (i + 1) << " from input.txt." << colors::RESET << std::endl;
            inputFile.close();
            outputFile.close();
            return 1;
        }

        /* Validate the item's value and weight. */
        if (v < 0.0) {
            std::cerr << colors::RED << "Error: Item " << (i + 1) << " has a negative value." << colors::RESET << std::endl;
            inputFile.close();
            outputFile.close();
            return 1;
        } else if (w <= 0.0) {
            /* Weight must be > 0 to avoid division by zero. */
            std::cerr << colors::RED << "Error: Item " << (i + 1) << " has a non-positive weight." << colors::RESET << std::endl;
            inputFile.close();
            outputFile.close();
            return 1;
        } else {
            // valid data.
            Item newItem;
            newItem.value = v;
            newItem.weight = w;
            newItem.valuePerWeight = v / w; 
            newItem.inputOrderIndex = i;   
            
            
            std::cout << "  - " << colors::CYAN << "Read Item " << (i + 1)
                      << ": Value=" << newItem.value 
                      << ", Weight=" << newItem.weight
                      << colors::GREY << " (v/w: " << newItem.valuePerWeight << ")"
                      << colors::RESET << std::endl;

            allItems.push_back(newItem); 
        }
    }

    
    solveFractionalKnapsack(itemCount, truckCapacity, allItems, outputFile);

    
    inputFile.close();
    outputFile.close();

    std::cout << colors::GREEN << "Calculation complete. Result written to output.txt" << colors::RESET << std::endl;

    return 0; 
}

