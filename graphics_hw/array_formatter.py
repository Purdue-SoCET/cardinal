#helper script to convert files from Aiden into form that tmu can read

import numpy as np
import re



with open("pixeldebug_UV.txt") as file:
    lines = file.readlines()[1:-1]


pattern = r"S:([+-]?\d+\.\d+).*?T:([+-]?\d+\.\d+)"

out = np.zeros(shape = (800,800,2))
for col in range(800):
    for row in range(800):
        match = re.search(pattern, lines[(row * 800) + col])
        u = float(match.group(1))
        v = float(match.group(2))
        out[row][col] = [u,v]

np.save('teapot', out)







