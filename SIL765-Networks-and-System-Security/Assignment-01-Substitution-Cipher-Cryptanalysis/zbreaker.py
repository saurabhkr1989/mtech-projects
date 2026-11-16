#!/usr/bin/env python3

import sys
import os
import random
import time
import string
from concurrent.futures import ProcessPoolExecutor, as_completed

# --- Configuration & Tuning ---
CIPHER_ALPHABET = "1234567890@#$zyxwvutsrqpon"
PLAIN_ALPHABET = string.ascii_lowercase

# Execution Constraints
MAX_EXECUTION_TIME_SECONDS = 90
NUMBER_OF_WORKER_PROCESSES = os.cpu_count() or 4 
DEBUG_MODE = False

# Heuristic Weights (Tuned for English text)
WEIGHT_QUAD = 4.0
WEIGHT_QUINT = 6.0
WEIGHT_VOCAB = 5.0

# Penalties
DEFAULT_QUAD_PENALTY = -12.0
DEFAULT_QUINT_PENALTY = -15.0

# Console Colors
HEADER = '\033[95m'
BLUE_INFO = '\033[94m'
GREEN_SUCCESS = '\033[92m'
YELLOW_WARN = '\033[93m'
RED_FAIL = '\033[91m'
RESET = '\033[0m'

try:
    from ngram_data import ENGLISH_BIGRAMS, ENGLISH_TRIGRAMS, ENGLISH_QUADGRAMS, ENGLISH_QUINTGRAMS
    from dictionary_data import ENGLISH_VOCAB
except ImportError as import_error:
    print(f"{RED_FAIL}[Critical Error] Missing data files: {import_error}{RESET}")
    sys.exit(1)

class SubstitutionCipherSolver:
    def __init__(self, ciphertext_input):
        self.ciphertext_raw = ciphertext_input
        self.filtered_cipher_chars = [char for char in ciphertext_input if char in CIPHER_ALPHABET]

    def _calculate_fitness_score(self, current_key_map):
        decrypted_chars_list = [current_key_map.get(char, ' ') for char in self.filtered_cipher_chars]
        decrypted_text_segment = "".join(decrypted_chars_list).upper()
        text_length = len(decrypted_text_segment)
        
        if text_length < 5: return -99999.0
        
        fitness_score = 0.0
        
        # N-Gram Analysis
        for i in range(text_length - 3):
            quadgram = decrypted_text_segment[i:i+4]
            fitness_score += WEIGHT_QUAD * ENGLISH_QUADGRAMS.get(quadgram, DEFAULT_QUAD_PENALTY)
            
        for i in range(text_length - 4):
            quintgram = decrypted_text_segment[i:i+5]
            fitness_score += WEIGHT_QUINT * ENGLISH_QUINTGRAMS.get(quintgram, DEFAULT_QUINT_PENALTY)
        
        # Dictionary Bonus (Sampled for large texts)
        if text_length > 10: 
            sample_size = min(len(self.ciphertext_raw), 1000)
            reconstructed_chars = []
            for i in range(sample_size):
                char = self.ciphertext_raw[i]
                reconstructed_chars.append(current_key_map.get(char, char))
            
            reconstructed_string = "".join(reconstructed_chars).upper()
            
            for punct in string.punctuation:
                reconstructed_string = reconstructed_string.replace(punct, " ")
            
            candidate_words = reconstructed_string.split()
            vocabulary_bonus = 0.0
            
            for word_token in candidate_words:
                clean_word = word_token.strip()
                if len(clean_word) > 2 and clean_word in ENGLISH_VOCAB:
                    vocabulary_bonus += (len(clean_word) ** 2) * WEIGHT_VOCAB
            
            fitness_score += vocabulary_bonus
        
        return fitness_score

    def _generate_key_map(self, plain_chars_permutation):
        return {cipher: plain for cipher, plain in zip(CIPHER_ALPHABET, plain_chars_permutation)}

    def execute_single_solver_run(self, random_seed):
        random.seed(random_seed)
        current_key_permutation = list(PLAIN_ALPHABET)
        random.shuffle(current_key_permutation)
        
        current_map = self._generate_key_map(current_key_permutation)
        current_score = self._calculate_fitness_score(current_map)
        
        # Stochastic Hill Climbing
        for _ in range(1500):
            idx_a, idx_b = random.sample(range(26), 2)
            current_key_permutation[idx_a], current_key_permutation[idx_b] = current_key_permutation[idx_b], current_key_permutation[idx_a]
            
            new_map = self._generate_key_map(current_key_permutation)
            new_score = self._calculate_fitness_score(new_map)
            
            if new_score > current_score:
                current_score = new_score
            else:
                # Revert swap
                current_key_permutation[idx_a], current_key_permutation[idx_b] = current_key_permutation[idx_b], current_key_permutation[idx_a]
        
        # Deterministic Local Polish
        is_improving = True
        while is_improving:
            is_improving = False
            for i in range(len(current_key_permutation)):
                for j in range(i + 1, len(current_key_permutation)):
                    current_key_permutation[i], current_key_permutation[j] = current_key_permutation[j], current_key_permutation[i]
                    
                    new_map = self._generate_key_map(current_key_permutation)
                    new_score = self._calculate_fitness_score(new_map)
                    
                    if new_score > current_score:
                        current_score = new_score
                        is_improving = True 
                    else:
                        current_key_permutation[i], current_key_permutation[j] = current_key_permutation[j], current_key_permutation[i]
                        
        return current_score, current_key_permutation

def run_solver_pipeline(ciphertext_input):
    start_time = time.time()
    solver_instance = SubstitutionCipherSolver(ciphertext_input)
    
    global_best_score = -float('inf')
    global_best_key_list = None
    
    print(f"{BLUE_INFO} Initializing Parallel Workers ({NUMBER_OF_WORKER_PROCESSES} cores){RESET}")

    with ProcessPoolExecutor(max_workers=NUMBER_OF_WORKER_PROCESSES) as executor:
        futures_list = []
        # Oversubscribe to ensure CPU saturation
        for _ in range(NUMBER_OF_WORKER_PROCESSES * 4):
            seed = random.randint(0, 100000)
            futures_list.append(executor.submit(solver_instance.execute_single_solver_run, seed))

        for future in as_completed(futures_list):
            elapsed_time = time.time() - start_time
            if elapsed_time > (MAX_EXECUTION_TIME_SECONDS - 2):
                print(f"{YELLOW_WARN}[Time Limit] Stopping optimization to meet deadline.{RESET}")
                break
                
            score, key_list = future.result()
            
            if score > global_best_score:
                global_best_score = score
                global_best_key_list = key_list
                if DEBUG_MODE:
                    print(f"{GREEN_SUCCESS}  > New Best Score: {score:.2f}{RESET}")

    if global_best_key_list:
        return {cipher_char: plain_char for cipher_char, plain_char in zip(CIPHER_ALPHABET, global_best_key_list)}
    else:
        return {}

# --- Helpers ---

def decrypt_text(ciphertext, key_map):
    result_chars = []
    for char in ciphertext:
        result_chars.append(key_map.get(char, char))
    return "".join(result_chars)

def format_key_output(key_map):
    plain_to_cipher_map = {v: k for k, v in key_map.items()}
    return "".join([plain_to_cipher_map.get(char, '?') for char in PLAIN_ALPHABET])

def save_results(original_text, plaintext, key_string):
    try:
        with open("output.txt", "w", encoding='utf-8') as file_handle:
            file_handle.write(" CIPHER TEXT \n" + original_text + "\n\n")
            file_handle.write(" DECIPHERED PLAIN TEXT \n" + plaintext + "\n\n")
            file_handle.write(" DECIPHERED KEY \n" + key_string + "\n")
        return True
    except IOError as error_msg:
        print(f"{RED_FAIL}[Error] File write failed : {error_msg}{RESET}")
        return False

def main():
    print(f"{HEADER}{'='*60}")
    print(f"Substitution Cipher Breaker")
    print(f"{'='*60}{RESET}\n")

    if len(sys.argv) < 2:
        print(f"{RED_FAIL}Usage : python cryptanalysis_solver.py <file.txt>{RESET}")
        return

    input_filename = sys.argv[1]
    if not os.path.exists(input_filename):
        print(f"{RED_FAIL}File '{input_filename}' not found.{RESET}")
        return

    try:
        with open(input_filename, 'r', encoding='utf-8') as file_handle:
            file_content = file_handle.read()
    except Exception as error_msg:
        print(f"{RED_FAIL}Read Error: {error_msg}{RESET}")
        return

    best_key_map = run_solver_pipeline(file_content)
    final_plaintext = decrypt_text(file_content, best_key_map)
    final_key_string = format_key_output(best_key_map)

    if save_results(file_content, final_plaintext, final_key_string):
        print(f"{BLUE_INFO}Cipher Text :{RESET} {file_content}\n")
        print(f"\n{GREEN_SUCCESS}[Success] Results written to output.txt{RESET}")
        print("-" * 60)
        print(f"{BLUE_INFO}Key :{RESET} {final_key_string}\n")
        print(f"{BLUE_INFO}Plain Text :{RESET}{final_plaintext}\n")

if __name__ == "__main__":
    main()