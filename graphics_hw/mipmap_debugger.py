import os
from PIL import Image


def generate_debug_mipmaps(texture_name="debug_colors", base_size=512):
    """
    Generates a series of solid-color mipmap images halving in size each level.
    Saves them to the directory structure expected by the renderer.
    """
    # Create the folder structure (e.g., "textures/debug_colors/")
    tex_dir = os.path.join("textures/textures", texture_name)
    os.makedirs(tex_dir, exist_ok=True)

    # A list of highly distinct, high-contrast RGB colors for easy visual debugging
    colors = [
        (255, 0, 0),  # LOD 0: Red       (Base resolution)
        (0, 255, 0),  # LOD 1: Green     (Half size)
        (0, 0, 255),  # LOD 2: Blue      (Quarter size)
        (255, 255, 0),  # LOD 3: Yellow    (Eighth size)
        (0, 255, 255),  # LOD 4: Cyan
        (255, 0, 255),  # LOD 5: Magenta
        (255, 128, 0),  # LOD 6: Orange
        (128, 0, 128),  # LOD 7: Purple
        (0, 128, 255),  # LOD 8: Light Blue
        (255, 255, 255)  # LOD 9: White
    ]

    size = base_size
    mip_level = 0

    # Loop until the image size shrinks down to 1x1 pixel
    while size >= 1:
        # Grab the color for this level (cycles if we run out of colors)
        color = colors[mip_level % len(colors)]

        # Create a new solid color image
        img = Image.new('RGB', (size, size), color)

        # Save it to the expected filename format
        filepath = os.path.join(tex_dir, f"mip_{mip_level}.png")
        img.save(filepath)

        print(f"Created {filepath} - Size: {size}x{size}")

        # Divide the dimension by 2 for the next mipmap level
        size //= 2
        mip_level += 1


# Run the function to generate a 512x512 debug texture chain
if __name__ == "__main__":
    generate_debug_mipmaps("debug_colors", 512)