import sys
from pathlib import Path

# print csr helper
def print_csr(csr):
    for i in range(len(csr["x"])):
        print(f"lane {i:2d}: (z={csr['z'][i]}, y={csr['y'][i]}, x={csr['x'][i]})")


# thread block scheduler
def tbs(x, y, z):
    blocksize = x*y*z

    if blocksize > 32:
        print("fuck you 3")
        sys.exit(1)

    csr = {"x": [i % x for i in range(blocksize)], "y": [(i // x) % y for i in range(blocksize)], "z": [i // (x * y) for i in range(blocksize)]}
    return csr

# actual emulator
def emulator(csr, regfile, input_file, mem):
    # PC IS NOT IMPLEMENTED CURRENTLY ALL, JUMP AND LINK HAS NO FUNCTIONALITY YET
    with input_file.open("r") as f:
    
        while(line := f.readline()):
            line = line.strip()
            instr_type = int(line[0:3], 2) # bits 31:29
            funct = int(line[3:7], 2) # bits 28:25

            match instr_type:
                case 0b000:
                    print("rtype")  

    return

# main function
if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("fuck u lol")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print("fuck u again lol")
        sys.exit(1)

    csr = tbs(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    regfile = [[0 for i in range(32)] for j in range(32)]

    # print_csr(csr) # uncomment to print out csr
