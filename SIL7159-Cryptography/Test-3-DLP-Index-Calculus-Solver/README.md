Parallel Index Calculus Algorithm for DLP
This project is a C++ implementation of the Index Calculus algorithm designed to solve the Discrete Logarithm Problem (DLP) in the multiplicative group Z*_p*. The implementation is parallelized using the Message Passing Interface (MPI) to accelerate the most computationally intensive phase of the algorithm and uses the GMP (GNU Multiple Precision Arithmetic) library to handle cryptographically large integers.

The program is capable of solving DLP for primes ranging from 10 to 40 digits, dynamically adjusting its parameters for optimal performance based on the input prime size.

Features
Safe Prime Generation: Generates a cryptographically secure safe prime p of a given bit length.

Generator Finding: Efficiently finds and lists generators for the group Z*_p*.

Parallel Relation Collection: The core of the algorithm, this stage uses MPI to distribute the search for smooth relations across multiple processes, significantly reducing runtime.

Dynamic Solver: The program dynamically adapts its parameters (like the factor base size) based on the size of the prime, making it effective for a wide range of problem sizes (10-40 digits).

Robust Linear Algebra: Implements a Gaussian elimination solver for systems of linear congruences and includes a dynamic retry mechanism that automatically collects more relations if the initial set is linearly dependent (singular matrix).

Interactive UI: A command-line menu allows users to select predefined test cases or enter manual values for alpha and beta to solve custom DLP instances.

Attractive Console Output: Uses formatted and colored text to clearly distinguish the various stages of the algorithm and display mathematical results.

Prerequisites
To compile and run this program, you will need the following dependencies installed on your system:

A C++ compiler that supports C++11 (e.g., g++).

An MPI implementation (e.g., Open MPI or MPICH).

The GNU Multiple Precision Arithmetic Library (GMP), including its C++ interface (-lgmpxx).

On a Debian-based system (like Ubuntu or Kali Linux), you can install these with:

sudo apt-get update
sudo apt-get install build-essential libgmp3-dev libmpfr-dev libmpc-dev openmpi-bin libopenmpi-dev

Compilation
The project includes a Makefile that simplifies the compilation process.

Navigate to the project's root directory in your terminal.

Run the make command. This will use mpic++ to compile all the source files and link them with the necessary GMP and MPI libraries.

make

This will create an executable file named index_calculus.

To remove all compiled object files and the executable, you can run:

make clean

Execution
The program is executed using the mpirun command, which launches the application in a parallel environment.

Command Structure
mpirun -np <num_processes> --oversubscribe ./index_calculus <n_bits>

-np <num_processes>: Specifies the total number of parallel processes to use (e.g., 4, 8, 32).

--oversubscribe: Important for personal machines. This flag allows you to run more processes than the number of physical CPU cores, which is necessary for testing on laptops and desktops.

./index_calculus: The name of the compiled program.

<n_bits>: The desired bit length for the safe prime p.

Examples
For a 10-13 digit prime (fast execution):
Use a bit length between 33 and 43.

mpirun -np 4 --oversubscribe ./index_calculus 40

For a 30-40 digit prime (slow, computationally intensive execution):
Use a bit length between 100 and 133.

mpirun -np 32 --oversubscribe ./index_calculus 100

Program Functioning
The program guides the user through an interactive command-line interface.

1. Initialization
Upon launch, the program first generates a safe prime p and a list of 10 unique generators for the group Z*_p*.

2. Manual Problem Setup
You are then prompted to set up the DLP instance (p, alpha, beta):

Select alpha: You must choose one of the available generators from the list.

Set beta: You can either choose to enter beta manually or have it generated automatically by the test cases.

3. Test Case Menu
An interactive menu is presented with the following options:

Test Cases (1-3): These will automatically generate a secret exponent x, compute beta = alpha^x mod p, and then solve for x.

Manual Entry for beta (4): If you did not set beta manually at the start, this option allows you to do so now.

Display DLP Instance Only (0): If you have entered beta manually, this option will print the full DLP problem details and return to the menu without starting the lengthy computation. This is useful for demonstrations.

Exit (5): Terminates the program.

4. Algorithm Execution
Once a test case is selected, the program proceeds through the main stages of the Index Calculus algorithm:

Stage 1 (Relation Collection): The program searches in parallel for the required number of smooth relations. A progress indicator is displayed by the master process.

Stage 2 (Linear Algebra): The system of linear congruences is solved. If the matrix is singular, the program automatically returns to Stage 1 to collect more relations and retries until a solution is found.

Stage 3 (Final DLP Computation): The final discrete logarithm for beta is computed.

Verification: The program verifies the result by computing alpha^x mod p and checking if it matches the original beta.