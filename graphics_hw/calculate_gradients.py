import numpy as np


def process_tmu_quads(texture_ids, uv_coords):
    """
    Simulates quad dispatch and gradient calculation for a TMU.
    Handles matrices of any n x m size by padding edges to complete 2x2 quads.

    Parameters:
    texture_ids : np.ndarray
        (n, m) matrix of texture IDs. -1 indicates untextured/helper lanes.
    uv_coords : np.ndarray
        (n, m, 2) matrix of (u, v) floats.

    Returns:
    dict containing gradients, execution masks, and quad texture assignments.
    """
    n, m = texture_ids.shape

    # 1. Calculate padding needed to align to 2x2 quads
    pad_n = n % 2
    pad_m = m % 2

    # 2. Pad arrays if dimensions are odd
    if pad_n > 0 or pad_m > 0:
        # Pad texture IDs with -1 (helper lanes) on the bottom and/or right
        texture_ids = np.pad(
            texture_ids,
            pad_width=((0, pad_n), (0, pad_m)),
            mode='constant',
            constant_values=-1
        )

        # Pad UVs by repeating the edge values. This ensures the derivative
        # (gradient) across the padded helper lane evaluates to 0, remaining stable.
        uv_coords = np.pad(
            uv_coords,
            pad_width=((0, pad_n), (0, pad_m), (0, 0)),
            mode='edge'
        )

    # 3. Extract the four pixels of each 2x2 quad using array slicing
    tl_uv = uv_coords[0::2, 0::2, :]  # Top-Left
    tr_uv = uv_coords[0::2, 1::2, :]  # Top-Right
    bl_uv = uv_coords[1::2, 0::2, :]  # Bottom-Left

    tl_tex = texture_ids[0::2, 0::2]
    tr_tex = texture_ids[0::2, 1::2]
    bl_tex = texture_ids[1::2, 0::2]
    br_tex = texture_ids[1::2, 1::2]

    # 4. Calculate Gradients (Implicit Derivatives)
    dfdx = tr_uv - tl_uv
    dfdy = bl_uv - tl_uv

    # 5. Generate the Execution Mask
    exec_mask_tl = tl_tex != -1
    exec_mask_tr = tr_tex != -1
    exec_mask_bl = bl_tex != -1
    exec_mask_br = br_tex != -1

    # 6. Group data by quad for the TMU pipeline
    quad_data = {
        "dfdx": dfdx,
        "dfdy": dfdy,
        "texture_ids": np.stack([tl_tex, tr_tex, bl_tex, br_tex], axis=-1),
        "execution_mask": np.stack([exec_mask_tl, exec_mask_tr, exec_mask_bl, exec_mask_br], axis=-1)
    }

    return quad_data


# --- Example Usage with an Odd 3x3 Matrix ---
n, m = 3, 3
mock_texture_ids = np.array([
    [1, 1, 2],
    [1, 1, 2],
    [3, 3, 3]
])

mock_uv_coords = np.random.rand(n, m, 2)

tmu_output = process_tmu_quads(mock_texture_ids, mock_uv_coords)

# The 3x3 input requires padding to 4x4, resulting in a 2x2 grid of quads.
print("Output Grid Shape (Quads):", tmu_output["execution_mask"].shape[:2])

# Check the bottom-right quad (index 1, 1).
# It should only have one active pixel (Top-Left) from the original 3x3 matrix.
print("\nExecution Mask for Bottom-Right Quad (1,1):\n", tmu_output["execution_mask"][1, 1])
print("Should be: [True, False, False, False]")