from __future__ import annotations

import os

import numpy as np
from PIL import Image

class MipMapGenerator:
    #Generate an array of mip maps from single source image
    def __init__(self, texture_path):
        img = Image.open(texture_path).convert('RGB')
        self.base_tex = np.array(img)
        self.levels: List[np.ndarray] = []

    def generate_maps(self, level):
        ''' TODO : implement handling for skinny images, to keep downsampling until reaching 1x1'''

        if(len(self.levels[level]) <= 1 | len(self.levels[level][0]) <= 1) :
            return

        #define current level
        tex_map = self.levels[level]
        child_rows = len(tex_map) // 2
        child_cols= len(tex_map[0]) // 2
        child_mip = np.zeros((child_rows, child_cols, 3))

        #iterate through pixels of successor
        for row in range(child_rows):
            for col in range(child_cols):
                #parent texels
                P00 = tex_map[2 * row][2 * col]
                P01 = tex_map[2 * row][2 * col + 1]
                P10 = tex_map[2 * row + 1][2 * col]
                P11 = tex_map[2 * row + 1][2 * col + 1]

                #weighted average
                child_mip[row][col] = (P00.astype(int) + P01.astype(int) + P10.astype(int) + P11.astype(int)) // 4 #division by 4 is right shift by 2 in hardware

        level += 1
        self.levels.append(child_mip)
        self.generate_maps(level)

    def generate(self, level = 0) -> List[np.ndarray]:
        self.levels = [self.base_tex]
        self.generate_maps(level)
        return self.levels

    def save_levels(self, directory:str) -> None:
        os.makedirs(directory, exist_ok = True)
        for idx, level in enumerate(self.levels):
            img = Image.fromarray(level.astype(np.uint8))
            filename = os.path.join(directory, f"mip_{idx}.png")
            img.save(filename)
        
def create_texture_array(input_path:str, output_dir: str) -> List[np.ndarray]:
    generator = MipMapGenerator(input_path)
    levels = generator.generate()
    generator.save_levels(output_dir)
    return levels

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate mipmap array from a texture.")
    parser.add_argument("input", help="Path to input texture.")
    parser.add_argument("output", help="Directory to store mip levels")
    args = parser.parse_args()

    create_texture_array(args.input, args.output)