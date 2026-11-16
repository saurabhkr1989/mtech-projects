#!/usr/bin/env python3
"""
SIL7165: Basic Cryptanalysis (Assignment 1)

    This script implements a Stochastic Hill Climbing algorithm accelerated by Multiprocessing to break Substitution Ciphers which relies on Semantic Anchoring (Dictionary Validation) and N-Gram statistics
    to navigate key space efficiently.

    Architecture Highlights:
    - Parallel Processing : Utilization of all CPU cores for independent restarts.
    - Optimization : Early abandonment of poor starting points and swap pass to resolve local minima
    - Dictionary for prioritizing over N Gram models.

"""

import sys
import os
import random
import time
import string
#import math
from concurrent.futures import ProcessPoolExecutor, as_completed
#from collections import Counter

# Language Models
CIPHER_ALPHABET = "1234567890@#$zyxwvutsrqpon"
PLAIN_ALPHABET = string.ascii_lowercase

# Time and Resource Limits
MAX_EXECUTION_TIME_SECONDS = 90
NUMBER_OF_WORKER_PROCESSES = os.cpu_count() or 4 

# Debugging Flag 
DEBUG_MODE = False

# Color Codes for Console Output
class ConsoleStyle:
    HEADER = '\033[95m'
    BLUE_INFO = '\033[94m'
    GREEN_SUCCESS = '\033[92m'
    YELLOW_WARN = '\033[93m'
    RED_FAIL = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Importing statistical models 
try:
    from ngram_data import ENGLISH_BIGRAMS, ENGLISH_TRIGRAMS, ENGLISH_QUADGRAMS, ENGLISH_QUINTGRAMS
    from dictionary_data import ENGLISH_VOCAB
except ImportError as import_error:
    print(f"{ConsoleStyle.RED_FAIL}[Critical Error] Missing data files: {import_error}{ConsoleStyle.RESET}")
    sys.exit(1)

# Penalty scores for N-Grams 
DEFAULT_QUAD_PENALTY = -12.0
DEFAULT_QUINT_PENALTY = -15.0

class SubstitutionCipherSolver:
    # Core solver logic encapsulating fitness scoring and hill climbing algorithms.
    def __init__(self, ciphertext_input):
        self.ciphertext_raw = ciphertext_input
        
        # Calculating indices of valid cipher characters to avoid repeatedly checking validity of cipher alphabet during scoring loops.
        self.valid_cipher_indices = [char for char in ciphertext_input if char in CIPHER_ALPHABET]

    def _calculate_fitness_score(self, current_key_map):
        """
        Calculates the fitness score of a candidate key wherein higher score indicates text that it is closely resembles English.
        
        Fitness Logic 
            -   Dictionary Coverage is Primary : Checks for whole words found in the dictionary and Matches receive an exponential bonus based on word length.
            -   N-Gram Probability is Secondary : Uses Quadgrams and Quintgrams for smoothing for providing a gradient when exact word matches are not yet found.
        
        """
        # Decryption of only  relevant characters for N gram analysis
        decrypted_chars_list = [current_key_map.get(char, ' ') for char in self.valid_cipher_indices]
        decrypted_text_segment = "".join(decrypted_chars_list).upper()
        text_length = len(decrypted_text_segment)
        
        # Guard clause for extremely short texts
        if text_length < 5: return -99999.0
        
        fitness_score = 0.0
        
        # N-Gram Smoothing (Gradient) - Sum log probabilities of Quadgrams and Quintgrams for climbing towards English like patterns even before full words form.
        for i in range(text_length - 3):
            quadgram = decrypted_text_segment[i:i+4]
            fitness_score += 4.0 * ENGLISH_QUADGRAMS.get(quadgram, DEFAULT_QUAD_PENALTY)
            
        for i in range(text_length - 4):
            quintgram = decrypted_text_segment[i:i+5]
            fitness_score += 6.0 * ENGLISH_QUINTGRAMS.get(quintgram, DEFAULT_QUINT_PENALTY)
            
        # Dictionary Anchoring (Semantic Lock) for reconstructing full text to check word boundaries.
        if text_length > 10: 
            
            # Uncomment to inspect raw text reconstruction during scoring
            # if DEBUG_MODE and random.random() < 0.001:
            #     print(f"[Debug] Scoring Text: {decrypted_text_segment[:40]}...")
            
            # Optimization: Sampling first 1000 characters for speed if text is huge
            sample_size = min(len(self.ciphertext_raw), 1000)
            reconstructed_chars = []
            for i in range(sample_size):
                char = self.ciphertext_raw[i]
                # If char is in cipher alphabet map it otherwise keep original 
                reconstructed_chars.append(current_key_map.get(char, char))
            
            reconstructed_string = "".join(reconstructed_chars).upper()
            
            # Simple tokenization for Replacing punctuation with spaces to isolate words
            for punct in string.punctuation:
                reconstructed_string = reconstructed_string.replace(punct, " ")
            

            candidate_words = reconstructed_string.split()
            vocabulary_bonus = 0.0
            


            for word_token in candidate_words:
                clean_word = word_token.strip()
                # Exponential Bonus : Square of length * 5.0 to ensure real words heavily outweigh random N-gram noise.
                if len(clean_word) > 2 and clean_word in ENGLISH_VOCAB:
                    vocabulary_bonus += (len(clean_word) ** 2) * 5.0
            

            fitness_score += vocabulary_bonus
        
        return fitness_score

    def _generate_key_map(self, plain_chars_permutation):
        # Helper to create  Cipher->Plain  mapping dictionary from a list.
        
        return {cipher: plain for cipher, plain in zip(CIPHER_ALPHABET, plain_chars_permutation)}

    def execute_single_solver_run(self, random_seed):
       
        """
        Worker Function : Executing one independent instance of Stochastic Hill Climbing.
        This function is designed to be serialized and run in a separate process.
        """
        random.seed(random_seed)
        
        # Random Initialization
        current_key_permutation = list(PLAIN_ALPHABET)
        random.shuffle(current_key_permutation)
        

        current_map = self._generate_key_map(current_key_permutation)
        current_score = self._calculate_fitness_score(current_map)
        
        # Stochastic Hill Climbing 
        # Coarse Tuning : Randomly mutate key (If better -> keep. If worse -> revert); Iteration count is tuned to 1500 to allow Fail Fast behavior.
      
        for _ in range(1500):
            # Mutation : Swap 2 random characters
            idx_a, idx_b = random.sample(range(26), 2)
            current_key_permutation[idx_a], current_key_permutation[idx_b] = current_key_permutation[idx_b], current_key_permutation[idx_a]
            
            new_map = self._generate_key_map(current_key_permutation)
            new_score = self._calculate_fitness_score(new_map)
            
            if new_score > current_score:
               
                current_score = new_score
                # Improvement found : Keep the swap
            else:
                # No improvement : Revert the swap
                current_key_permutation[idx_a], current_key_permutation[idx_b] = current_key_permutation[idx_b], current_key_permutation[idx_a]
        
        # Deterministic Polish 
        # Fine Tuning: Systematically check every possible pair swap (325 combinations) guaranting convergence to  local maximum for  current basin.
        is_improving = True
        while is_improving:
            is_improving = False
            for i in range(len(current_key_permutation)):
                for j in range(i + 1, len(current_key_permutation)):
                    # Tentative Swap
                    current_key_permutation[i], current_key_permutation[j] = current_key_permutation[j], current_key_permutation[i]
                    
                    new_map = self._generate_key_map(current_key_permutation)
                    new_score = self._calculate_fitness_score(new_map)
                    
                    if new_score > current_score:
                        current_score = new_score
                        is_improving = True 
                        # Improvement found, restart loop to reevaluate new basin
                    else:
                        # Revert Swap
                        current_key_permutation[i], current_key_permutation[j] = current_key_permutation[j], current_key_permutation[i]
                        
        return current_score, current_key_permutation

def orchestrate_parallel_solver(ciphertext_input):
    """
    Manager function that coordinates the parallel execution of solver workers and Collect results for tracking  global best solution.
    """
    start_time = time.time()
    solver_instance = SubstitutionCipherSolver(ciphertext_input)
    
    global_best_score = -float('inf')
    global_best_key_list = None
    
    print(f"{ConsoleStyle.BLUE_INFO}[Phase 1] Initializing Parallel Workers ({NUMBER_OF_WORKER_PROCESSES} cores)...{ConsoleStyle.RESET}")

    # ProcessPoolExecutor manages a pool of worker processes
    with ProcessPoolExecutor(max_workers=NUMBER_OF_WORKER_PROCESSES) as executor:
        futures_list = []
        
        # Submit initial batch of jobs - Submit 4x  core count to ensure the CPU pipeline stays full
        for _ in range(NUMBER_OF_WORKER_PROCESSES * 4):
            seed = random.randint(0, 100000)
            futures_list.append(executor.submit(solver_instance.execute_single_solver_run, seed))
            
        # Processing results as they complete 
        for future in as_completed(futures_list):
            # Enforcing Time Limit Constraint
            elapsed_time = time.time() - start_time
            if elapsed_time > (MAX_EXECUTION_TIME_SECONDS - 2):
                print(f"{ConsoleStyle.YELLOW_WARN}[Time Limit] Stopping optimization to meet deadline.{ConsoleStyle.RESET}")
                break
                
            score, key_list = future.result()
            
            # Uncomment to view the result of every single worker thread
            # if DEBUG_MODE:
            #     print(f"[Debug] Worker finished. Score: {score:.2f}")
            
            if score > global_best_score:
                global_best_score = score
                global_best_key_list = key_list
                if DEBUG_MODE:
                    print(f"{ConsoleStyle.GREEN_SUCCESS}  > New Best Score: {score:.2f}{ConsoleStyle.RESET}")

    # Convert best key list back to a mapping dictionary
    if global_best_key_list:
        return {cipher_char: plain_char for cipher_char, plain_char in zip(CIPHER_ALPHABET, global_best_key_list)}
    else:
        return {}




# MAIN EXECUTION FLOW

def helper_decrypt_full_text(ciphertext, key_map):
    """
    Decrypts the entire ciphertext using the provided key map. Preserves anchors (characters not in the cipher alphabet).
    """
    result_chars = []
    for char in ciphertext:
        # Get mapping or keep original if not in cipher alphabet (Anchor)
        result_chars.append(key_map.get(char, char))
    return "".join(result_chars)

def helper_format_key_string(key_map):
    """
    Formats the key string for submission (a->?, b->?, ...) and Returns the string of cipher characters corresponding to a-z.
    """
    # Invert mapping to get Plain -> Cipher
    plain_to_cipher_map = {v: k for k, v in key_map.items()}
    # Construct string in a-z order
    return "".join([plain_to_cipher_map.get(char, '?') for char in PLAIN_ALPHABET])

def helper_save_results_to_file(original_text, plaintext, key_string):
    """
    Writes final results to 'output.txt'.
    """
    try:
        with open("output.txt", "w", encoding='utf-8') as file_handle:
            file_handle.write("--- CIPHER TEXT ---\n" + original_text + "\n\n")
            file_handle.write("--- DECIPHERED PLAIN TEXT ---\n" + plaintext + "\n\n")
            file_handle.write("--- DECIPHERED KEY ---\n" + key_string + "\n")
        return True
    except IOError as error_msg:
        print(f"{ConsoleStyle.RED_FAIL}[Error] File write failed: {error_msg}{ConsoleStyle.RESET}")
        return False

def main_entry_point():
    print(f"{ConsoleStyle.HEADER}{'='*60}")
    print(f"Substitution Cipher Breaker ")
    print(f"{'='*60}{ConsoleStyle.RESET}\n")

    # Command Line Argument Parsing
    if len(sys.argv) < 2:
        print(f"{ConsoleStyle.RED_FAIL}Usage: python cryptanalysis_solver.py <file.txt>{ConsoleStyle.RESET}")
        return

    input_filename = sys.argv[1]
    if not os.path.exists(input_filename):
        print(f"{ConsoleStyle.RED_FAIL}File '{input_filename}' not found.{ConsoleStyle.RESET}")
        return

    # Read Ciphertext
    try:
        with open(input_filename, 'r', encoding='utf-8') as file_handle:
            file_content = file_handle.read()
    except Exception as error_msg:
        print(f"{ConsoleStyle.RED_FAIL}Read Error: {error_msg}{ConsoleStyle.RESET}")
        return

    # Uncomment to inspect the raw input content
    # print(f"[Debug] Input Content Length: {len(file_content)}")
    
    # Execute Solver
    best_key_map = orchestrate_parallel_solver(file_content)
    
    # Post Processing
    final_plaintext = helper_decrypt_full_text(file_content, best_key_map)
    final_key_string = helper_format_key_string(best_key_map)
    
    # Output Results
    if helper_save_results_to_file(file_content, final_plaintext, final_key_string):
        print(f"\n{ConsoleStyle.GREEN_SUCCESS}[Success] Results written to output.txt{ConsoleStyle.RESET}")
        print("-" * 60)
        print(f"{ConsoleStyle.BLUE_INFO}Final Key:{ConsoleStyle.RESET} {final_key_string}")
        print(f"{ConsoleStyle.BLUE_INFO}Preview:{ConsoleStyle.RESET}   {final_plaintext}...")

if __name__ == "__main__":
    main_entry_point()