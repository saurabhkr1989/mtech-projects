#!/bin/bash

# --- Configuration ---
EXECUTABLE="./hybrid_encrypt"
KEY_FILE="key.txt"
CSV_FILE="analysis_results_raw.csv"  # New file for raw data
MAX_LENGTH=1000
NUM_TESTS=10
TEMP_INPUT_FILE="temp_analysis_input.txt"
# --- End Configuration ---

# Check if the executable exists
if [ ! -f "$EXECUTABLE" ]; then
    echo "Error: Executable '$EXECUTABLE' not found."
    echo "Please compile your code first (e.g., g++ *.cpp -o hybrid_encrypt -std=c++17)"
    exit 1
fi

# Check if the key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo "Error: Key file '$KEY_FILE' not found."
    exit 1
fi

# Read the single master key
MASTER_KEY=$(cat $KEY_FILE)
echo "Using Master Key: ${MASTER_KEY:0:10}..."

# Write the new header to the CSV file for raw data
echo "Serial_No,PlaintextLength,Test_No,Entropy,Avalanche" > $CSV_FILE

echo "Starting analysis loop: 1-to-$MAX_LENGTH lengths, $NUM_TESTS tests per length."
echo "This will run $(($MAX_LENGTH * $NUM_TESTS)) total tests and save all raw data."

# Initialize a total serial number counter
SERIAL_NO=1

# --- Main Analysis Loop (Outer) ---
for (( len=1; len<=$MAX_LENGTH; len++ )); do
    
    # --- Inner Loop (10 Tests) ---
    for (( test=1; test<=$NUM_TESTS; test++ )); do
        
        echo -ne "Processing: Length $len/$MAX_LENGTH, Test $test/$NUM_TESTS  (Total: $SERIAL_NO)  \r"
        
        # 1. Generate RANDOM alphanumeric plaintext of length 'len'
        CURRENT_PLAINTEXT=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c $len)
        
        # 2. Create the temporary input file
        echo "$MASTER_KEY" > $TEMP_INPUT_FILE
        echo "$CURRENT_PLAINTEXT" >> $TEMP_INPUT_FILE
        
        # 3. Run the C++ program and capture ALL standard output
        OUTPUT=$( $EXECUTABLE $TEMP_INPUT_FILE 2>/dev/null ) # Hide C++ output for speed
        
        # 4. Parse the output, strip color codes
        ENTROPY_VAL=$(echo "$OUTPUT" | grep 'Entropy H(X):' | awk '{print $(NF-1)}' | sed 's/\x1b\[[0-9;]*m//g')
        AVALANCHE_VAL=$(echo "$OUTPUT" | grep 'Avalanche Effect A:' | awk '{print $(NF-1)}' | sed 's/\x1b\[[0-9;]*m//g')

        # 5. Handle cases where grep might fail (e.g., on very small files)
        if [ -z "$ENTROPY_VAL" ]; then
            ENTROPY_VAL="0.0"
        fi
        if [ -z "$AVALANCHE_VAL" ]; then
            AVALANCHE_VAL="0.0"
        fi

        # 6. Write the raw data row to our CSV file
        echo "$SERIAL_NO,$len,$test,$ENTROPY_VAL,$AVALANCHE_VAL" >> $CSV_FILE
        
        # 7. Increment the total serial number
        SERIAL_NO=$((SERIAL_NO + 1))
        
    done
    
done

# --- Cleanup ---
rm $TEMP_INPUT_FILE
echo -e "\nAnalysis complete. All 10,000 raw test results saved to $CSV_FILE"