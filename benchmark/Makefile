# --- Variables ---

# CPU Compiler and flags
CPU_CC = gcc
CPU_CFLAGS = -DCPU_SIM -Wall -Wextra -g -lm -I ./cpu_sim/include
CPU_LDFLAGS = -lm
CPU_32BIT_FLAGS = -m32 -fsingle-precision-constant -Wdouble-promotion

GPU_CC = python3 ../../gpu-ppci-compiler/compile_twig.py
GPU_CFLAGS = 

# CPU files
KERNEL ?= saxpy
CPU_SRCS = cpu_sim/main_new.c cpu_sim/kernel_run.c cpu_sim/graphics_lib.c cpu_sim/shader_memdump.c \
       kernels/vertex.c kernels/triangle.c kernels/pixel.c kernels/post.c kernels/vertexShader.c kernels/blend.c
CPU_TARGET = cpu_sim.out
CPU_PPM = frame_000.ppm

CUSTOM_SRCS = cpu_sim/main_$(KERNEL).c cpu_sim/kernel_run.c kernels/$(KERNEL).c cpu_sim/shader_memdump.c

CPU_BUILD_DIR = build/
CPU_OUTPUT_DIR = $(CPU_BUILD_DIR)output/
CPU_MEM_DUMP_DIR = $(CPU_BUILD_DIR)mem_dump/

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

run32: #need gcc-multilib
	mkdir -p $(CPU_BUILD_DIR) $(CPU_OUTPUT_DIR) $(CPU_MEM_DUMP_DIR) build/threads
	$(CPU_CC) $(CPU_CFLAGS) $(CPU_32BIT_FLAGS) -o $(CPU_BUILD_DIR)$(CPU_TARGET) $(CPU_SRCS) $(CPU_LDFLAGS)
	./$(CPU_BUILD_DIR)$(CPU_TARGET)

run32_dump: #need gcc-multilib
	twig kernels/vertex.c --bin-output compiled/vertex.bin -O2 --entry kernel_vertex -DGPU_SIM
	twig kernels/triangle.c --bin-output compiled/triangle.bin -O2 --entry kernel_triangle -DGPU_SIM
	twig kernels/pixel.c --bin-output compiled/pixel.bin -O2 --entry kernel_pixel -DGPU_SIM
	mkdir -p $(CPU_BUILD_DIR) $(CPU_OUTPUT_DIR) $(CPU_MEM_DUMP_DIR) build/threads
	$(CPU_CC) $(CPU_CFLAGS) $(CPU_32BIT_FLAGS) -o $(CPU_BUILD_DIR)$(CPU_TARGET) $(CPU_SRCS) $(CPU_LDFLAGS)
	./$(CPU_BUILD_DIR)$(CPU_TARGET)
	python cpu_sim/data/stitch_data.py \
	--big_endian False \
	build/threads/vertexThreads.txt \
	build/threads/triangleThreads.txt \
	build/threads/pixelThreads.txt

run32_dump_em: #need gcc-multilib
	twig kernels/vertex.c --bin-output compiled/vertex.bin -O2 --entry kernel_vertex -DGPU_SIM
	twig kernels/triangle.c --bin-output compiled/triangle.bin -O2 --entry kernel_triangle -DGPU_SIM
	twig kernels/pixel.c --bin-output compiled/pixel.bin -O2 --entry kernel_pixel -DGPU_SIM
	mkdir -p $(CPU_BUILD_DIR) $(CPU_OUTPUT_DIR) $(CPU_MEM_DUMP_DIR) build/threads
	$(CPU_CC) $(CPU_CFLAGS) $(CPU_32BIT_FLAGS) -o $(CPU_BUILD_DIR)$(CPU_TARGET) $(CPU_SRCS) $(CPU_LDFLAGS)
	./$(CPU_BUILD_DIR)$(CPU_TARGET)
	python cpu_sim/data/stitch_data.py \
	--big_endian True \
	build/threads/vertexThreads.txt \
	build/threads/triangleThreads.txt \
	build/threads/pixelThreads.txt

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

new_custom:
	python jinja2/generate.py $(KERNEL)

custom: 
	$(CPU_CC) $(CPU_CFLAGS) -o $(CPU_BUILD_DIR)$(KERNEL) $(CUSTOM_SRCS) $(CPU_LDFLAGS)
	./$(CPU_BUILD_DIR)/$(KERNEL)

custom32: 
	$(CPU_CC) $(CPU_CFLAGS) $(CPU_32BIT_FLAGS) -o $(CPU_BUILD_DIR)$(KERNEL) $(CUSTOM_SRCS) $(CPU_LDFLAGS)
	./$(CPU_BUILD_DIR)/$(KERNEL)

custom32_dump: 
	twig kernels/$(KERNEL).c --bin-output compiled/$(KERNEL).bin -O2 --entry kernel_$(KERNEL) -DGPU_SIM
	mkdir -p $(CPU_BUILD_DIR) $(CPU_OUTPUT_DIR) $(CPU_MEM_DUMP_DIR) build/threads
	$(CPU_CC) $(CPU_CFLAGS) $(CPU_32BIT_FLAGS) -o $(CPU_BUILD_DIR)$(KERNEL) $(CUSTOM_SRCS) $(CPU_LDFLAGS)
	./$(CPU_BUILD_DIR)/$(KERNEL)
	python cpu_sim/data/stitch_data_compute.py $(KERNEL) build/threads/$(KERNEL)Threads.txt

# Pattern rule: How to build 'compiled/X.asm' from 'kernels/X.c' + 'graphics_lib.c'
$(GPU_OUTPUT_DIR)%.asm: kernels/%.c $(GPU_LIB_SRC)
	mkdir -p $(GPU_OUTPUT_DIR)
	$(GPU_CC) $(GPU_CFLAGS) $^
	mv kernels/*.ir $(GPU_OUTPUT_DIR)
	mv kernels/*.s $(GPU_OUTPUT_DIR)

# Lighting workload
LIGHTING_SRCS = cpu_sim/lighting_main.c cpu_sim/kernel_run.c cpu_sim/graphics_lib.c \
       kernels/vertexShader.c kernels/triangle.c kernels/pixel.c

lighting:
	mkdir -p $(CPU_BUILD_DIR) $(CPU_OUTPUT_DIR)
	$(CPU_CC) $(CPU_CFLAGS) -o $(CPU_BUILD_DIR)lighting_sim.out $(LIGHTING_SRCS) $(CPU_LDFLAGS)
	./$(CPU_BUILD_DIR)lighting_sim.out

# Tell 'make' that 'all', 'run', 'clean', and 'lighting' are not files
.PHONY: all run clean lighting