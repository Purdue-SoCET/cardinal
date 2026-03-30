from jinja2 import Environment, FileSystemLoader
import sys
import yaml
import os

if len(sys.argv) < 2:
    print("Usage: python gen.py <kernel_name>")
    sys.exit(1)

kernel_name = sys.argv[1] 

try:
    with open(f"yaml_structs/{kernel_name}.yaml", "r") as f:
        struct_data = yaml.safe_load(f)
except FileNotFoundError:
    print(f"Error: YAML file for kernel '{kernel_name}' not found in 'yaml_structs/' directory.")
    sys.exit(1)

data = {
    "kernel_name": kernel_name,
    "structs": struct_data.get('structs', [])
}

env = Environment(loader=FileSystemLoader('jinja2/templates'))

template = env.get_template('main.c.jt2') 
output_filename = f"cpu_sim/main_{kernel_name}.c"
with open(output_filename, "w") as f:
    f.write(template.render(data))

template = env.get_template('header.h.jt2') 
output_filename = f"kernels/include/{kernel_name}.h"
with open(output_filename, "w") as f:
    f.write(template.render(data))

template = env.get_template('kernel.c.jt2') 
output_filename = f"kernels/{kernel_name}.c"
with open(output_filename, "w") as f:
    f.write(template.render(data))

print(f"Successfully built {output_filename}")