# =======================================================
# TIMELY Congestion Control Simulator - Final Makefile
# ==========================================================

CXX = g++
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra
LDFLAGS =
SRC = main.cpp simulator.cpp timely.cpp dctcp.cpp utils.cpp
OBJ = $(SRC:.cpp=.o)
TARGET = timely_sim

YELLOW=\033[33;1m
GREEN=\033[32;1m
RESET=\033[0m

# ==========================================================
# Compilation Rules
# ========================================================

all: $(TARGET)
	@echo "$(GREEN)Build complete: $(TARGET)$(RESET)"

$(TARGET): $(OBJ)
	@echo "$(YELLOW)Linking...$(RESET)"
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJ) $(LDFLAGS)

%.o: %.cpp
	@echo "$(YELLOW)Compiling $< ...$(RESET)"
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	@echo "$(YELLOW)Cleaning object files...$(RESET)"
	rm -f $(OBJ)

reset:
	@echo "$(YELLOW)Resetting all output directories and executable...$(RESET)"
	rm -rf output
	rm -f $(OBJ) $(TARGET)

run: $(TARGET)
	@echo "$(GREEN)Launching simulator UI...$(RESET)"
	./$(TARGET)

# =========================================================
# Automated experiment pipeline (runs all experiments)
# ==========================================================

DATE := $(shell date +%Y%m%d_%H%M%S)
RUN_DIR := output/runs/$(DATE)

auto: $(TARGET)
	@echo "$(GREEN)=== Running All 6 TIMELY Experiments Automatically ===$(RESET)"
	@mkdir -p $(RUN_DIR)
	@for exp in 1 2 3 4 5 6; do \
		echo "$(YELLOW)[*] Running Experiment $$exp ...$(RESET)"; \
		mkdir -p $(RUN_DIR)/Exp$$exp; \
		printf "$$exp\n5\n40\nd\n3\n0\n0\nn\n8\n" | ./$(TARGET) > $(RUN_DIR)/Exp$$exp/run.log 2>&1; \
		cp -r output/csv $(RUN_DIR)/Exp$$exp/ 2>/dev/null || true; \
		cp -r output/graphs $(RUN_DIR)/Exp$$exp/ 2>/dev/null || true; \
	done
	@echo "$(GREEN)=== All Experiments Complete ===$(RESET)"
	@echo "Results archived under $(RUN_DIR)/Exp*/"
