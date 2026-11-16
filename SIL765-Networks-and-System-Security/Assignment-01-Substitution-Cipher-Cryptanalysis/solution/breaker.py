#!/usr/bin/env python3

import sys
import os
import random
import time
import string
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed

# --- Configuration ---
CIPHER_ALPHABET = "1234567890@#$zyxwvutsrqpon"
PLAIN_ALPHABET = string.ascii_lowercase

# Execution Constraints
MAX_TIME = 90  

# Heuristic Weights (Tuned for Generality)
WEIGHT_BI = 2.0
WEIGHT_TRI = 3.0
WEIGHT_QUAD = 4.0
WEIGHT_QUINT = 6.0
WEIGHT_VOCAB = 40.0 

# Penalties
DEFAULT_BI_PENALTY = -8.0
DEFAULT_TRI_PENALTY = -10.0
DEFAULT_QUAD_PENALTY = -12.0
DEFAULT_QUINT_PENALTY = -15.0

@contextlib.contextmanager
def suppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:  
            yield
        finally:
            sys.stdout = old_stdout

# --- Data Loading ---
with suppress_stdout():
    try:
        from ngram_data import ENGLISH_BIGRAMS
    except ImportError:
        ENGLISH_BIGRAMS = {}

    try:
        from ngram_data import ENGLISH_TRIGRAMS
    except ImportError:
        ENGLISH_TRIGRAMS = {}

    try:
        from ngram_data import ENGLISH_QUADGRAMS
    except ImportError:
        ENGLISH_QUADGRAMS = {}
    
    try:
        from ngram_data import ENGLISH_QUINTGRAMS
    except ImportError:
        ENGLISH_QUINTGRAMS = {}

    try:
        from dictionary_data import ENGLISH_VOCAB
    except ImportError:
        ENGLISH_VOCAB = set()

    #if len(ENGLISH_VOCAB) < 1000:
    #    sys.stderr.write(f"\n[WARNING] Dictionary NOT loaded! Size: {len(ENGLISH_VOCAB)} (Using Fallback)\n")
    #else:
    #    sys.stderr.write(f"\n[SUCCESS] Dictionary Loaded. Size: {len(ENGLISH_VOCAB)} words.\n")
"""
# Basic Fallbacks to ensure logic doesn't crash if data is missing
if not ENGLISH_BIGRAMS:
    ENGLISH_BIGRAMS = {'TH': -1.52, 'HE': -1.59}
if not ENGLISH_TRIGRAMS:
    ENGLISH_TRIGRAMS = {'THE': -1.8, 'AND': -1.9}
if not ENGLISH_QUADGRAMS:
    ENGLISH_QUADGRAMS = {'THAT': -2.54, 'THER': -2.61}

"""

class CipherSolver:
    def __init__(self, ciphertext):
        self.ciphertext = ciphertext
        # Pre-calculate seen chars for the x masking rule
        self.seen_chars = set(c for c in ciphertext if c in CIPHER_ALPHABET)
        
        # Optimisation (Pre process ciphertext)
        # 1. Clean string for N-gram scoring (removes spaces/punctuation once)
        self.clean_cipher_str = "".join([c for c in ciphertext if c in CIPHER_ALPHABET])
        
        # 2. Extract words for Vocab scoring 
        self.cipher_words = []
        current_word = []
        for char in ciphertext:
            if char in CIPHER_ALPHABET:
                current_word.append(char)
            else:
                if current_word:
                    self.cipher_words.append("".join(current_word))
                    current_word = []
        if current_word:
            self.cipher_words.append("".join(current_word))

    def decrypt(self, text, key_str):
        #Full decryption for final output.
        trans_table = str.maketrans(key_str, PLAIN_ALPHABET)
        return text.translate(trans_table)

    def score_key(self, key_str):
        # Optimized scoring function which Uses Bigrams through Quintgrams + Dictionary for maximum generality
        trans_table = str.maketrans(key_str, PLAIN_ALPHABET)
        
        # 1. Decrypt clean string for N-grams 
        clean_text = self.clean_cipher_str.translate(trans_table).upper()
        
        score = 0
        if len(clean_text) < 5: return -1e10

        # Bigrams 
        if ENGLISH_BIGRAMS:
            for i in range(len(clean_text) - 1):
                bi = clean_text[i:i+2]
                score += ENGLISH_BIGRAMS.get(bi, DEFAULT_BI_PENALTY) * WEIGHT_BI

        # Trigrams
        if ENGLISH_TRIGRAMS:
            for i in range(len(clean_text) - 2):
                tri = clean_text[i:i+3]
                score += ENGLISH_TRIGRAMS.get(tri, DEFAULT_TRI_PENALTY) * WEIGHT_TRI
        
        # Quadgrams
        for i in range(len(clean_text) - 3):
            quad = clean_text[i:i+4]
            score += ENGLISH_QUADGRAMS.get(quad, DEFAULT_QUAD_PENALTY) * WEIGHT_QUAD

        # Quintgrams
        if ENGLISH_QUINTGRAMS:
            for i in range(len(clean_text) - 4):
                quint = clean_text[i:i+5]
                score += ENGLISH_QUINTGRAMS.get(quint, DEFAULT_QUINT_PENALTY) * WEIGHT_QUINT

        # 2. Vocabulary Score 
        if ENGLISH_VOCAB:
            hits = 0
            for c_word in self.cipher_words:
                p_word = c_word.translate(trans_table).upper()
                if len(p_word) > 2 and p_word in ENGLISH_VOCAB:
                    hits += 1
            score += hits * WEIGHT_VOCAB
            
        return score

def worker_routine(ciphertext, timeout):
    #Worker process running Iterated Local Search.
    with suppress_stdout():
        try:
            solver = CipherSolver(ciphertext)
            best_local_key = None
            best_local_score = -float('inf')
            
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # 1. Random Start
                c_list = list(CIPHER_ALPHABET)
                random.shuffle(c_list)
                parent_key = "".join(c_list)
                parent_score = solver.score_key(parent_key)
                
                # Kick cycles to escape local maxima 
                kick_cycles = 0
                max_kick_cycles = 10
                
                while kick_cycles < max_kick_cycles and (time.time() - start_time < timeout):
                    
                    # A. Stochastic Hill Climbing 
                    patience = 2000
                    fails = 0
                    while fails < patience:
                        a = random.randint(0, 25)
                        b = random.randint(0, 25)
                        
                        p_list = list(parent_key)
                        p_list[a], p_list[b] = p_list[b], p_list[a]
                        child_key = "".join(p_list)
                        
                        child_score = solver.score_key(child_key)
                        
                        if child_score > parent_score:
                            parent_score = child_score
                            parent_key = child_key
                            fails = 0
                        else:
                            fails += 1
                    
                    # B. Deterministic Refinement 
                    # Scan possible single swaps. If any swap improves the score, take it.
                    improved_deterministic = True
                    while improved_deterministic and (time.time() - start_time < timeout):
                        improved_deterministic = False
                        for i in range(26):
                            for j in range(i + 1, 26):
                                p_list = list(parent_key)
                                p_list[i], p_list[j] = p_list[j], p_list[i]
                                temp_key = "".join(p_list)
                                temp_score = solver.score_key(temp_key)
                                
                                if temp_score > parent_score:
                                    parent_score = temp_score
                                    parent_key = temp_key
                                    improved_deterministic = True
                                    break 
                                # Restart scan with new key
                            if improved_deterministic:
                                break
                    
                    # Update local best
                    if parent_score > best_local_score:
                        best_local_score = parent_score
                        best_local_key = parent_key
                        kick_cycles = 0 
                    else:
                        kick_cycles += 1
                    
                    # C. Perturbation (Kick). Mutate 3 random pairs to jump to a new search area
                    p_list = list(parent_key)
                    for _ in range(3):
                        ka = random.randint(0, 25)
                        kb = random.randint(0, 25)
                        p_list[ka], p_list[kb] = p_list[kb], p_list[ka]
                    parent_key = "".join(p_list)
                    parent_score = solver.score_key(parent_key)

            return best_local_score, best_local_key
        except Exception:
            # Safe fallback in case of crash
            return -float('inf'), CIPHER_ALPHABET

def format_key_output(key_str, seen_chars):
    #Format key: substitute x if cipher char not in ciphertext.
    
    res = ""
    if not key_str or len(key_str) != 26: 
        return "x" * 26
    
    for i in range(26):
        cipher_char = key_str[i]
        if cipher_char in seen_chars:
            res += cipher_char
        else:
            res += "x"
    return res

def main():
    input_text = ""
    output_file = None
    
    # Input Handling 
    # 1. Command Line Arguments
    if len(sys.argv) >= 2:
        try:
            if os.path.exists(sys.argv[1]):
                with open(sys.argv[1], 'r', encoding='utf-8') as f:
                    input_text = f.read().strip()
                if len(sys.argv) >= 3:
                    output_file = sys.argv[2]
            else:
                sys.stderr.write(f"Error: Input file '{sys.argv[1]}' not found.\n")
                return
        except Exception:
            return

    # 2. Standard Input (Pipeline)
    if not input_text:
        try:
            if not sys.stdin.isatty():
                input_text = sys.stdin.read().strip()
        except Exception:
            pass

    if not input_text:
        if len(sys.argv) < 2:
            sys.stderr.write("Usage: python breaker.py <input_file> [output_file]\n")
        return

    # Execution 
    num_workers = os.cpu_count() or 4
    worker_timeout = MAX_TIME - 5
    best_global_score = -float('inf')
    best_global_key = CIPHER_ALPHABET

    try:
        # Multiprocessing
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker_routine, input_text, worker_timeout) for _ in range(num_workers)]
            for future in as_completed(futures):
                try:
                    score, key = future.result(timeout=worker_timeout + 5)
                    if score > best_global_score:
                        best_global_score = score
                        best_global_key = key
                except Exception:
                    continue
    except Exception:
        # Single threaded fallback
        best_global_score, best_global_key = worker_routine(input_text, worker_timeout)

    # Output Generation 
    try:
        solver = CipherSolver(input_text)
        
        # Validate key integrity
        if not best_global_key or len(best_global_key) != 26:
             best_global_key = CIPHER_ALPHABET

        decrypted_text = solver.decrypt(input_text, best_global_key)
        final_key_str = format_key_output(best_global_key, solver.seen_chars)
        
        output_content = f"Deciphered Plaintext: {decrypted_text}\nDeciphered Key: {final_key_str}"

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_content)
                f.flush()
        else:
            print(output_content, end='', flush=True)

    except Exception as e:
        # Failsafe output
        err = f"Deciphered Plaintext: ERROR\nDeciphered Key: xxxxxxxxxxxxxxxxxxxxxxxxxx\n"
        if output_file:
            with open(output_file, 'w') as f: f.write(err)
        else:
            print(err)

if __name__ == "__main__":
    main()