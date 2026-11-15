# TIMELY Congestion Control Simulator

This project is a C++ implementation of the TIMELY congestion control protocol, based on the SIGCOMM 2015 paper "TIMELY: RTT-based Congestion Control for the Datacenter." It includes a virtual simulator to run experiments and a Python script to automatically generate and visualize the results.

## Project Structure

-   **`main.cpp`**: Provides the main user interface (UI) for selecting experiments, setting parameters and managing the simulation.
-   **`simulator.h` / `simulator.cpp`**: Implements a modular, event-driven network simulator. It models senders, receivers and a bottleneck switch queue to simulate network behavior with microsecond precision.
-   **`timely.h` / `timely.cpp`**: Contains the core implementation of the TIMELY congestion control algorithm as described in Algorithm 1 of the paper.
-   **`generate_graphs.py`**: A Python script that uses `pandas` and `matplotlib` to read simulation output from `.csv` files and generate graphs that replicate the key findings of the paper.
-   **`Makefile`**: A simple makefile to compile the C++ source code.
-   **`README.md`**: This file.

## Features

-   **Interactive Console UI**: Allows the user to select from a list of predefined experiments from the paper and the extended project scope.
-   **Customizable Parameters**: Users can either run simulations with the paper's default parameters for best-aligned results or input them manually.
-   **Modular Simulation**: A C++17 event-driven simulator models network components for precise, microsecond-level virtual scheduling.
-   **Automated Data and Graph Generation**:
    -   Simulation results are automatically saved to `.csv` files in the `output/csv/` directory.
    -   The C++ application automatically invokes the Python script to generate graphs from the CSV data, which are saved in `output/graphs/`.
-   **Clear Outputs**: An option to easily clear all generated CSV files and graphs.

## How to Compile and Run

### Prerequisites

1.  A C++ compiler that supports C++17 (e.g., `g++`).
2.  `make` build automation tool.
3.  Python 3.x.
4.  Required Python libraries: `pandas` and `matplotlib`.

You can install the Python libraries using pip:
```
pip install pandas matplotlib
```

### Compilation

Navigate to the project directory and run `make`:

```
make
```

This will compile the C++ source files and create an executable named `timely_sim`.

### Running the Simulator

Execute the compiled program from your terminal:

```
./timely_sim
```

You will be greeted with a menu. Follow the on-screen prompts to:
1.  Select an experiment to run.
2.  Choose between default or manual parameters.
3.  View console logs and find generated outputs in the `output/` folder.
4.  Clear previous results or exit the application.

```

***