// ChaCha20–AES Hybrid Encryption (Assignment 3)

#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <cstdint>
#include <cmath>
#include <map>
#include <iomanip>
#include <sstream>
#include <cstdlib> // For exit()
#include <algorithm> // For std::min and std::fill

using namespace std;

#include "chacha_crypt.h"
#include "aes_crypt.h"

// console colors 
#define BOLD_YELLOW "\033[1;33m"
#define BOLD_GREEN  "\033[1;32m"
#define RESET_COLOR "\033[0m"

// =============
// Helpers
// =====================

// convert a single hex char to integer value
int hex_char_to_int(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;  // if something goes wrong
}

// convert byte vector into hex string (for printing)
string bytes_to_hex_string(const vector<uint8_t>& bytes_vec) {
    stringstream hex_stream;
    hex_stream << hex << setfill('0');
    for (auto b : bytes_vec)
        hex_stream << setw(2) << (int)b;
    return hex_stream.str();
}

// Reads the input file, validates it, and loads the key and plaintext.
// Returns true on success, false on any validation error.
bool read_input_file(string filename,
                     uint8_t origin_key_material[64],
                     vector<uint8_t>& original_message_data) {

    ifstream file_handle(filename);
    string file_line;
    if (!file_handle.is_open()) {
        cerr << BOLD_YELLOW << "Error: " << RESET_COLOR << "Could not open file " << filename << "\n";
        return false;
    }

    // first line = key
    if (!getline(file_handle, file_line)) {
        cerr << BOLD_YELLOW << "Error: " << RESET_COLOR << "Input file is empty.\n";
        file_handle.close();
        return false;
    }

    // Trim trailing whitespace (like \r from Windows files)
    while (!file_line.empty() && (file_line.back() == '\r' || file_line.back() == '\n' || file_line.back() == ' ')) {
        file_line.pop_back();
    }
    
    // Hard fail if the key is empty
    if (file_line.empty()) {
        cerr << BOLD_YELLOW << "Error: " << RESET_COLOR << "Master key on line 1 is empty.\n";
        file_handle.close();
        return false;
    }

    // Hard fail if any character is not a valid hex digit
    for (char c : file_line) {
        if (hex_char_to_int(c) == -1) {
            cerr << BOLD_YELLOW << "Error: " << RESET_COLOR << "Invalid hex character '" << c << "' in master key.\n";
            file_handle.close();
            return false;
        }
    }

    // Hard fail if the key has an odd number of characters
    if (file_line.length() % 2 != 0) {
        cerr << BOLD_YELLOW << "Error: " << RESET_COLOR << "Master key has an odd number of hex characters (" 
             << file_line.length() << "). Cannot parse into bytes.\n";
        file_handle.close();
        return false;
    }
    
    // --- Handle Key Length (Warn, but do not fail) ---
    size_t original_len = file_line.length();
    
    if (original_len > 128) {
        cout << BOLD_YELLOW << "Warning: " << RESET_COLOR << "Master key is " << original_len 
             << " chars. Truncating to first 128 chars (64 bytes).\n";
    }
    if (original_len < 128) {
         cout << BOLD_YELLOW << "Warning: " << RESET_COLOR << "Master key is " << original_len 
             << " chars. Padding with 0s to 64 bytes.\n";
    }

    // Initialize the key material to all zeros
    std::fill(origin_key_material, origin_key_material + 64, (uint8_t)0);

    // Parse the key, up to a maximum of 128 characters (64 bytes)
    size_t chars_to_parse = std::min((size_t)128, original_len);
    for (size_t i = 0; i < chars_to_parse; i += 2) {
        int high = hex_char_to_int(file_line[i]);
        int low = hex_char_to_int(file_line[i + 1]);
        origin_key_material[i / 2] = (high << 4) | low;
    }

    // rest = plaintext lines (each char → byte)
    while (getline(file_handle, file_line)) {
        for (char c : file_line)
            original_message_data.push_back((uint8_t)c);
    }
    file_handle.close();
    return true; // Success
}

// convert array of bytes into a hex string
string bytes_to_hex_string_arr(const uint8_t* arr, int len) {
    stringstream s;
    s << hex << setfill('0');
    for (int i = 0; i < len; ++i)
        s << setw(2) << (int)arr[i];
    return s.str();
}

// print a ChaCha state matrix neatly
void print_chacha_state(const ChaCha_Internal_Matrix& s, string title) {
    cout << BOLD_GREEN << title << RESET_COLOR << endl;
    for (int i = 0; i < 4; ++i) {
        cout << "  ";
        for (int j = 0; j < 4; ++j)
            cout << hex << setw(8) << setfill('0')
                 << s.internal_cipher_quads[i * 4 + j] << " ";
        cout << dec << "\n";
    }
}

// quick helper (used twice)
static void word_to_bytes_local(uint32_t word, uint8_t* out) {
    out[0] = (word >> 0) & 0xFF;
    out[1] = (word >> 8) & 0xFF;
    out[2] = (word >> 16) & 0xFF;
    out[3] = (word >> 24) & 0xFF;
}

// =====================================
// Entropy and Avalanche Analysis
// ================================

// Entropy in bits/byte
double H(const vector<uint8_t>& data_stream) {
    // Prevent division by zero if the data stream is empty
    if (data_stream.empty()) {
        cout << "Warning: Entropy calculation on empty data stream.\n";
        return 0.0;
    }
    map<uint8_t, long long> freq;
    for (auto byte : data_stream) freq[byte]++;

    double total_entropy = 0.0;
    double N = (double)data_stream.size();

    for (auto [val, count] : freq) {
        if (count > 0) {
            double p = (double)count / N;
            total_entropy -= p * log2(p);
        }
    }
    return total_entropy;
}

// Avalanche = % of changed bits between two ciphertexts
double A(const vector<uint8_t>& c1, const vector<uint8_t>& c2) {
    // Sanity check for avalanche calculation
    if (c1.size() != c2.size()) {
        cerr << "Avalanche Error: Ciphertext sizes do not match.\n";
        return 0.0;
    }
    if (c1.empty()) {
        cout << "Warning: Avalanche calculation on empty data streams.\n";
        return 0.0;
    }

    long long diff_bits = 0;
    long long total_bits = (long long)c1.size() * 8; // Cast to long long

    for (size_t i = 0; i < c1.size(); ++i) {
        uint8_t delta = c1[i] ^ c2[i];
        for (int b = 0; b < 8; ++b)
            if ((delta >> b) & 1)
                diff_bits++;
    }
    return ((double)diff_bits / (double)total_bits) * 100.0;
}

// =====================
// MAIN
// ==========================

int main(int argc, char* argv[]) {

    cout << BOLD_YELLOW
         << "====== ChaCha20–AES Hybrid Encryptor ======"
         << RESET_COLOR << "\n";

    // -------------------------------------------------
    // Step 1. Load input
    // -------------------------------------------------
    uint8_t origin_key_material[64];
    uint8_t S0_bytes[64];
    uint8_t iv[16];

    vector<uint8_t> original_message_data;
    vector<uint8_t*> cyclical_key_schedule;

    // Allow using a filename from the command line, e.g., ./hybrid_encrypt my_file.txt
    string input_filename = "input.txt";   // default input
    if (argc > 1) {
        input_filename = argv[1];
    }
    cout << "Attempting to read from: " << input_filename << "\n";
    
    // Stop if the file read or validation failed.
    if (!read_input_file(input_filename, origin_key_material, original_message_data)) {
        cerr << BOLD_YELLOW << "Aborting due to input file error." << RESET_COLOR << "\n";
        return 1; // Exit with error
    }

    cout << BOLD_GREEN << "1. Input File Read: " << RESET_COLOR
         << "Success from " << input_filename << "\n";


    // -------------------------------------------------
    // Step 2. Initialize ChaCha state (Task 1)
    // -------------------------------------------------
    ChaCha_Internal_Matrix S_0, key_gen_matrix;
    init_chacha_state_matrix(S_0, origin_key_material);

    print_chacha_state(S_0, "2. Initial S0 State Matrix (Task 1)");

    for (int i = 0; i < 16; ++i)
        word_to_bytes_local(S_0.internal_cipher_quads[i], &S0_bytes[i * 4]);

    // -------------------------------------------------
    // Step 3. Generate AES round keys (Task 2)
    // -------------------------------------------------
    cout << BOLD_GREEN << "3. AES Key Generation (Task 2)"
         << RESET_COLOR << endl;

    key_gen_matrix = S_0;  // start from same base
    while (cyclical_key_schedule.size() < 14) {
        uint8_t round_out[64];
        chacha_permute_and_output(key_gen_matrix, round_out);

        for (int i = 0; i < 4 && cyclical_key_schedule.size() < 14; ++i) {
            uint8_t* K_i = new uint8_t[16];
            for (int j = 0; j < 16; ++j)
                K_i[j] = round_out[i * 16 + j];
            cyclical_key_schedule.push_back(K_i);

            // show first two keys (debug / assignment req)
            if (cyclical_key_schedule.size() == 1)
                cout << "  K1: " << bytes_to_hex_string_arr(K_i, 16) << "\n";
            if (cyclical_key_schedule.size() == 2)
                cout << "  K2: " << bytes_to_hex_string_arr(K_i, 16) << "\n";
        }
        advance_progression_index(key_gen_matrix);
    }
    cout << "  ... total " << cyclical_key_schedule.size()
         << " AES round keys generated.\n";

    // -------------------------------------------------
    // Step 4. Encrypt (Task 3)
    // -------------------------------------------------
    cout << BOLD_GREEN << "4. Encryption Process (Task 3)"
         << RESET_COLOR << endl;

    size_t original_pt_size = original_message_data.size();
    size_t padded_size = original_pt_size;

    // Pad the plaintext to be a multiple of 64 bytes (the pre-whitening block size).
    // This also handles the case if the file was empty (key-only).
    if (padded_size % 64 != 0 || padded_size == 0) {
        if (padded_size == 0) {
            padded_size = 64; // Handle empty plaintext
        } else {
            padded_size = (original_pt_size / 64 + 1) * 64; // Find next multiple of 64
        }
        
        cout << BOLD_YELLOW << "Info: " << RESET_COLOR << "Padding plaintext from "
             << original_pt_size << " bytes to " << padded_size << " bytes.\n";

        while (original_message_data.size() < padded_size)
            original_message_data.push_back(0x00);
    }


    for (int i = 0; i < 16; ++i)
        iv[i] = S0_bytes[48 + i];  // IV = last 16 bytes of S0

    cout << "  Using CBC Mode. IV: "
         << bytes_to_hex_string_arr(iv, 16) << "\n";

    vector<uint8_t> final_secured_output;
    uint8_t chain[16];
    for (int i = 0; i < 16; ++i) chain[i] = iv[i];

    // CBC encryption (process 64B blocks)
    for (size_t i = 0; i < original_message_data.size(); i += 64) {
        uint8_t P_prime[64];
        // This is the pre-whitening step from the assignment
        for (int j = 0; j < 64; ++j)
            P_prime[j] = original_message_data[i + j] ^ S0_bytes[j];

        if (i == 0) {
            cout << "  Plaintext (first 64B): "
                 << bytes_to_hex_string_arr(&original_message_data[i], 64) << "\n";
            cout << "  P' (first 64B): "
                 << bytes_to_hex_string_arr(P_prime, 64) << "\n";
        }

        // Process the 64B block in four 16B segments
        for (int seg = 0; seg < 4; ++seg) {
            uint8_t block[16];
            for (int k = 0; k < 16; ++k) block[k] = P_prime[seg * 16 + k];

            // CBC XOR step
            for (int k = 0; k < 16; ++k)
                block[k] ^= chain[k];

            // Encrypt with our dynamic keys
            AES_dynamic_key_encryption(block, cyclical_key_schedule);

            // update chaining variable
            for (int k = 0; k < 16; ++k)
                chain[k] = block[k];

            // collect ciphertext bytes
            for (int k = 0; k < 16; ++k)
                final_secured_output.push_back(block[k]);
        }

        if (i == 0)
            cout << "  Ciphertext (first 64B): "
                 << bytes_to_hex_string_arr(&final_secured_output[0], 64)
                 << "\n";
    }

    cout << "\n" << BOLD_GREEN << "5. Encryption Complete."
         << RESET_COLOR << "\n";
    cout << "Final Ciphertext (Hex): "
         << bytes_to_hex_string(final_secured_output) << "\n";

    // -------------------------------------------------
    // Step 5. Analysis (Task 4)
    // -------------------------------------------------
    cout << BOLD_YELLOW << "\n====== Analysis (Task 4) ======"
         << RESET_COLOR << endl;

    cout << BOLD_GREEN << "Entropy H(X): " << RESET_COLOR
         << H(final_secured_output) << " bits/byte\n";

    // avalanche check
    vector<uint8_t> flipped = original_message_data;
    
    // Can't run avalanche test on an empty message, so check first.
    if (!flipped.empty() && flipped.size() == original_message_data.size()) // Check size just in case
        flipped[0] ^= 0x01;  // flip first bit
    else
        cout << BOLD_YELLOW << "Warning: " << RESET_COLOR << "Skipping avalanche test, no plaintext to flip.\n";


    vector<uint8_t> second_cipher;
    uint8_t chain2[16];
    for (int i = 0; i < 16; ++i) chain2[i] = iv[i]; // re-initialize chain

    for (size_t i = 0; i < flipped.size(); i += 64) {
        uint8_t Pp2[64];
        for (int j = 0; j < 64; ++j)
            Pp2[j] = flipped[i + j] ^ S0_bytes[j];

        for (int seg = 0; seg < 4; ++seg) {
            uint8_t block[16];
            for (int k = 0; k < 16; ++k)
                block[k] = Pp2[seg * 16 + k];

            // CBC XOR
            for (int k = 0; k < 16; ++k)
                block[k] ^= chain2[k];

            AES_dynamic_key_encryption(block, cyclical_key_schedule);

            // update chain
            for (int k = 0; k < 16; ++k)
                chain2[k] = block[k];

            for (int k = 0; k < 16; ++k)
                second_cipher.push_back(block[k]);
        }
    }

    double avalanche_val = A(final_secured_output, second_cipher);
    cout << BOLD_GREEN << "Avalanche Effect A: " << RESET_COLOR
         << avalanche_val << " %\n";

    // cleanup
    for (auto ptr : cyclical_key_schedule)
        delete[] ptr;

    cout << BOLD_YELLOW
         << "\n====== Run Complete ======"
         << RESET_COLOR << endl;

    return 0;
}