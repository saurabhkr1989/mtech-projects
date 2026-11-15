#pragma once   // include guard

#include <cstdint>   // for uint8_t, uint32_t

// This struct basically holds the internal 16 words of ChaCha (each 32-bit).
// I’m calling them 'quads' just to stick with the assignment naming.
struct ChaCha_Internal_Matrix {
    uint32_t internal_cipher_quads[16];
};

// --- Function declarations ---
// Everything here is just defined in chacha_crypt.cpp later on.

// Task 1: initialize state from the 64-byte master key.
// The constant words are XORed with first 16 bytes of the key,
// rest of the bytes go to key, counter, and nonce positions.
void init_chacha_state_matrix(
    ChaCha_Internal_Matrix& state_matrix,
    const uint8_t master_key_material[64]
);

// Task 2: Run full 20 rounds (10 column + 10 diagonal) and produce 64-byte output.
// Output goes to 'output_stream_block'.
void chacha_permute_and_output(
    ChaCha_Internal_Matrix& state_matrix,
    uint8_t output_stream_block[64]
);

// Helper: increment counter (the standard ChaCha style ++).
void advance_progression_index(ChaCha_Internal_Matrix& state_matrix);