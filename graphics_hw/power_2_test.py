import math
import numpy as np
from PIL import Image

from power_2_mipmap import power2_mipmaps

# Return smallest power of 2 that is >= n
def next_pow2(n):
    power = 1

    while power < n:
        power = power * 2

    return power


def resize_to_pot(img):
    #current width, height
    width = img.size[0]
    height = img.size[1]


    #find next pot sizes
    new_width = next_pow2(width)
    new_height = next_pow2(height)

    #if already pot, return original
    if new_width == width and new_height == height:
        return img

    # resize
    resized_img = img.resize((new_width, new_height), Image.BILINEAR)

    return resized_img


def main():
    in_path = "IMG_7501.png"

    img = Image.open(in_path).convert("RGB")
    print("original size (W,H):", img.size)

    #resize to pow of 2
    img_pot = resize_to_pot(img)
    print("POT size (W,H):", img_pot.size)

    img_pot.save("IMG_7501_pot.png")

    #convert to float text [0,1]
    texture = np.asarray(img_pot).astype(np.float32) / 255.0
    print("Texture array shape (H,W,C):", texture.shape)

    # mipmaps
    mipmaps = power2_mipmaps(texture)
    print("Mip levels:", len(mipmaps))
    for i, mip in enumerate(mipmaps):
        print(f"  Level {i}: {mip.shape[1]}x{mip.shape[0]}")  # W x H

    #save each mip level to files
    for i, mip in enumerate(mipmaps):
        out = np.clip(np.rint(mip * 255.0), 0, 255).astype(np.uint8)
        Image.fromarray(out, mode="RGB").save(f"mip_level_{i}.png")



if __name__ == "__main__":
    main()
