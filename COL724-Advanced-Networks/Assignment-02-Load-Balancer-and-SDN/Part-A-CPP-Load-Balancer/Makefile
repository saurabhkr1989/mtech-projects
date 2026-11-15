# Makefile for the project
# its for compiling the server and client

CXX := g++
CXXFLAGS := -std=c++17 -Wall -I./include/
LDFLAGS := -pthread

BUILD_DIR := build
SERVER_EXEC := $(BUILD_DIR)/server
CLIENT_EXEC := $(BUILD_DIR)/client

all: $(BUILD_DIR) $(SERVER_EXEC) $(CLIENT_EXEC)

$(SERVER_EXEC): src/server.cpp
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)
	@echo "Server is built."

$(CLIENT_EXEC): src/client.cpp
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)
	@echo "Client is built."

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

clean:
	@rm -rf $(BUILD_DIR)