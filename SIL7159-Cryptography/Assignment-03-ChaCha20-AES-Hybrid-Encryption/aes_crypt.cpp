#include "aes_crypt.h"
#include <iostream>   

// --- S-Box table ---
// Standard AES S-box (no experiments here).
// Ref: NIST FIPS-197 5.1.1
static const uint8_t s_box_lookup[256] = {
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0x54,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
};

// --- AES round helpers ---

// Substitute each byte via S-box
static void substitute_bytes_lookup(uint8_t state_grid[4][4]) {
    for (int r = 0; r < 4; ++r) {
        for (int c = 0; c < 4; ++c) {
            state_grid[r][c] = s_box_lookup[state_grid[r][c]];
        }
    }
    // // DEBUG peek:
    // std::cout << "[sub] state(0,0)=" << std::hex << (int)state_grid[0][0] << std::dec << "\n";
}

// ShiftRows (row i shifts left by i)
static void shift_rows_transform(uint8_t state_grid[4][4]) {
    // Row 0 unchanged
    // Row 1: shift by 1
    uint8_t t = state_grid[1][0];
    state_grid[1][0] = state_grid[1][1];
    state_grid[1][1] = state_grid[1][2];
    state_grid[1][2] = state_grid[1][3];
    state_grid[1][3] = t;

    // Row 2: shift by 2 (swap pairs)
    t = state_grid[2][0]; state_grid[2][0] = state_grid[2][2]; state_grid[2][2] = t;
    t = state_grid[2][1]; state_grid[2][1] = state_grid[2][3]; state_grid[2][3] = t;

    // Row 3: shift by 3 (i.e., right by 1)
    t = state_grid[3][3];
    state_grid[3][3] = state_grid[3][2];
    state_grid[3][2] = state_grid[3][1];
    state_grid[3][1] = state_grid[3][0];
    state_grid[3][0] = t;
}

// GF(2^8) multiply 
// Ref: FIPS-197 4.2.1
static uint8_t galois_multiply(uint8_t a, uint8_t b) {
    uint8_t p = 0;
    for (int i = 0; i < 8; ++i) {
        if (b & 1) p ^= a;
        uint8_t hi = a & 0x80;
        a <<= 1;
        if (hi) a ^= 0x1b;   // irreducible polynomial (x^8 + x^4 + x^3 + x + 1)
        b >>= 1;
    }
    return p;
}

// MixColumns (matrix multiply in GF(2^8))
// each column is transformed independently
static void mix_columns_transform(uint8_t state_grid[4][4]) {
    uint8_t col[4];
    for (int c = 0; c < 4; ++c) {
        // stash the column first (avoids in-place overwrite issues)
        for (int r = 0; r < 4; ++r) col[r] = state_grid[r][c];

        state_grid[0][c] = galois_multiply(col[0], 2) ^ galois_multiply(col[1], 3) ^
                           galois_multiply(col[2], 1) ^ galois_multiply(col[3], 1);
        state_grid[1][c] = galois_multiply(col[0], 1) ^ galois_multiply(col[1], 2) ^
                           galois_multiply(col[2], 3) ^ galois_multiply(col[3], 1);
        state_grid[2][c] = galois_multiply(col[0], 1) ^ galois_multiply(col[1], 1) ^
                           galois_multiply(col[2], 2) ^ galois_multiply(col[3], 3);
        state_grid[3][c] = galois_multiply(col[0], 3) ^ galois_multiply(col[1], 1) ^
                           galois_multiply(col[2], 1) ^ galois_multiply(col[3], 2);
    }
    // // sanity print during dev:
    // std::cout << "[mix] state(0,0)=" << std::hex << (int)state_grid[0][0] << std::dec << "\n";
}

// XOR the round key with the state (AddRoundKey)
static void add_round_key_operation(uint8_t state_grid[4][4], const uint8_t* round_key) {
    // note: state is column-major in AES (r,c) -> index c*4 + r
    for (int c = 0; c < 4; ++c) {
        for (int r = 0; r < 4; ++r) {
            state_grid[r][c] ^= round_key[c * 4 + r];
        }
    }
    // // check
    // std::cout << "[ark] state(0,0)=" << std::hex << (int)state_grid[0][0] << std::dec << "\n";
}

// --- Main encryption routine ---
// Uses 14 externally provided round keys (cyclical_key_schedule[0..13])
void AES_dynamic_key_encryption(
    uint8_t current_data_block[16],
    const std::vector<uint8_t*>& cyclical_key_schedule
) {
    // 1) 16 bytes -> 4x4 state (col-major)
    uint8_t state_grid[4][4];
    for (int r = 0; r < 4; ++r) {
        for (int c = 0; c < 4; ++c) {
            state_grid[r][c] = current_data_block[c * 4 + r];
        }
    }

    // 2) Rounds 1..13 (standard SubBytes → ShiftRows → MixColumns → AddRoundKey)
    for (int i = 0; i < 13; ++i) {
        substitute_bytes_lookup(state_grid);
        shift_rows_transform(state_grid);
        mix_columns_transform(state_grid);
        add_round_key_operation(state_grid, cyclical_key_schedule[i]);
    }

    // 3) Final round (no MixColumns)
    substitute_bytes_lookup(state_grid);
    shift_rows_transform(state_grid);
    add_round_key_operation(state_grid, cyclical_key_schedule[13]);

    // 4) write state back to the 16-byte block (still column-major mapping)
    for (int r = 0; r < 4; ++r) {
        for (int c = 0; c < 4; ++c) {
            current_data_block[c * 4 + r] = state_grid[r][c];
        }
    }
}