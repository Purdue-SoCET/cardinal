# --- Variables ---

# CPU Compiler and flags
CPU_CC = gcc
CPU_CFLAGS = -DCPU_SIM -Wall -Wextra -g
CPU_LDFLAGS = -lm

GPU_CC = python3 ../../gpu-ppci-compiler/compile_twig.py
GPU_CFLAGS = 

# CPU files
CPU_SRCS = cpu_sim/main.c cpu_sim/kernel_run.c cpu_sim/graphics_lib.c \
       kernels/vertexShader.c kernels/triangle.c kernels/pixel.c
CPU_TARGET = cpu_sim.out
CPU_PPM = frame_000.ppm

CPU_BUILD_DIR = build/
CPU_OUTPUT_DIR = $(CPU_BUILD_DIR)output/

# GPU files
GPU_LIB_SRCS = 
GPU_LIB_EXCLUDE = kernels/graphics_lib.c
GPU_KERNEL_SRCS = $(filter-out $(GPU_LIB_EXCLUDE), $(wildcard kernels/*.c))
GPU_OUTPUT_DIR = compiled/
GPU_TARGETS = $(patsubst kernels/%.c, $(GPU_OUTPUT_DIR)%.asm, $(GPU_KERNEL_SRCS))

# --- Targets ---

# Default
all: output.png

run: $(CPU_PPM)

# Compiles all found kernels
gpu_all: $(GPU_TARGETS)

$(CPU_TARGET): $(SRCS)
 	# Make build dir if it does not exist
	mkdir -p $(CPU_BUILD_DIR)
	mkdir -p $(CPU_OUTPUT_DIR)
	$(CPU_CC) $(CPU_CFLAGS) -o $(CPU_BUILD_DIR)$(CPU_TARGET) $(CPU_SRCS) $(CPU_LDFLAGS)

$(CPU_PPM): $(CPU_TARGET)
	./$(CPU_BUILD_DIR)$(CPU_TARGET)

output.png: $(CPU_PPM)
	ffmpeg -y -loglevel error -i $(CPU_OUTPUT_DIR)$(CPU_PPM) $(CPU_BUILD_DIR)output.png

# Rule to clean up all generated files
clean:
	rm -rf $(CPU_BUILD_DIR)*


# Pattern rule: How to build 'compiled/X.asm' from 'kernels/X.c' + 'graphics_lib.c'
$(GPU_OUTPUT_DIR)%.asm: kernels/%.c $(GPU_LIB_SRC)
	mkdir -p $(GPU_OUTPUT_DIR)
	$(GPU_CC) $(GPU_CFLAGS) $^
	mv kernels/*.ir $(GPU_OUTPUT_DIR)
	mv kernels/*.s $(GPU_OUTPUT_DIR)

# Tell 'make' that 'all', 'run', and 'clean' are not files
.PHONY: all run clean