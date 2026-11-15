#include "chacha_crypt.h"
#include <string.h>   // for memcpy
#include <iostream>   // left for debugging if needed

// --- helper: bytes <-> word conversions ---

// combine 4 bytes (little endian) → one 32-bit word
static uint32_t bytes_to_word_local(const uint8_t* input_bytes) {
    return  (uint32_t)input_bytes[0]
          | ((uint32_t)input_bytes[1] << 8)
          | ((uint32_t)input_bytes[2] << 16)
          | ((uint32_t)input_bytes[3] << 24);
}

// split one 32-bit word into 4 bytes (also little endian)
static void word_to_bytes_local(uint32_t single_word, uint8_t* output_bytes) {
    output_bytes[0] = (single_word >> 0)  & 0xFF;
    output_bytes[1] = (single_word >> 8)  & 0xFF;
    output_bytes[2] = (single_word >> 16) & 0xFF;
    output_bytes[3] = (single_word >> 24) & 0xFF;
}

// simple rotate-left for 32-bit
static uint32_t bitwise_rotation_left(uint32_t rotation_value, int num_bits) {
    return (rotation_value << num_bits) | (rotation_value >> (32 - num_bits));
}

// --- core ChaCha round logic ---
// from the original paper by Bernstein (SASC 2008)
// modifies values directly (passed by reference)
static void chacha_quarter_round(uint32_t& a_val, uint32_t& b_val,
                                 uint32_t& c_val, uint32_t& d_val) {
    a_val += b_val; d_val ^= a_val; d_val = bitwise_rotation_left(d_val, 16);
    c_val += d_val; b_val ^= c_val; b_val = bitwise_rotation_left(b_val, 12);
    a_val += b_val; d_val ^= a_val; d_val = bitwise_rotation_left(d_val, 8);
    c_val += d_val; b_val ^= c_val; b_val = bitwise_rotation_left(b_val, 7);
}

// ---------------------------------------------------------------------
// Task 1: initialize the ChaCha state (from the 64-byte master key)
// ---------------------------------------------------------------------
void init_chacha_state_matrix(ChaCha_Internal_Matrix& state_matrix,
                              const uint8_t master_key_material[64]) {
    // constant words ("expand 32-byte k")
    const uint32_t chacha_constants[4] = {
        0x61707865, 0x3320646e, 0x79622d32, 0x6b206574
    };

    // mix constants with first 16 bytes of the key (makes the state unique)
    for (int i = 0; i < 4; ++i) {
        state_matrix.internal_cipher_quads[i] =
            chacha_constants[i] ^ bytes_to_word_local(&master_key_material[i * 4]);
    }

    // next 32 bytes → actual key words (8 of them)
    for (int i = 0; i < 8; ++i) {
        state_matrix.internal_cipher_quads[4 + i] =
            bytes_to_word_local(&master_key_material[16 + i * 4]);
    }

    // counter field (8 bytes → 2 words)
    state_matrix.internal_cipher_quads[12] = bytes_to_word_local(&master_key_material[48]);
    state_matrix.internal_cipher_quads[13] = bytes_to_word_local(&master_key_material[52]);

    // nonce field (last 8 bytes → 2 words)
    state_matrix.internal_cipher_quads[14] = bytes_to_word_local(&master_key_material[56]);
    state_matrix.internal_cipher_quads[15] = bytes_to_word_local(&master_key_material[60]);

    // // uncomment to see state setup during debugging
    // for (int i = 0; i < 16; ++i)
    //     std::cout << "init_state[" << i << "] = "
    //               << std::hex << state_matrix.internal_cipher_quads[i] << "\n";
}

// ---------------------------------------------------------------------
// Task 2: Run full 20-round permutation and output 64-byte keystream
// ---------------------------------------------------------------------
void chacha_permute_and_output(ChaCha_Internal_Matrix& state_matrix,
                               uint8_t output_stream_block[64]) {
    // make a working copy of the current state (so original stays intact)
    ChaCha_Internal_Matrix working_matrix;
    memcpy(working_matrix.internal_cipher_quads, state_matrix.internal_cipher_quads, 64);

    uint32_t* q = working_matrix.internal_cipher_quads;  // shorthand

    // do 20 rounds (10 pairs of column+diagonal)
    for (int i = 0; i < 10; ++i) {
        // column rounds
        chacha_quarter_round(q[0], q[4], q[8],  q[12]);
        chacha_quarter_round(q[1], q[5], q[9],  q[13]);
        chacha_quarter_round(q[2], q[6], q[10], q[14]);
        chacha_quarter_round(q[3], q[7], q[11], q[15]);

        // diagonal rounds
        chacha_quarter_round(q[0], q[5], q[10], q[15]);
        chacha_quarter_round(q[1], q[6], q[11], q[12]);
        chacha_quarter_round(q[2], q[7], q[8],  q[13]);
        chacha_quarter_round(q[3], q[4], q[9],  q[14]);
    }

    // // debugging note: this print helps confirm 20-round mix
    // std::cout << "After rounds: " << std::hex << q[0] << " " << q[1] << std::dec << "\n";

    // add original state (feed-forward step)
    for (int i = 0; i < 16; ++i) {
        q[i] += state_matrix.internal_cipher_quads[i];
    }

    // convert back to bytes (little endian)
    for (int i = 0; i < 16; ++i) {
        word_to_bytes_local(q[i], &output_stream_block[i * 4]);
    }

    // // sample output
    // std::cout << "ChaCha block first bytes: "
    //           << std::hex << (int)output_stream_block[0] << " "
    //           << (int)output_stream_block[1] << "\n";
}

// ---------------------------------------------------------------------
// simple helper: increment the counter (handle overflow to next word)
// ---------------------------------------------------------------------
void advance_progression_index(ChaCha_Internal_Matrix& state_matrix) {
    state_matrix.internal_cipher_quads[12]++;  // lower counter
    if (state_matrix.internal_cipher_quads[12] == 0) {
        state_matrix.internal_cipher_quads[13]++;  // carry overflow
    }
}