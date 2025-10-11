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
def emulator():
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

    csr = tbs(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]));
    # print_csr(csr) # uncomment to print out csr
