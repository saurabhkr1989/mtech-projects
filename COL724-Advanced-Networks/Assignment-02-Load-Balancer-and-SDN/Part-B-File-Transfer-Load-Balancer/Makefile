# Compiler and flags
CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -pthread -g
LDFLAGS = -pthread

# --- DIRECTORIES ---
# Source, Include, Object, and Binary directories
SRC_DIR = src
INC_DIR = include
OBJ_DIR = obj
BIN_DIR = .

# --- SOURCES ---
# Find all .cpp files in the source directory
SOURCES = $(wildcard $(SRC_DIR)/*.cpp)
# Create a list of object files in the object directory
OBJECTS = $(patsubst $(SRC_DIR)/%.cpp,$(OBJ_DIR)/%.o,$(SOURCES))

# --- EXECUTABLES ---
# Define the final executable names
LB_EXEC = $(BIN_DIR)/load_balancer
SERVER_EXEC = $(BIN_DIR)/server
CLIENT_EXEC = $(BIN_DIR)/client

# --- FLAGS ---
# Add the include directory to the compiler flags
CXXFLAGS += -I$(INC_DIR)

# --- TARGETS ---

# Default target: build all executables
all: $(LB_EXEC) $(SERVER_EXEC) $(CLIENT_EXEC)

# Rule to link the load_balancer executable
$(LB_EXEC): $(OBJ_DIR)/load_balancer.o
	@echo "Linking $@..."
	@$(CXX) $(LDFLAGS) -o $@ $^

# Rule to link the server executable
$(SERVER_EXEC): $(OBJ_DIR)/server.o
	@echo "Linking $@..."
	@$(CXX) $(LDFLAGS) -o $@ $^

# Rule to link the client executable
$(CLIENT_EXEC): $(OBJ_DIR)/client.o
	@echo "Linking $@..."
	@$(CXX) $(LDFLAGS) -o $@ $^

# Pattern rule to compile .cpp files into .o object files
# It also creates the object directory if it doesn't exist
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.cpp | $(OBJ_DIR)
	@echo "Compiling $<..."
	@$(CXX) $(CXXFLAGS) -c -o $@ $<

# Rule to create the object directory
$(OBJ_DIR):
	@mkdir -p $(OBJ_DIR)

# Clean up build artifacts and created directories
clean:
	@echo "Cleaning up..."
	@rm -rf $(OBJ_DIR)
	@rm -f $(LB_EXEC) $(SERVER_EXEC) $(CLIENT_EXEC)
	@rm -f *.o *.log *.csv
	@rm -rf ./server*_files ./client_data

# Phony targets
.PHONY: all clean

