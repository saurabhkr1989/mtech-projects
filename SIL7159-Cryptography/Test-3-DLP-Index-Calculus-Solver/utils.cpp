#include "utils.h"
#include <iostream>

// Function to print styled headers
void print_header(const std::string& text) {
    std::cout << "\n" << C_BOLD << C_YELLOW << "===== " << text << " =====" << C_RESET << std::endl;
}

// Function to print styled steps
void print_step(const std::string& text) {
    std::cout << "\n" << C_BOLD << C_BLUE << "--- " << text << " ---" << C_RESET << std::endl;
}

// Function to print key-value pairs
void print_info(const std::string& key, const std::string& value) {
    std::cout << "  " << C_CYAN << key << ": " << C_RESET << value << std::endl;
}

