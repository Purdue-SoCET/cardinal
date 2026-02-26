import numpy as np


def _is_power_of_two(n):
    if n <= 0:
        return False
    return (n & (n - 1)) == 0


def power2_mipmaps(texture):
    #current shape = (H, W, 3)

    current = texture.astype(np.float32)
    mipmaps = [current]
    next_level = 0

    while True:
        h, w, c = current.shape

        # stop at 1x1
        if h == 1 and w == 1:
            break

        #1: normal (2x2 box filter)
        if h > 1 and w > 1:
            top_left = current[0::2, 0::2, :]
            top_right = current[0::2, 1::2, :]
            bottom_left = current[1::2, 0::2, :]
            bottom_right = current[1::2, 1::2, :]

            next_level = (top_left + top_right + bottom_left + bottom_right) / 4.0

        #2: height is 1, sample only width
        elif h == 1 and w > 1:
            left = current[:, 0::2, :]
            right = current[:, 1::2, :]
            next_level = (left + right) / 2.0

        #3: width is 1, sample only height
        elif w == 1 and h > 1:
            top = current[0::2, :, :]
            bottom = current[1::2, :, :]
            next_level = (top + bottom) / 2.0

        mipmaps.append(next_level)
        current = next_level

    return mipmaps
