import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from graphics_lib import Triangle, Projector, Vertex


class Rasterizer:
    def __init__(self, vs=None, col1=None, col2=None, col3=None,
                 u=None, v=None, msaa=0, w=1280, h=720, near=1, far=10, tex_id=None):
        if vs is None: vs = [[[]]]
        if col1 is None: col1 = [[]]
        if col2 is None: col2 = [[]]
        if col3 is None: col3 = [[]]
        if u is None: u = [[-1, -1, -1]]
        if v is None: v = [[-1, -1, -1]]
        if tex_id is None: tex_id = [-1]

        self.msaa = 2 if (msaa > 2) else msaa
        self.w = w
        self.h = h
        self.vs = vs
        self.col1 = col1
        self.col2 = col2
        self.col3 = col3

        count = len(vs)
        self.u = u * count if u[0][0] == -1 else u
        self.v = v * count if v[0][0] == -1 else v
        self.tex_ids = tex_id * count if tex_id[0] == -1 else tex_id

        self.projector = Projector(self.w, self.h, near, far)
        self.screen = np.zeros((h, w, 3))

        z_depth = self.msaa if self.msaa > 0 else 1
        self.z_buffer = np.full((h, w, z_depth), np.inf)
        self.color_buffer = np.zeros((h, w, z_depth, 3))
        self.uv_buffer = np.full((h, w, 2), np.nan)
        self.sampleId_buffer = np.full((h, w), -1.0, dtype=int)

    # --- Geometry Helpers ---

    def getNDC(self, vertex: Vertex):
        near_point = self.projector.toNearPlane(vertex)
        ndc = self.projector.toNDC(near_point)
        ndc.z = self.projector.depth(ndc)
        return ndc

    def project(self, vert):
        ndc = self.getNDC(vert)
        return self.projector.toScreenSpace(ndc)

    def edge(self, a, b, x, y):
        return (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x)

    def validEdge(self, v0, v1):
        edge_vec = [v1.x - v0.x, v1.y - v0.y]
        is_top = (edge_vec[1] == 0 and edge_vec[0] < 0)
        is_left = (edge_vec[1] < 0)
        return is_top or is_left

    def de_dx(self, a, b):
        return -b.y + a.y

    def de_dy(self, a, b):
        return b.x - a.x

    # --- Buffer Accessors ---

    def getUV(self):
        return self.uv_buffer

    def getSamples(self):
        return self.sampleId_buffer

    def applyTextures(self, newRGB: np.array):
        # Optimized Apply Textures
        mask = np.isfinite(self.uv_buffer[:, :, 0])

        # Extract texture RGBs where valid
        # newRGB shape matches screen shape, so we can just use the mask

        if self.msaa == 2:
            # We need to broadcast the texture data to the MSAA samples
            # newRGB is (H, W, 3). color_buffer is (H, W, 2, 3)
            # We can multiply.

            # Expand dims of newRGB to (H, W, 1, 3) so it broadcasts over the 2 samples
            tex_data = newRGB[:, :, np.newaxis, :]

            # Apply to color buffer only where mask is true
            self.color_buffer[mask] *= tex_data[mask]

            # Resolve to screen
            self.screen[mask] = np.mean(self.color_buffer[mask], axis=1)

        else:
            self.screen[mask] *= newRGB[mask]

    # --- Rendering ---

    def render(self):
        if self.msaa == 2:
            self.render_2msaa()
        else:
            self.render_0msaa()

    def render_2msaa(self):
        for i in range(len(self.vs)):
            v1 = Vertex(self.vs[i][0][0], self.vs[i][0][1], self.vs[i][0][2], self.col1[i], self.u[i][0], self.v[i][0])
            v2 = Vertex(self.vs[i][1][0], self.vs[i][1][1], self.vs[i][1][2], self.col2[i], self.u[i][1], self.v[i][1])
            v3 = Vertex(self.vs[i][2][0], self.vs[i][2][1], self.vs[i][2][2], self.col3[i], self.u[i][2], self.v[i][2])

            tri_orig = Triangle(v1, v2, v3)

            ss_v1 = self.project(tri_orig.A)
            ss_v2 = self.project(tri_orig.B)
            ss_v3 = self.project(tri_orig.C)
            ss_tri = Triangle(ss_v1, ss_v2, ss_v3)

            area = self.edge(ss_tri.A, ss_tri.B, ss_tri.C.x, ss_tri.C.y) / 2
            if area < 0:
                ss_tri.B, ss_tri.C = ss_tri.C, ss_tri.B
                area = -area

            if area == 0: continue
            norm_factor = 1.0 / (2 * area)

            # --- Bounding Box & Scissor Clamping ---
            raw_min = ss_tri.min().floor()
            raw_max = ss_tri.max().ceil()

            min_x = max(0, int(raw_min.x))
            max_x = min(self.w, int(raw_max.x))
            min_y = max(0, int(raw_min.y))
            max_y = min(self.h, int(raw_max.y))

            # If triangle is off screen, skip
            if min_x >= max_x or min_y >= max_y:
                continue

            # --- Setup Edges ---
            # IMPORTANT: We initialize edge functions based on the CLAMPED min_x/min_y
            # This ensures the loop logic stays consistent.
            x0, y0 = min_x + 0.25, min_y + 0.25
            x1, y1 = min_x + 0.75, min_y + 0.75
            cx, cy = min_x + 0.50, min_y + 0.50

            e0_1 = self.edge(ss_tri.B, ss_tri.C, x0, y0) * norm_factor
            e0_2 = self.edge(ss_tri.C, ss_tri.A, x0, y0) * norm_factor
            e0_3 = self.edge(ss_tri.A, ss_tri.B, x0, y0) * norm_factor

            e1_1 = self.edge(ss_tri.B, ss_tri.C, x1, y1) * norm_factor
            e1_2 = self.edge(ss_tri.C, ss_tri.A, x1, y1) * norm_factor
            e1_3 = self.edge(ss_tri.A, ss_tri.B, x1, y1) * norm_factor

            ec_1 = self.edge(ss_tri.B, ss_tri.C, cx, cy) * norm_factor
            ec_2 = self.edge(ss_tri.C, ss_tri.A, cx, cy) * norm_factor
            ec_3 = self.edge(ss_tri.A, ss_tri.B, cx, cy) * norm_factor

            dx1 = self.de_dx(ss_tri.B, ss_tri.C) * norm_factor
            dx2 = self.de_dx(ss_tri.C, ss_tri.A) * norm_factor
            dx3 = self.de_dx(ss_tri.A, ss_tri.B) * norm_factor

            dy1 = self.de_dy(ss_tri.B, ss_tri.C) * norm_factor
            dy2 = self.de_dy(ss_tri.C, ss_tri.A) * norm_factor
            dy3 = self.de_dy(ss_tri.A, ss_tri.B) * norm_factor

            row_e0_1, row_e0_2, row_e0_3 = e0_1, e0_2, e0_3
            row_e1_1, row_e1_2, row_e1_3 = e1_1, e1_2, e1_3
            row_ec_1, row_ec_2, row_ec_3 = ec_1, ec_2, ec_3

            check1 = 0 if self.validEdge(ss_tri.B, ss_tri.C) else -1e-12
            check2 = 0 if self.validEdge(ss_tri.C, ss_tri.A) else -1e-12
            check3 = 0 if self.validEdge(ss_tri.A, ss_tri.B) else -1e-12

            for y in range(min_y, max_y):
                e0_1, e0_2, e0_3 = row_e0_1, row_e0_2, row_e0_3
                e1_1, e1_2, e1_3 = row_e1_1, row_e1_2, row_e1_3
                ec_1, ec_2, ec_3 = row_ec_1, row_ec_2, row_ec_3

                for x in range(min_x, max_x):
                    cov0 = (e0_1 + check1 >= 0) and (e0_2 + check2 >= 0) and (e0_3 + check3 >= 0)
                    cov1 = (e1_1 + check1 >= 0) and (e1_2 + check2 >= 0) and (e1_3 + check3 >= 0)

                    if cov0 or cov1:
                        z0 = (ss_tri.A.z * e0_1 + ss_tri.B.z * e0_2 + ss_tri.C.z * e0_3)
                        z1 = (ss_tri.A.z * e1_1 + ss_tri.B.z * e1_2 + ss_tri.C.z * e1_3)

                        pass0 = cov0 and (z0 <= self.z_buffer[y][x][0])
                        pass1 = cov1 and (z1 <= self.z_buffer[y][x][1])

                        if pass0 or pass1:
                            self.sampleId_buffer[y][x] = self.tex_ids[i]

                            if pass0 and not pass1:
                                w1, w2, w3 = e0_1, e0_2, e0_3
                            elif not pass0 and pass1:
                                w1, w2, w3 = e1_1, e1_2, e1_3
                            else:
                                w1, w2, w3 = ec_1, ec_2, ec_3

                            # Attribute Interpolation
                            r = ss_tri.A.R * w1 + ss_tri.B.R * w2 + ss_tri.C.R * w3
                            g = ss_tri.A.G * w1 + ss_tri.B.G * w2 + ss_tri.C.G * w3
                            b = ss_tri.A.B * w1 + ss_tri.B.B * w2 + ss_tri.C.B * w3
                            u_interp = ss_tri.A.u * w1 + ss_tri.B.u * w2 + ss_tri.C.u * w3
                            v_interp = ss_tri.A.v * w1 + ss_tri.B.v * w2 + ss_tri.C.v * w3

                            self.uv_buffer[y][x][0] = u_interp
                            self.uv_buffer[y][x][1] = v_interp

                            if pass0:
                                self.z_buffer[y][x][0] = z0
                                self.color_buffer[y][x][0] = [r, g, b]

                            if pass1:
                                self.z_buffer[y][x][1] = z1
                                self.color_buffer[y][x][1] = [r, g, b]

                            c0 = self.color_buffer[y][x][0]
                            c1 = self.color_buffer[y][x][1]
                            self.screen[y][x] = (c0 + c1) / 2.0

                    e0_1 += dx1;
                    e0_2 += dx2;
                    e0_3 += dx3
                    e1_1 += dx1;
                    e1_2 += dx2;
                    e1_3 += dx3
                    ec_1 += dx1;
                    ec_2 += dx2;
                    ec_3 += dx3

                row_e0_1 += dy1;
                row_e0_2 += dy2;
                row_e0_3 += dy3
                row_e1_1 += dy1;
                row_e1_2 += dy2;
                row_e1_3 += dy3
                row_ec_1 += dy1;
                row_ec_2 += dy2;
                row_ec_3 += dy3

    def render_0msaa(self):
        for i in range(len(self.vs)):
            v1 = Vertex(self.vs[i][0][0], self.vs[i][0][1], self.vs[i][0][2], self.col1[i], self.u[i][0], self.v[i][0])
            v2 = Vertex(self.vs[i][1][0], self.vs[i][1][1], self.vs[i][1][2], self.col2[i], self.u[i][1], self.v[i][1])
            v3 = Vertex(self.vs[i][2][0], self.vs[i][2][1], self.vs[i][2][2], self.col3[i], self.u[i][2], self.v[i][2])

            tri_orig = Triangle(v1, v2, v3)

            ss_v1 = self.project(tri_orig.A)
            ss_v2 = self.project(tri_orig.B)
            ss_v3 = self.project(tri_orig.C)
            ss_tri = Triangle(ss_v1, ss_v2, ss_v3)

            area = self.edge(ss_tri.A, ss_tri.B, ss_tri.C.x, ss_tri.C.y) / 2
            if area < 0:
                ss_tri.B, ss_tri.C = ss_tri.C, ss_tri.B
                area = -area

            if area == 0: continue
            norm_factor = 1.0 / (2 * area)

            # --- Bounding Box & Scissor Clamping ---
            raw_min = ss_tri.min().floor()
            raw_max = ss_tri.max().ceil()

            min_x = max(0, int(raw_min.x))
            max_x = min(self.w, int(raw_max.x))
            min_y = max(0, int(raw_min.y))
            max_y = min(self.h, int(raw_max.y))

            if min_x >= max_x or min_y >= max_y:
                continue

            # --- Setup Edges ---
            cx, cy = min_x + 0.5, min_y + 0.5

            e_1 = self.edge(ss_tri.B, ss_tri.C, cx, cy) * norm_factor
            e_2 = self.edge(ss_tri.C, ss_tri.A, cx, cy) * norm_factor
            e_3 = self.edge(ss_tri.A, ss_tri.B, cx, cy) * norm_factor

            dx1 = self.de_dx(ss_tri.B, ss_tri.C) * norm_factor
            dx2 = self.de_dx(ss_tri.C, ss_tri.A) * norm_factor
            dx3 = self.de_dx(ss_tri.A, ss_tri.B) * norm_factor

            dy1 = self.de_dy(ss_tri.B, ss_tri.C) * norm_factor
            dy2 = self.de_dy(ss_tri.C, ss_tri.A) * norm_factor
            dy3 = self.de_dy(ss_tri.A, ss_tri.B) * norm_factor

            row_e1, row_e2, row_e3 = e_1, e_2, e_3

            check1 = 0 if self.validEdge(ss_tri.B, ss_tri.C) else -1e-12
            check2 = 0 if self.validEdge(ss_tri.C, ss_tri.A) else -1e-12
            check3 = 0 if self.validEdge(ss_tri.A, ss_tri.B) else -1e-12

            for y in range(min_y, max_y):
                e_1, e_2, e_3 = row_e1, row_e2, row_e3

                for x in range(min_x, max_x):
                    if (e_1 + check1 >= 0) and (e_2 + check2 >= 0) and (e_3 + check3 >= 0):
                        z = ss_tri.A.z * e_1 + ss_tri.B.z * e_2 + ss_tri.C.z * e_3

                        if z <= self.z_buffer[y][x][0]:
                            r = ss_tri.A.R * e_1 + ss_tri.B.R * e_2 + ss_tri.C.R * e_3
                            g = ss_tri.A.G * e_1 + ss_tri.B.G * e_2 + ss_tri.C.G * e_3
                            b = ss_tri.A.B * e_1 + ss_tri.B.B * e_2 + ss_tri.C.B * e_3

                            u = ss_tri.A.u * e_1 + ss_tri.B.u * e_2 + ss_tri.C.u * e_3
                            v = ss_tri.A.v * e_1 + ss_tri.B.v * e_2 + ss_tri.C.v * e_3

                            self.screen[y][x] = [r, g, b]
                            self.sampleId_buffer[y][x] = self.tex_ids[i]
                            self.uv_buffer[y][x] = [u, v]
                            self.z_buffer[y][x][0] = z

                    e_1 += dx1
                    e_2 += dx2
                    e_3 += dx3

                row_e1 += dy1
                row_e2 += dy2
                row_e3 += dy3

    def showScreen(self):
        plt.imshow(np.clip(self.screen, 0.0, 1.0))
        plt.axis('off')
        plt.show()

    def saveScreen(self, filename='lossless.png'):
        img_uint8 = (np.clip(self.screen, 0.0, 1.0) * 255).astype(np.uint8)
        img = Image.fromarray(img_uint8)
        img.save(filename, mode='RGB')