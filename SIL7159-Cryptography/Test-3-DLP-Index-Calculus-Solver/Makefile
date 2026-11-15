# Compiler
CXX = mpic++

# Compiler flags
CXXFLAGS = -std=c++11 -Wall -O3

# Libraries
LIBS = -lgmpxx -lgmp

# Target executable
TARGET = index_calculus

# Source files
SOURCES = main.cpp safe_prime.cpp generators.cpp factor_base.cpp relation_collection.cpp linear_algebra.cpp dlp_computation.cpp test_cases.cpp utils.cpp

# Object files
OBJECTS = $(SOURCES:.cpp=.o)

# Default target
all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJECTS) $(LIBS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Clean up
clean:
	rm -f $(TARGET) $(OBJECTS)

.PHONY: all clean

