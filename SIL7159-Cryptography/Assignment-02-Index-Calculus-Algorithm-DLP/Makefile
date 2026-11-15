CXX = mpicxx
CXXFLAGS = -O2 -std=c++11
LDLIBS = -lgmp

SRC = main.cpp
OBJ = $(SRC:.cpp=.o)
TARGET = index_calculus_solver

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJ)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDLIBS)
	@echo " built: $(TARGET) "

# compile rules (explicit)
%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# convenience run
run: $(TARGET)
	@echo "running (use mpirun -np .. if needed) ..."
	@./$(TARGET) --help || true

clean:
	@rm -f $(OBJ) $(TARGET)
	@echo "cleaned up"