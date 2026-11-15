#ifndef UTILS_H
#define UTILS_H

#include <iostream>
#include <string>

// ANSI Color Codes for attractive UI
const std::string C_RESET = "\033[0m";
const std::string C_BOLD = "\033[1m";
const std::string C_YELLOW = "\033[33m";
const std::string C_BLUE = "\033[34m";
const std::string C_CYAN = "\033[36m";
const std::string C_GREEN = "\033[32m";
const std::string C_RED = "\033[31m";


// Function to print styled headers
void print_header(const std::string& text);

// Function to print styled steps
void print_step(const std::string& text);

// Function to print key-value pairs
void print_info(const std::string& key, const std::string& value);


#endif // UTILS_H
