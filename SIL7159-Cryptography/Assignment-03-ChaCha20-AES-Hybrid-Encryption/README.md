#ChaCha20-AES Hybrid Encryption

#This C++ program implements a hybrid encryption algorithm as described in the assignment. It uses ChaCha20 as a key generator to produce dynamic round keys for AES-256 encryption.

***The program is built as a console application and provides detailed intermediate output for all tasks, including the final cryptographic analysis (Entropy and Avalanche Effect).

**Code Structure

`The project is split into five main files:

`main.cpp: The main control center. Handles file I/O, orchestrates all tasks, and performs the final analysis.

``Note: The code defaults to using a CBC-like chaining mode, as this provides a much stronger avalanche effect (closer to the 50% ideal) than the simpler ECB mode.

`chacha_crypt.h / chacha_crypt.cpp: Contains all logic for ChaCha20, including state initialization (Task 1) and key block generation (Task 2).

`aes_crypt.h / aes_crypt.cpp: Contains all logic for AES, including the AES_dynamic_key_encryption function that runs the 14-round AES process (Task 3).

`input.txt: The input file containing the master key and plaintext.


#1. How to Compile

`A C++ compiler with C++17 support is required (e.g., g++ or clang++).

`Open your terminal, navigate to the directory containing all the .cpp and .h files, and run the following command:


***g++ main.cpp chacha_crypt.cpp aes_crypt.cpp -o hybrid_encrypt -std=c++17



g++: The compiler.

main.cpp chacha_crypt.cpp aes_crypt.cpp: The source files to compile.

-o hybrid_encrypt: The name of the final executable program.

-std=c++17: Specifies the C++17 standard (needed for some features like if with initialization).


#2. How to Run

Before running, you must have an input.txt file in the same directory.

input.txt Format

The program expects a very specific format for input.txt:

Line 1: The 128-character (64-byte) Master Key in hexadecimal.

Line 2 (and onward): The plaintext message to be encrypted. The program will read all subsequent lines as part of the plaintext.

An example input.txt is provided (input.txt).

Running the Program

Once compiled, run the executable from your terminal:


***./hybrid_encrypt



The program will automatically read input.txt, perform all encryption steps, and print a detailed, color-coded report to the console. This report includes all the intermediate outputs (S_0 state, K_1, K_2, P', C) and the final Task 4 analysis.