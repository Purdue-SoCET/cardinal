import struct
import math
import argparse

# ==========================================
# Memory Map Layout
# ==========================================
ADDR_ARGS_VERT       = 0x20000000 # vertexShader_arg_t
ADDR_ARGS_TRI        = 0x20000100 # triangle_arg_t

ADDR_VERTS_IN        = 0x30000000 # Input array
ADDR_OA              = 0x30000100 
ADDR_ADIST           = 0x30000110 
ADDR_ALPHAR          = 0x30000120 
ADDR_CAMERA          = 0x30000130 
ADDR_INVTRANS        = 0x30000140 

ADDR_VERTS_TRANS_OUT = 0x40000000 # 3D Transformed Output
ADDR_VERTS_2D_OUT    = 0x40000200 # 2D Projected Output

ADDR_DEPTH_BUFF      = 0x50000000 # Z-Buffer
ADDR_TAG_BUFF        = 0x51000000 # Tag Buffer

# ==========================================
# Helpers
# ==========================================
def float_to_hex(f):
    packed = struct.pack('>f', f) 
    return f"0x{packed.hex().upper()}"

def int_to_hex(i):
    packed = struct.pack('>i', int(i))
    return f"0x{packed.hex().upper()}"

def write_line(f_handle, addr, val_str):
    f_handle.write(f"0x{addr:08X} {val_str}\n")

# Vector & Matrix Math
def cross(v1, v2):
    return [v1[1]*v2[2] - v1[2]*v2[1], v1[2]*v2[0] - v1[0]*v2[2], v1[0]*v2[1] - v1[1]*v2[0]]

def normalize(v):
    mag = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
    if mag == 0: return [0.0, 0.0, 0.0]
    return [v[0]/mag, v[1]/mag, v[2]/mag]

def mat_vec_mult(mat, vec):
    return [
        mat[0]*vec[0] + mat[1]*vec[1] + mat[2]*vec[2],
        mat[3]*vec[0] + mat[4]*vec[1] + mat[5]*vec[2],
        mat[6]*vec[0] + mat[7]*vec[1] + mat[8]*vec[2]
    ]

def det3x3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2]) -
            m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
            m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))

def inv3x3(m):
    d = det3x3(m)
    if abs(d) < 1e-8: return [0]*9
    invD = 1.0 / d
    return [
        (m[1][1]*m[2][2] - m[2][1]*m[1][2])*invD, (m[0][2]*m[2][1] - m[0][1]*m[2][2])*invD, (m[0][1]*m[1][2] - m[0][2]*m[1][1])*invD,
        (m[1][2]*m[2][0] - m[1][0]*m[2][2])*invD, (m[0][0]*m[2][2] - m[0][2]*m[2][0])*invD, (m[0][2]*m[1][0] - m[0][0]*m[1][2])*invD,
        (m[1][0]*m[2][1] - m[2][0]*m[1][1])*invD, (m[0][1]*m[2][0] - m[0][0]*m[2][1])*invD, (m[0][0]*m[1][1] - m[0][1]*m[1][0])*invD
    ]

# ==========================================
# Main Simulation
# ==========================================
def main():
    parser = argparse.ArgumentParser()
    
    # Test Architecture Setup
    parser.add_argument("--mode", choices=['vertex', 'triangle', 'pipeline'], required=True)
    parser.add_argument("--out_init", default="init.hex")
    parser.add_argument("--out_exp", default="expected.hex")
    
    # Simulation Parameters
    parser.add_argument("--angle", type=float, default=0.0)
    parser.add_argument("--camera", type=float, nargs=3, default=[0.0, 0.0, 0.0])
    parser.add_argument("--origin", type=float, nargs=3, default=[0.0, 0.0, -30.0])
    parser.add_argument("--axis", type=float, nargs=3, default=[1.0, 1.0, 0.0])
    
    # Triangle specific parameters
    parser.add_argument("--buff_w", type=int, default=800)
    parser.add_argument("--buff_h", type=int, default=800)
    parser.add_argument("--tri_tag", type=int, default=7)
    
    args = parser.parse_args()

    num_verts = 8
    viewport_w, viewport_h = args.buff_w, args.buff_h
    alpha_r = args.angle
    Oa = args.origin
    a_dist = args.axis
    camera = args.camera
    
    invTrans = [
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, -1.0
    ]

    verts_in = [
        [-10, -10, -20, 0, 0], [-10,  10, -20, 0, 1],
        [ 10, -10, -20, 1, 0], [ 10,  10, -20, 1, 1],
        [-10, -10, -40, 0, 1], [-10,  10, -40, 1, 1],
        [ 10, -10, -40, 0, 0], [ 10,  10, -40, 1, 0]
    ]

    # ---------------------------------------------------------
    # STAGE 1: SIMULATE VERTEX SHADER
    # ---------------------------------------------------------
    verts_trans_out = []
    verts_2d_out = []

    selAxis = [0.0, 0.0, 0.0]
    x2 = a_dist[0] * a_dist[0]
    y2 = a_dist[1] * a_dist[1]
    z2 = a_dist[2] * a_dist[2]
    if x2 < y2 and x2 < z2: selAxis[0] = 1.0
    elif y2 < z2: selAxis[1] = 1.0
    else: selAxis[2] = 1.0
    
    lcs_row0 = normalize(cross(selAxis, a_dist))
    lcs_row1 = normalize(a_dist)
    lcs_row2 = normalize(cross(lcs_row0, lcs_row1))
    lcs = lcs_row0 + lcs_row1 + lcs_row2
    lcsInv = [lcs[0], lcs[3], lcs[6], lcs[1], lcs[4], lcs[7], lcs[2], lcs[5], lcs[8]]

    rotMat = [
        math.cos(alpha_r), 0, math.sin(alpha_r),
        0, 1, 0,
        -math.sin(alpha_r), 0, math.cos(alpha_r)
    ]

    for v in verts_in:
        coords = [v[0], v[1], v[2]]
        p_temp = [coords[0]-Oa[0], coords[1]-Oa[1], coords[2]-Oa[2]]
        p1 = mat_vec_mult(lcsInv, p_temp)
        p2 = mat_vec_mult(rotMat, p1)
        p_world = mat_vec_mult(lcs, p2)
        trans = [p_world[0]+Oa[0], p_world[1]+Oa[1], p_world[2]+Oa[2]]
        verts_trans_out.append([trans[0], trans[1], trans[2], v[3], v[4]])

        threeD_norm = [trans[0]-camera[0], trans[1]-camera[1], trans[2]-camera[2]]
        q = mat_vec_mult(invTrans, threeD_norm)
        
        if q[2] >= 0.0:
            sx = q[0] / q[2]
            sy = q[1] / q[2]
            sz = 1.0 / q[2]
            verts_2d_out.append([sx, sy, sz, v[3], v[4]])
        else:
            verts_2d_out.append([0.0, 0.0, 0.0, 0.0, 0.0])

    # ---------------------------------------------------------
    # STAGE 2: SIMULATE TRIANGLE SHADER
    # ---------------------------------------------------------
    pVs = [verts_2d_out[0], verts_2d_out[1], verts_2d_out[2]]
    
    # Calc Bounding Box
    u_min = max(0, int(min(pVs[0][0], pVs[1][0], pVs[2][0]) - 0.5))
    u_max = min(args.buff_w - 1, int(max(pVs[0][0], pVs[1][0], pVs[2][0]) + 0.5))
    v_min = max(0, int(min(pVs[0][1], pVs[1][1], pVs[2][1]) - 0.5))
    v_max = min(args.buff_h - 1, int(max(pVs[0][1], pVs[1][1], pVs[2][1]) + 0.5))
    
    bb_start = [u_min, v_min]
    bb_size = [u_max - u_min, v_max - v_min]

    # Calc Barycentric Matrix
    m = [
        [1.0, 1.0, 1.0],
        [pVs[0][0], pVs[1][0], pVs[2][0]],
        [pVs[0][1], pVs[1][1], pVs[2][1]]
    ]
    bc_im = inv3x3(m)

    # Rasterize
    rendered_pixels = {}
    for ix in range(bb_size[0]):
        for iy in range(bb_size[1]):
            u = ix + bb_start[0]
            v = iy + bb_start[1]
            
            l0 = 1.0 * bc_im[0] + (u+0.5) * bc_im[1] + (v+0.5) * bc_im[2]
            l1 = 1.0 * bc_im[3] + (u+0.5) * bc_im[4] + (v+0.5) * bc_im[5]
            l2 = 1.0 * bc_im[6] + (u+0.5) * bc_im[7] + (v+0.5) * bc_im[8]
            
            if l0 < -0.0001 or l1 < -0.00001 or l2 < -0.00001 or (l0+l1+l2) > 1.01:
                continue # Outside
                
            pix_z = l0*pVs[0][2] + l1*pVs[1][2] + l2*pVs[2][2]
            
            if pix_z >= 0.0:
                rendered_pixels[(u, v)] = (pix_z, args.tri_tag)

    # ---------------------------------------------------------
    # STAGE 3: WRITE HEX FILES BASED ON ARCHITECTURE MODE
    # ---------------------------------------------------------
    print(f"Baking memory for MODE: {args.mode.upper()}")
    
    with open(args.out_init, 'w') as f_init, open(args.out_exp, 'w') as f_exp:
        
        # --- WRITE INITIALIZATION STATE ---
        if args.mode in ['vertex', 'pipeline']:
            # Write Vertex Args (0x20000000)
            v_args = [
                (0, int_to_hex(ADDR_OA)), (4, int_to_hex(ADDR_ADIST)), (8, int_to_hex(ADDR_ALPHAR)),
                (12, int_to_hex(ADDR_VERTS_IN)), (16, int_to_hex(ADDR_VERTS_TRANS_OUT)),
                (20, int_to_hex(ADDR_CAMERA)), (24, int_to_hex(ADDR_INVTRANS)), (28, int_to_hex(ADDR_VERTS_2D_OUT)),
                (32, int_to_hex(num_verts)), (36, float_to_hex(viewport_w)), (40, float_to_hex(viewport_h))
            ]
            for offset, val in v_args: write_line(f_init, ADDR_ARGS_VERT + offset, val)

            # Write Input Data Pointers
            write_line(f_init, ADDR_OA, float_to_hex(Oa[0])); write_line(f_init, ADDR_OA+4, float_to_hex(Oa[1])); write_line(f_init, ADDR_OA+8, float_to_hex(Oa[2]))
            write_line(f_init, ADDR_ADIST, float_to_hex(a_dist[0])); write_line(f_init, ADDR_ADIST+4, float_to_hex(a_dist[1])); write_line(f_init, ADDR_ADIST+8, float_to_hex(a_dist[2]))
            write_line(f_init, ADDR_ALPHAR, float_to_hex(alpha_r))
            write_line(f_init, ADDR_CAMERA, float_to_hex(camera[0])); write_line(f_init, ADDR_CAMERA+4, float_to_hex(camera[1])); write_line(f_init, ADDR_CAMERA+8, float_to_hex(camera[2]))
            for i, val in enumerate(invTrans): write_line(f_init, ADDR_INVTRANS + (i*4), float_to_hex(val))
            
            curr_addr = ADDR_VERTS_IN
            for v in verts_in:
                for i in range(5): write_line(f_init, curr_addr + (i*4), float_to_hex(v[i]))
                curr_addr += 20

        if args.mode in ['triangle', 'pipeline']:
            # Write Triangle Args Struct (0x20000100)
            # This directly embeds the results of the Host CPU setup and Vertex math!
            t_args = [
                (0, int_to_hex(bb_start[0])), (4, int_to_hex(bb_start[1])),
                (8, int_to_hex(bb_size[0])), (12, int_to_hex(bb_size[1]))
            ]
            for i, val in enumerate(bc_im): t_args.append((16 + i*4, float_to_hex(val)))
            t_args.append((52, int_to_hex(args.tri_tag)))
            
            pv_idx = 56
            for vec in pVs:
                for coord in vec[:3]:
                    t_args.append((pv_idx, float_to_hex(coord)))
                    pv_idx += 4
                    
            t_args.extend([
                (92, int_to_hex(args.buff_w)), (96, int_to_hex(args.buff_h)),
                (100, int_to_hex(ADDR_DEPTH_BUFF)), (104, int_to_hex(ADDR_TAG_BUFF))
            ])
            for offset, val in t_args: write_line(f_init, ADDR_ARGS_TRI + offset, val)


        # --- WRITE EXPECTED OUTPUT STATE ---
        if args.mode == 'vertex':
            curr_trans = ADDR_VERTS_TRANS_OUT
            curr_2d = ADDR_VERTS_2D_OUT
            for trans, p2d in zip(verts_trans_out, verts_2d_out):
                for i in range(5): write_line(f_exp, curr_trans + (i*4), float_to_hex(trans[i]))
                curr_trans += 20
                for i in range(5): write_line(f_exp, curr_2d + (i*4), float_to_hex(p2d[i]))
                curr_2d += 20

        elif args.mode in ['triangle', 'pipeline']:
            # For pipeline, the ultimate output is the depth/tag buffer
            for (u, v), (depth, tag) in rendered_pixels.items():
                idx = v * args.buff_w + u
                write_line(f_exp, ADDR_DEPTH_BUFF + (idx * 4), float_to_hex(depth))
                write_line(f_exp, ADDR_TAG_BUFF + (idx * 4), int_to_hex(tag))

if __name__ == "__main__":
    main()