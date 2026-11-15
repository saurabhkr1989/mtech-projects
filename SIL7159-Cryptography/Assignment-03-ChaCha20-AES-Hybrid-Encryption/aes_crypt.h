#pragma once   // include guard
#include <cstdint>
#include <vector>   // vector of round-key pointers


// This is only the declaration — implementation lives in aes_crypt.cpp.

// Our AES encryptor that uses 14 dynamic round keys (128-bit each).
// Input: one 16B block in 'current_data_block' (modified in-place).
// Keys: cyclical_key_schedule holds 14 pointers, each -> 16 bytes.
void AES_dynamic_key_encryption(
    uint8_t current_data_block[16],
    const std::vector<uint8_t*>& cyclical_key_schedule
);