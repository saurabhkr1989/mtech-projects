import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys

# --- Configuration ---
CSV_FILENAME = 'analysis_results_raw.csv'
ENTROPY_GRAPH_FILE = 'entropy_vs_length.png'
AVALANCHE_GRAPH_FILE = 'avalanche_vs_length.png'
# ---

try:
    # Step 1: Read the raw data from the CSV
    # This loads all 10,000 test results into a DataFrame
    df = pd.read_csv(CSV_FILENAME)
except FileNotFoundError:
    print(f"Error: File not found: '{CSV_FILENAME}'")
    print("Please make sure you have run the 'run_analysis.sh' script first.")
    sys.exit(1)
except Exception as e:
    print(f"An error occurred while reading the file: {e}")
    sys.exit(1)

# Step 2: Aggregate the raw data
# We have 10 tests per length. For a clean line plot, we must average them.
# We group by 'PlaintextLength' and calculate the mean for Entropy and Avalanche.
print(f"Reading and aggregating all 10,000 data points from '{CSV_FILENAME}'...")
grouped_data = df.groupby('PlaintextLength')[['Entropy', 'Avalanche']].mean()
print("Data aggregation complete.")

# Dynamically find the max length for the X-axis
max_length = grouped_data.index.max()
# Create X-axis ticks every 50, as you requested
x_ticks = np.arange(0, max_length + 1, 50) 

# Use a clean, professional style for the graphs
plt.style.use('seaborn-v0_8-whitegrid')

# --- Graph 1: Entropy vs. Plaintext Length ---
print(f"Generating '{ENTROPY_GRAPH_FILE}'...")
plt.figure(figsize=(12, 7)) # Create a new figure
plt.plot(grouped_data.index, grouped_data['Entropy'], linestyle='-', marker='.', markersize=2, label='Average Entropy')

# Add M.Tech-level titles and labels
plt.title('Analysis of Cipher Entropy', fontsize=16, loc='left')
plt.suptitle('Average Entropy (bits/byte) vs. Plaintext Length', fontsize=18, fontweight='bold', y=0.96)
plt.xlabel('Plaintext Length (bytes)', fontsize=12)
plt.ylabel('Average Entropy (bits/byte)', fontsize=12)

# Set X-axis grid interval to 50, as requested
plt.xticks(x_ticks, rotation=45)
plt.xlim(0, max_length) # Set X-axis limit
    
# Set Y-axis grid to automatic, as requested
plt.yticks()
plt.ylim(0, 8.1) # Max entropy is 8, so 8.1 is a good limit
plt.grid(True, linestyle='--', alpha=0.6) # Turn on both grids
plt.legend()
plt.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout to fit suptitle
    
plt.savefig(ENTROPY_GRAPH_FILE)
plt.close() # Close the figure to start fresh for the next graph

# --- Graph 2: Avalanche Effect vs. Plaintext Length ---
print(f"Generating '{AVALANCHE_GRAPH_FILE}'...")
plt.figure(figsize=(12, 7)) # Create a new figure
plt.plot(grouped_data.index, grouped_data['Avalanche'], linestyle='-', marker='.', markersize=2, label='Average Avalanche %', color='crimson')

# Add M.Tech-level titles and labels
plt.title('Analysis of Cipher Diffusion (Avalanche Effect)', fontsize=16, loc='left')
plt.suptitle('Average Avalanche Effect (%) vs. Plaintext Length', fontsize=18, fontweight='bold', y=0.96)
plt.xlabel('Plaintext Length (bytes)', fontsize=12)
plt.ylabel('Average Avalanche Effect (%)', fontsize=12)

# Add a reference line for the "ideal" 50% avalanche
plt.axhline(y=50, color='gray', linestyle=':', linewidth=2, label='Ideal 50% Diffusion')
    
# Set X-axis grid interval to 50, as requested
plt.xticks(x_ticks, rotation=45)
plt.xlim(0, max_length)
    
# Set Y-axis grid to automatic, but set a sensible limit
plt.yticks()
plt.ylim(0, 100) # Avalanche is a percentage
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend()
plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
plt.savefig(AVALANCHE_GRAPH_FILE)
plt.close()

print("\nDone. Graphs saved as:")
print(f"- {ENTROPY_GRAPH_FILE}")
print(f"- {AVALANCHE_GRAPH_FILE}")