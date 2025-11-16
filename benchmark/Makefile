# --- Variables ---

# Compiler
CC = gcc

# Compiler flags
# -DCPU_SIM is from your command
# -Wall -Wextra -g are standard flags for warnings and debugging
CFLAGS = -DCPU_SIM -Wall -Wextra -g

# Linker flags
LDFLAGS = -lm

# List of all your source code files
SRCS = cpu_sim/main.c cpu_sim/kernel_run.c kernels/graphics_lib.c \
       kernels/vertexShader.c kernels/triangle.c kernels/pixel.c

# The name of the executable to create
TARGET = a.out

# --- Targets ---

# The default target: build and convert everything
# This is the first target, so it runs when you just type "make"
all: output.png

# Target to just compile and run the program
run: frame0.ppm

# Rule to compile (link) the executable
# It depends on all your source files
$(TARGET): $(SRCS)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRCS) $(LDFLAGS)

# Rule to create the PPM file
# It depends on the executable (it must be built first)
frame0.ppm: $(TARGET)
	./$(TARGET)

# Rule to convert the PPM to PNG
# It depends on the PPM file (it must be created first)
output.png: frame0.ppm
	ffmpeg -y -loglevel error -i frame0.ppm output.png

# Rule to clean up all generated files
clean:
	rm -f $(TARGET) frame0.ppm output.png

# Tell 'make' that 'all', 'run', and 'clean' are not files
.PHONY: all run clean