#!/usr/bin/env python3
"""
SIL765: Assignment 1 - Substitution Cipher Generator
Description: 
    Generates a random key based on the assignment's alphabet set OR uses a 
    manually provided key to encrypt a given plaintext file.
    Use this to generate "ground truth" test cases to verify your cryptanalysis solver.

Usage: 
    python cipher_generator.py <plaintext_file>
"""

import sys
import os
import random
import string

# ==============================================================================
# CONFIGURATION (Must match Assignment Specs)
# ==============================================================================
# The set of characters used in the Plaintext (a-z)
PLAIN_CHARS = string.ascii_lowercase

# The set of characters used in the Ciphertext
CIPHER_CHARS = "1234567890@#$zyxwvutsrqpon"

# ------------------------------------------------------------------------------
# MANUAL KEY OPTION
# Paste your 26-character key string here to force a specific encryption mapping.
# The string implies mapping for a, b, c... z in order.
# Leave it empty ("") to generate a random key automatically.
# Example: "3456120987pqrstzyxwvu$@#no"
# ------------------------------------------------------------------------------
MANUAL_KEY = "" 

def get_cipher_key():
    """
    Determines whether to use the MANUAL_KEY or generate a random one.
    
    Returns:
        key_map (dict): Mapping from Plain char -> Cipher char
        key_string (str): The string representation of the key
    """
    if MANUAL_KEY and len(MANUAL_KEY) == 26:
        key_string = MANUAL_KEY
        print(f"[Info] Using Manual Key: {key_string}")
    else:
        # Generate Random Permutation
        chars_list = list(CIPHER_CHARS)
        random.shuffle(chars_list)
        key_string = "".join(chars_list)
        print(f"[Info] Generated Random Key: {key_string}")

    # Create Dictionary Map
    key_map = {}
    for i, char in enumerate(PLAIN_CHARS):
        key_map[char] = key_string[i]
        
    return key_map, key_string

def encrypt_text(plaintext, key_map):
    """
    Encrypts the plaintext using the key_map.
    Case-insensitive mapping: 'A' -> maps same as 'a'.
    Non-alpha chars are preserved.
    """
    cipher_chars = []
    for char in plaintext:
        if char.lower() in key_map:
            # Map valid chars
            cipher_chars.append(key_map[char.lower()])
        else:
            # Keep punctuation/spaces/numbers/newlines as is
            cipher_chars.append(char)
    return "".join(cipher_chars)

def generate_masked_key(key_string, plaintext):
    """
    Generates the key string with unused characters masked as 'x'.
    Rule: If a plaintext character (e.g., 'z') is not present in the input text,
    its corresponding character in the key string is replaced with 'x'.
    """
    # Identify which plaintext characters are actually used
    used_chars = set(c.lower() for c in plaintext if c.lower() in PLAIN_CHARS)
    
    masked_key_list = []
    
    # Iterate through a-z to build the key string
    for i, plain_char in enumerate(PLAIN_CHARS):
        if plain_char in used_chars:
            masked_key_list.append(key_string[i])
        else:
            masked_key_list.append('x')
            
    return "".join(masked_key_list)

def main():
    # 1. Input Handling
    if len(sys.argv) < 2:
        print("Usage: python cipher_generator.py <plaintext_file>")
        return

    input_file = sys.argv[1]
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            plaintext = f.read()
            if not plaintext:
                print("[Error] Input file is empty.")
                return
    except Exception as e:
        print(f"[Error] Could not read file: {e}")
        return

    # 2. Key Generation & Encryption
    key_map, key_string = get_cipher_key()
    ciphertext = encrypt_text(plaintext, key_map)
    
    # Generate Masked Key for verification (The "Answer" format)
    masked_key = generate_masked_key(key_string, plaintext)

    # 3. Output
    output_filename = "test_ciphertext.txt"
    ground_truth_filename = "test_ground_truth.txt" # Helper file to verify results easily

    try:
        # Save Ciphertext (Input for Solver)
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(ciphertext)
            
        # Save Ground Truth (For your manual verification)
        with open(ground_truth_filename, 'w', encoding='utf-8') as f:
            f.write(f"--- ORIGINAL PLAINTEXT ---\n{plaintext}\n\n")
            f.write(f"--- FULL KEY (a-z) ---\n{key_string}\n\n")
            f.write(f"--- EXPECTED SOLVER OUTPUT ---\n")
            f.write(f"Deciphered Key: {masked_key}\n\n")
            f.write(f"--- CIPHERTEXT ---\n{ciphertext}\n")

        print(f"\n[Success] Encryption complete.")
        print(f"1. Ciphertext saved to:  {output_filename} (Feed this to your solver)")
        print(f"2. Answer Key saved to:  {ground_truth_filename} (Use this to verify)")
        print("-" * 60)
        # Using a newline if plaintext is long, or truncated for console
        print(f"Deciphered Plaintext: {plaintext[:50].replace(chr(10), ' ')}... (truncated)")
        print(f"Deciphered Key: {masked_key}")
        print("-" * 60)

    except Exception as e:
        print(f"[Error] Could not write output files: {e}")

if __name__ == "__main__":
    main()