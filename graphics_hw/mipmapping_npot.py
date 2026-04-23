"""Utility for handling non-power-of-two texture mipmap generation.

This module provides basic classes and functions that take an input texture
image and produce an array of downsampled textures (mip levels). It serves
as a minimal template; actual image processing logic can be filled in later.
"""

from __future__ import annotations

import os
from typing import List, Tuple, Union

import numpy as np
from PIL import Image


class MipMapGenerator:
    """Create an array of mipmap levels from a source image array.

    The constructor accepts either a NumPy array or a PIL Image object (or
    path string for convenience). The wrapper class from earlier versions was
    removed for simplicity.
    """

    def __init__(self, source: Union[str, np.ndarray, Image.Image]) -> None:
        if isinstance(source, str):
            with Image.open(source) as img:
                self.base_image = np.array(img)
        elif isinstance(source, Image.Image):
            self.base_image = np.array(source)
        else:
            # assume numpy array
            self.base_image = source
        self.levels: List[np.ndarray] = []

    def generate(self) -> List[np.ndarray]:
        """Generate mipmap levels for the base image.

        Returns a list of NumPy arrays starting with the original image.
        """
        # placeholder logic: simply add the base image
        self.levels = [self.base_image]
        # actual downsampling code should be implemented here
        return self.levels

    def save_levels(self, directory: str) -> None:
        """Write each mip level to the specified directory."""
        os.makedirs(directory, exist_ok=True)
        for idx, level in enumerate(self.levels):
            img = Image.fromarray(level)
            filename = os.path.join(directory, f"mip_{idx}.png")
            img.save(filename)


def create_texture_array(input_path: str, output_dir: str) -> List[np.ndarray]:
    """High-level convenience function to produce and save mipmap levels.

    Args:
        input_path: Path to the source texture image.
        output_dir: Directory where generated images will be stored.

    Returns:
        List of NumPy arrays representing each mip level.
    """
    generator = MipMapGenerator(input_path)
    levels = generator.generate()
    generator.save_levels(output_dir)
    return levels


if __name__ == "__main__":
    # simple demonstration when run as a script
    import argparse

    parser = argparse.ArgumentParser(description="Generate mipmap array from a texture.")
    parser.add_argument("input", help="Path to input texture.")
    parser.add_argument("output", help="Directory to store mip levels.")
    args = parser.parse_args()

    create_texture_array(args.input, args.output)
