import struct
import math
import argparse
import numpy as np

# ==========================================
# Memory Map Layout
# ==========================================
ADDR_ARGS_VERT       = 0x20000000 
ADDR_ARGS_TRI        = 0x20000100 
ADDR_ARGS_PIXEL      = 0x20010000 

ADDR_VERTS_IN        = 0x30000000 
ADDR_OA              = 0x30000100 
ADDR_ADIST           = 0x30000110 
ADDR_ALPHAR          = 0x30000120 
ADDR_CAMERA          = 0x30000130 
ADDR_INVTRANS        = 0x30000140 

ADDR_VERTS_TRANS_OUT = 0x40000000 
ADDR_VERTS_2D_OUT    = 0x40000200 
ADDR_TRIS            = 0x40000A00 

ADDR_DEPTH_BUFF      = 0x50000000 
ADDR_TAG_BUFF        = 0x51000000 

ADDR_TEXTURE_COLORS  = 0x60000000 
ADDR_COLOR_OUT       = 0x70000000 

# ==========================================
# Helpers
# ==========================================
def f32(val):
    """Force 32-bit single-precision float representation."""
    return np.float32(val)

def float_to_hex(f):
    packed = struct.pack('>f', float(f)) 
    return f"0x{packed.hex().upper()}"

def int_to_hex(i):
    if i < 0:
        i = (1 << 32) + i
    return f"0x{i:08X}"

def write_line(f_handle, addr, val_str):
    f_handle.write(f"0x{addr:08X} {val_str}\n")

# Vector & Matrix Math (Updated to force 32-bit evaluations)
def cross(v1, v2):
    return [f32(f32(v1[1]*v2[2]) - f32(v1[2]*v2[1])), 
            f32(f32(v1[2]*v2[0]) - f32(v1[0]*v2[2])), 
            f32(f32(v1[0]*v2[1]) - f32(v1[1]*v2[0]))]

def normalize(v):
    mag = np.sqrt(f32(f32(v[0]*v[0]) + f32(v[1]*v[1]) + f32(v[2]*v[2])))
    if mag == 0: return [f32(0.0), f32(0.0), f32(0.0)]
    return [f32(v[0]/mag), f32(v[1]/mag), f32(v[2]/mag)]

def mat_vec_mult(mat, vec):
    return [
        f32(f32(mat[0]*vec[0]) + f32(mat[1]*vec[1]) + f32(mat[2]*vec[2])),
        f32(f32(mat[3]*vec[0]) + f32(mat[4]*vec[1]) + f32(mat[5]*vec[2])),
        f32(f32(mat[6]*vec[0]) + f32(mat[7]*vec[1]) + f32(mat[8]*vec[2]))
    ]

def det3x3(m):
    t1 = f32(f32(m[1][1] * m[2][2]) - f32(m[2][1] * m[1][2]))
    t2 = f32(f32(m[1][0] * m[2][2]) - f32(m[1][2] * m[2][0]))
    t3 = f32(f32(m[1][0] * m[2][1]) - f32(m[1][1] * m[2][0]))
    return f32(f32(m[0][0] * t1) - f32(m[0][1] * t2) + f32(m[0][2] * t3))

def inv3x3(m):
    d = det3x3(m)
    if abs(d) < f32(1e-8): return [f32(0)]*9
    invD = f32(f32(1.0) / d)
    return [
        f32(f32(f32(m[1][1]*m[2][2]) - f32(m[2][1]*m[1][2]))*invD),
        f32(f32(f32(m[0][2]*m[2][1]) - f32(m[0][1]*m[2][2]))*invD),
        f32(f32(f32(m[0][1]*m[1][2]) - f32(m[0][2]*m[1][1]))*invD),
        f32(f32(f32(m[1][2]*m[2][0]) - f32(m[1][0]*m[2][2]))*invD),
        f32(f32(f32(m[0][0]*m[2][2]) - f32(m[0][2]*m[2][0]))*invD),
        f32(f32(f32(m[0][2]*m[1][0]) - f32(m[0][0]*m[1][2]))*invD),
        f32(f32(f32(m[1][0]*m[2][1]) - f32(m[2][0]*m[1][1]))*invD),
        f32(f32(f32(m[0][1]*m[2][0]) - f32(m[0][0]*m[2][1]))*invD),
        f32(f32(f32(m[0][0]*m[1][1]) - f32(m[0][1]*m[1][0]))*invD)
    ]

# ==========================================
# Main Simulation
# ==========================================
def main():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--mode", choices=['vertex', 'triangle', 'pixel', 'pipeline', 'all_tris'], required=True)
    parser.add_argument("--out_init", default="init.hex")
    parser.add_argument("--out_exp", default="expected.hex")
    
    parser.add_argument("--res", type=int, nargs=2, default=[800, 800])
    parser.add_argument("--angle", type=float, default=0.0)
    parser.add_argument("--camera", type=float, nargs=3, default=[0.0, 0.0, 0.0])
    parser.add_argument("--origin", type=float, nargs=3, default=[0.0, 0.0, -30.0])
    parser.add_argument("--axis", type=float, nargs=3, default=[1.0, 1.0, 0.0])
    parser.add_argument("--tri_idx", type=int, default=0)
    
    args = parser.parse_args()

    num_verts = 8
    viewport_w, viewport_h = args.res[0], args.res[1]
    alpha_r = args.angle
    Oa = args.origin
    a_dist = args.axis
    camera = args.camera

    focal_range = 1.0
    abc = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0 * (viewport_h / viewport_w), 0.0],
        [0.0, 0.0, -focal_range * (viewport_h / viewport_w)]
    ])
    abcTranspose = abc.T
    invTrans = inv3x3(abcTranspose.tolist())

    verts_in = [
        [-10, -10, -20, 0, 0], [-10,  10, -20, 0, 1],
        [ 10, -10, -20, 1, 0], [ 10,  10, -20, 1, 1],
        [-10, -10, -40, 0, 1], [-10,  10, -40, 1, 1],
        [ 10, -10, -40, 0, 0], [ 10,  10, -40, 1, 0]
    ]

    tris_map = [
        (0, 1, 2), (3, 1, 2), (1, 3, 5), (7, 3, 5), 
        (0, 2, 4), (6, 2, 4), (4, 5, 6), (7, 5, 6), 
        (0, 1, 4), (5, 1, 4), (2, 3, 6), (7, 3, 6)
    ]

    # Procedural Texture Initialization
    tex_w, tex_h = 64, 64
    texture_arr = []
    for ty in range(tex_h):
        for tx in range(tex_w):
            r = float(tx) / (tex_w - 1)
            g = float(ty) / (tex_h - 1)
            b = 1.0 - r
            texture_arr.append([r, g, b])

    # --- STAGE 1: VERTEX SHADER ---
    verts_trans_out = []
    verts_2d_out = []

    selAxis = [0.0, 0.0, 0.0]
    x2, y2, z2 = a_dist[0]**2, a_dist[1]**2, a_dist[2]**2
    if x2 < y2 and x2 < z2: selAxis[0] = 1.0
    elif y2 < z2: selAxis[1] = 1.0
    else: selAxis[2] = 1.0
    
    lcs_row0 = normalize(cross(selAxis, a_dist))
    lcs_row1 = normalize(a_dist)
    lcs_row2 = normalize(cross(lcs_row0, lcs_row1))
    lcs = lcs_row0 + lcs_row1 + lcs_row2
    lcsInv = [lcs[0], lcs[3], lcs[6], lcs[1], lcs[4], lcs[7], lcs[2], lcs[5], lcs[8]]

    rotMat = [math.cos(alpha_r), 0, math.sin(alpha_r), 0, 1, 0, -math.sin(alpha_r), 0, math.cos(alpha_r)]

    for v in verts_in:
        p_temp = [v[0]-Oa[0], v[1]-Oa[1], v[2]-Oa[2]]
        p1 = mat_vec_mult(lcsInv, p_temp)
        p2 = mat_vec_mult(rotMat, p1)
        p_world = mat_vec_mult(lcs, p2)
        trans = [p_world[0]+Oa[0], p_world[1]+Oa[1], p_world[2]+Oa[2]]
        verts_trans_out.append([trans[0], trans[1], trans[2], v[3], v[4]])

        threeD_norm = [trans[0]-camera[0], trans[1]-camera[1], trans[2]-camera[2]]
        q = mat_vec_mult(invTrans, threeD_norm)
        
        if q[2] >= 0.0:
            sx = (q[0]/q[2] + 1) * viewport_w / 2.0
            sy = (1 - q[1]/q[2]) * viewport_h / 2.0
            sz = 1.0 / q[2]
            verts_2d_out.append([sx, sy, sz, v[3], v[4]])
        else:
            verts_2d_out.append([0.0, 0.0, 0.0, 0.0, 0.0])


    # --- STAGE 2: TRIANGLE SHADER(S) ---
    depth_buffer = [f32(0.0)] * (viewport_w * viewport_h)
    tag_buffer = [-1] * (viewport_w * viewport_h)
    
    tri_structs = {} 
    tri_list = range(12) if args.mode in ['all_tris', 'pixel', 'pipeline'] else [args.tri_idx]

    if args.mode in ['triangle', 'pixel', 'pipeline', 'all_tris']:
        for t_idx in tri_list:
            target_tri = tris_map[t_idx]
            pVs = [verts_2d_out[target_tri[0]], verts_2d_out[target_tri[1]], verts_2d_out[target_tri[2]]]
            
            u_min = max(0, int(min(pVs[0][0], pVs[1][0], pVs[2][0]) - 0.5))
            u_max = min(viewport_w - 1, int(max(pVs[0][0], pVs[1][0], pVs[2][0]) + 0.5))
            v_min = max(0, int(min(pVs[0][1], pVs[1][1], pVs[2][1]) - 0.5))
            v_max = min(viewport_h - 1, int(max(pVs[0][1], pVs[1][1], pVs[2][1]) + 0.5))
            
            bb_start = [u_min, v_min]
            bb_size = [max(0, u_max - u_min), max(0, v_max - v_min)]

            m = [[f32(1.0), f32(1.0), f32(1.0)], 
                 [f32(pVs[0][0]), f32(pVs[1][0]), f32(pVs[2][0])], 
                 [f32(pVs[0][1]), f32(pVs[1][1]), f32(pVs[2][1])]]
            bc_im = inv3x3(m)

            for ix in range(bb_size[0]):
                for iy in range(bb_size[1]):
                    u = ix + bb_start[0]
                    v = iy + bb_start[1]
                    
                    l0 = f32(f32(1.0 * bc_im[0]) + f32((u+0.5) * bc_im[1]) + f32((v+0.5) * bc_im[2]))
                    l1 = f32(f32(1.0 * bc_im[3]) + f32((u+0.5) * bc_im[4]) + f32((v+0.5) * bc_im[5]))
                    l2 = f32(f32(1.0 * bc_im[6]) + f32((u+0.5) * bc_im[7]) + f32((v+0.5) * bc_im[8]))
                    
                    if l0 < f32(-0.00001) or l1 < f32(-0.00001) or l2 < f32(-0.00001) or f32(l0+l1+l2) > f32(1.01):
                        continue 
                        
                    pix_z = f32(f32(l0*f32(pVs[0][2])) + f32(l1*f32(pVs[1][2])) + f32(l2*f32(pVs[2][2])))
                    
                    if pix_z >= f32(0.0):
                        idx = v * viewport_w + u
                        if tag_buffer[idx] == -1 or pix_z >= depth_buffer[idx]:
                            depth_buffer[idx] = pix_z
                            tag_buffer[idx] = t_idx 

            t_args = [(0, int_to_hex(bb_start[0])), (4, int_to_hex(bb_start[1])), (8, int_to_hex(bb_size[0])), (12, int_to_hex(bb_size[1]))]
            for i, val in enumerate(bc_im): t_args.append((16 + i*4, float_to_hex(val)))
            t_args.append((52, int_to_hex(t_idx))) 
            
            pv_idx = 56
            for vec in pVs:
                for coord in vec[:3]:
                    t_args.append((pv_idx, float_to_hex(coord)))
                    pv_idx += 4
                    
            t_args.extend([(92, int_to_hex(viewport_w)), (96, int_to_hex(viewport_h)), (100, int_to_hex(ADDR_DEPTH_BUFF)), (104, int_to_hex(ADDR_TAG_BUFF))])
            tri_structs[t_idx] = t_args


    # --- STAGE 3: PIXEL SHADER ---
    color_buffer = [[0.0, 0.0, 0.0] for _ in range(viewport_w * viewport_h)]

    if args.mode in ['pixel', 'pipeline']:
        for idx in range(viewport_w * viewport_h):
            u = idx % viewport_w
            v = idx // viewport_w
            tag = tag_buffer[idx]

            if tag >= 0:
                tri = tris_map[tag]
                pVs = [verts_2d_out[tri[0]], verts_2d_out[tri[1]], verts_2d_out[tri[2]]]

                # Explicit 32-bit cast mapping of Pixel Shader C Code
                point_x = f32(f32(float(u)) + f32(0.5))
                point_y = f32(f32(float(v)) + f32(0.5))

                m00, m01, m02 = f32(1.0), f32(1.0), f32(1.0)
                m10, m11, m12 = f32(pVs[0][0]), f32(pVs[1][0]), f32(pVs[2][0])
                m20, m21, m22 = f32(pVs[0][1]), f32(pVs[1][1]), f32(pVs[2][1])

                t1 = f32(f32(m11 * m22) - f32(m21 * m12))
                t2 = f32(f32(m10 * m22) - f32(m12 * m20))
                t3 = f32(f32(m10 * m21) - f32(m11 * m20))
                det = f32(f32(m00 * t1) - f32(m01 * t2) + f32(m02 * t3))

                if det > f32(-0.00001) and det < f32(0.00001):
                    continue
                else:
                    invDet = f32(f32(1.0) / det)

                    bc00 = f32(t1 * invDet)
                    bc01 = f32(f32(f32(m02 * m21) - f32(m01 * m22)) * invDet)
                    bc02 = f32(f32(f32(m01 * m12) - f32(m02 * m11)) * invDet)
                    bc10 = f32(f32(f32(m12 * m20) - f32(m10 * m22)) * invDet)
                    bc11 = f32(f32(f32(m00 * m22) - f32(m02 * m20)) * invDet)
                    bc12 = f32(f32(f32(m02 * m10) - f32(m00 * m12)) * invDet)
                    bc20 = f32(f32(f32(m10 * m21) - f32(m20 * m11)) * invDet)
                    bc21 = f32(f32(f32(m20 * m01) - f32(m00 * m21)) * invDet)
                    bc22 = f32(f32(f32(m00 * m11) - f32(m10 * m01)) * invDet)

                    lx = f32(f32(bc00) + f32(bc01 * point_x) + f32(bc02 * point_y))
                    ly = f32(f32(bc10) + f32(bc11 * point_x) + f32(bc12 * point_y))
                    lz = f32(f32(bc20) + f32(bc21 * point_x) + f32(bc22 * point_y))

                    z0, z1, z2 = f32(pVs[0][2]), f32(pVs[1][2]), f32(pVs[2][2])
                    correction_factor = f32(f32(lx * z0) + f32(ly * z1) + f32(lz * z2))

                    s0, s1, s2 = f32(pVs[0][3]), f32(pVs[1][3]), f32(pVs[2][3])
                    s = f32(f32(lx * f32(s0 * z0)) + f32(ly * f32(s1 * z1)) + f32(lz * f32(s2 * z2)))
                    s = f32(s / correction_factor)

                    t0, t1, t2 = f32(pVs[0][4]), f32(pVs[1][4]), f32(pVs[2][4])
                    t = f32(f32(lx * f32(t0 * z0)) + f32(ly * f32(t1 * z1)) + f32(lz * f32(t2 * z2)))
                    t = f32(t / correction_factor)

                    s_abs = s if s > f32(0.0) else f32(f32(0.0) - s)
                    t_abs = t if t > f32(0.0) else f32(f32(0.0) - t)

                    w_minus_1 = f32(tex_w - 1)
                    h_minus_1 = f32(tex_h - 1)

                    s_fract = f32(s_abs - f32(int(float(s_abs))))
                    t_fract = f32(t_abs - f32(int(float(t_abs))))

                    texel_x = int(float(f32(f32(s_fract * w_minus_1) + f32(0.5))))
                    texel_y = int(float(f32(f32(t_fract * h_minus_1) + f32(0.5))))

                    tex_idx = texel_y * tex_w + texel_x
                    if tex_idx < len(texture_arr):
                        color_buffer[idx] = texture_arr[tex_idx]

    # --- STAGE 4: WRITE HEX FILES ---
    print(f"Baking memory for MODE: {args.mode.upper()} | Res: {viewport_w}x{viewport_h}")
    
    with open(args.out_init, 'w') as f_init, open(args.out_exp, 'w') as f_exp:
        
        # Init: Vertex Mode
        if args.mode in ['vertex', 'pipeline']:
            v_args = [(0, int_to_hex(ADDR_OA)), (4, int_to_hex(ADDR_ADIST)), (8, int_to_hex(ADDR_ALPHAR)), (12, int_to_hex(ADDR_VERTS_IN)), (16, int_to_hex(ADDR_VERTS_TRANS_OUT)), (20, int_to_hex(ADDR_CAMERA)), (24, int_to_hex(ADDR_INVTRANS)), (28, int_to_hex(ADDR_VERTS_2D_OUT)), (32, int_to_hex(num_verts)), (36, float_to_hex(viewport_w)), (40, float_to_hex(viewport_h))]
            for offset, val in v_args: write_line(f_init, ADDR_ARGS_VERT + offset, val)
    
            write_line(f_init, ADDR_OA, float_to_hex(Oa[0])); write_line(f_init, ADDR_OA+4, float_to_hex(Oa[1])); write_line(f_init, ADDR_OA+8, float_to_hex(Oa[2]))
            write_line(f_init, ADDR_ADIST, float_to_hex(a_dist[0])); write_line(f_init, ADDR_ADIST+4, float_to_hex(a_dist[1])); write_line(f_init, ADDR_ADIST+8, float_to_hex(a_dist[2]))
            write_line(f_init, ADDR_ALPHAR, float_to_hex(alpha_r))
            write_line(f_init, ADDR_CAMERA, float_to_hex(camera[0])); write_line(f_init, ADDR_CAMERA+4, float_to_hex(camera[1])); write_line(f_init, ADDR_CAMERA+8, float_to_hex(camera[2]))
            for i, val in enumerate(invTrans): write_line(f_init, ADDR_INVTRANS + (i*4), float_to_hex(val))
            
            curr_addr = ADDR_VERTS_IN
            for v in verts_in:
                for i in range(5): write_line(f_init, curr_addr + (i*4), float_to_hex(v[i]))
                curr_addr += 20

        # Init: Triangle Mode
        if args.mode in ['triangle', 'pipeline', 'all_tris', 'pixel']:
            for t_idx, struct_lines in tri_structs.items():
                base_addr = ADDR_ARGS_TRI + (t_idx * 0x100) if args.mode in ['all_tris', 'pixel', 'pipeline'] else ADDR_ARGS_TRI
                for offset, val in struct_lines:
                    write_line(f_init, base_addr + offset, val)
                    
            for idx in range(viewport_w * viewport_h):
                write_line(f_init, ADDR_DEPTH_BUFF + (idx * 4), float_to_hex(0.0 if args.mode == 'triangle' else depth_buffer[idx]))
                write_line(f_init, ADDR_TAG_BUFF + (idx * 4), int_to_hex(-1 if args.mode == 'triangle' else tag_buffer[idx]))

        # Init: Pixel Mode specific inputs
        if args.mode in ['pixel', 'pipeline']:
            p_args = [
                (0, int_to_hex(ADDR_VERTS_2D_OUT)), (4, int_to_hex(num_verts)),
                (8, int_to_hex(ADDR_TRIS)), (12, int_to_hex(len(tris_map))),
                (16, int_to_hex(viewport_w)), (20, int_to_hex(viewport_h)),
                (24, int_to_hex(ADDR_DEPTH_BUFF)), (28, int_to_hex(ADDR_TAG_BUFF)),
                (32, int_to_hex(ADDR_COLOR_OUT)), (36, int_to_hex(tex_w)),
                (40, int_to_hex(tex_h)), (44, int_to_hex(ADDR_TEXTURE_COLORS))
            ]
            for offset, val in p_args: write_line(f_init, ADDR_ARGS_PIXEL + offset, val)
            
            curr_addr = ADDR_VERTS_2D_OUT
            for v in verts_2d_out:
                for i in range(5): write_line(f_init, curr_addr + (i*4), float_to_hex(v[i]))
                curr_addr += 20
                
            curr_addr = ADDR_TRIS
            for tri in tris_map:
                for i in range(3): write_line(f_init, curr_addr + (i*4), int_to_hex(tri[i]))
                curr_addr += 12
                
            curr_addr = ADDR_TEXTURE_COLORS
            for color in texture_arr:
                for i in range(3): write_line(f_init, curr_addr + (i*4), float_to_hex(color[i]))
                curr_addr += 12

        # Expected Output generation
        if args.mode == 'vertex':
            curr_trans, curr_2d = ADDR_VERTS_TRANS_OUT, ADDR_VERTS_2D_OUT
            for trans, p2d in zip(verts_trans_out, verts_2d_out):
                for i in range(5): write_line(f_exp, curr_trans + (i*4), float_to_hex(trans[i]))
                curr_trans += 20
                for i in range(5): write_line(f_exp, curr_2d + (i*4), float_to_hex(p2d[i]))
                curr_2d += 20

        elif args.mode in ['triangle', 'all_tris']:
            for idx in range(viewport_w * viewport_h):
                write_line(f_exp, ADDR_DEPTH_BUFF + (idx * 4), float_to_hex(depth_buffer[idx]))
                write_line(f_exp, ADDR_TAG_BUFF + (idx * 4), int_to_hex(tag_buffer[idx]))
                
        elif args.mode in ['pixel', 'pipeline']:
            for idx in range(viewport_w * viewport_h):
                addr = ADDR_COLOR_OUT + (idx * 12)
                color = color_buffer[idx]
                write_line(f_exp, addr, float_to_hex(color[0]))
                write_line(f_exp, addr+4, float_to_hex(color[1]))
                write_line(f_exp, addr+8, float_to_hex(color[2]))

if __name__ == "__main__":
    main()