import numpy as np

def process_tmu_quads(texture_ids, uv_coords):
    """
    Calculates dfdx and dfdy for 2x2 quads and returns them mapped
    per-pixel to match the original screen dimensions (n, m, 2).
    """
    n, m = texture_ids.shape

    # 1. Pad arrays if dimensions are odd to complete 2x2 quads
    pad_n = n % 2
    pad_m = m % 2

    if pad_n > 0 or pad_m > 0:
        texture_ids = np.pad(
            texture_ids,
            pad_width=((0, pad_n), (0, pad_m)),
            mode='constant',
            constant_values=-1
        )
        uv_coords = np.pad(
            uv_coords,
            pad_width=((0, pad_n), (0, pad_m), (0, 0)),
            mode='edge'
        )

    # 2. Extract 2x2 quads for UVs and Texture IDs
    tl_uv = uv_coords[0::2, 0::2, :]
    tr_uv = uv_coords[0::2, 1::2, :]
    bl_uv = uv_coords[1::2, 0::2, :]
    br_uv = uv_coords[1::2, 1::2, :]

    tl_id = texture_ids[0::2, 0::2]
    tr_id = texture_ids[0::2, 1::2]
    bl_id = texture_ids[1::2, 0::2]
    br_id = texture_ids[1::2, 1::2]

    # 3. Create boolean masks to check which pixels are valid inside the triangle
    tl_valid = tl_id != -1
    tr_valid = tr_id != -1
    bl_valid = bl_id != -1
    br_valid = br_id != -1

    # Check which rows/columns have BOTH pixels valid to calculate a clean gradient
    top_valid = tl_valid & tr_valid
    bot_valid = bl_valid & br_valid
    left_valid = tl_valid & bl_valid
    right_valid = tr_valid & br_valid

    # 4. Calculate potential gradients for the quad
    dx_top = tr_uv - tl_uv
    dx_bot = br_uv - bl_uv
    dy_left = bl_uv - tl_uv
    dy_right = br_uv - tr_uv

    # Initialize quad gradients to 0 (fallback for isolated valid pixels)
    dfdx_quad = np.zeros_like(dx_top)
    dfdy_quad = np.zeros_like(dy_left)

    # Expand mask dimensions to broadcast against the (u, v) channels
    top_valid_exp = np.expand_dims(top_valid, -1)
    bot_valid_exp = np.expand_dims(bot_valid, -1)
    left_valid_exp = np.expand_dims(left_valid, -1)
    right_valid_exp = np.expand_dims(right_valid, -1)

    # 5. Apply fallback logic to get the final gradient for each quad
    dfdx_quad = np.where(bot_valid_exp, dx_bot, dfdx_quad)
    dfdx_quad = np.where(top_valid_exp, dx_top, dfdx_quad)

    dfdy_quad = np.where(right_valid_exp, dy_right, dfdy_quad)
    dfdy_quad = np.where(left_valid_exp, dy_left, dfdy_quad)

    # 6. Broadcast the quad gradients back out to per-pixel dimensions
    # np.repeat duplicates each row/col, turning a 1x1 into a 2x2
    dfdx_full = np.repeat(np.repeat(dfdx_quad, 2, axis=0), 2, axis=1)
    dfdy_full = np.repeat(np.repeat(dfdy_quad, 2, axis=0), 2, axis=1)

    # 7. Crop the arrays back to the exact original (n, m) shape to remove padding
    dfdx_out = dfdx_full[:n, :m, :]
    dfdy_out = dfdy_full[:n, :m, :]

    return dfdx_out, dfdy_out