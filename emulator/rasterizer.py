import numpy as np
from graphics_lib import Triangle, Projector, Vertex
import matplotlib.pyplot as plt
from PIL import Image

#Set up machines
class Rasterizer():

    def getNDC(self, vertex : Vertex):
        near_point = self.projector.toNearPlane(vertex)
        ndc : Vertex = self.projector.toNDC(near_point)
        ndc.z = self.projector.depth(ndc)
        return ndc

    def project(self, vert):
        #Convert to NDC
        ndc = self.getNDC(vert)

        #Convert to screen space
        return self.projector.toScreenSpace(ndc)

    def edge(self, a, b, x, y):
        return (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x)

    def validEdge (self, v0, v1):
        edge_vec = [v1.x - v0.x, v1.y - v0.y]
        top = edge_vec[1] == 0 and edge_vec[0] < 0  
        left = edge_vec[1] < 0                      
        return top or left
    
    def de_dx(self, a, b):
        return -b.y + a.y
    def de_dy(self, a, b):
        return b.x - a.x

    def __init__(self, vx1, vy1, vz1, vx2, vy2, vz2, vx3, vy3, vz3, col1 = [[]], col2 = [[]], col3 = [[]], u = [[-1, -1, -1]], v = [[-1, -1, -1]], msaa = 0, w=1280, h=720, near = 1, far = 10, tex_id = [1]):
        msaa = 2 if (msaa > 2) else msaa
        
        #numpy arrays, all of them. Cols will be nx3x3 array
        self.vx1 = vx1
        self.vy1 = vy1
        self.vz1 = vz1
        
        self.vx2 = vx2
        self.vy2 = vy2
        self.vz2 = vz2

        self.vx3 = vx3
        self.vy3 = vy3
        self.vz3 = vz3

        self.col1 = col1
        self.col2 = col2
        self.col3 = col3

        self.u = u * len(vx1)
        self.v = v * len(vx1)

        self.msaa = msaa
        self.w = w
        self.h = h

        self.tex_ids = tex_id * len(vx1) #The sample name or number whatever you want for each triangle. len = no. triangles

        self.projector = Projector(self.w, self.h, near, far) #width, height, near plane, far plane
        self.screen = np.zeros((h,w,3))
        self.z_buffer = np.full((h,w,msaa if msaa > 0 else 1),np.inf)
        self.color_buffer = np.zeros((h,w,msaa if msaa > 0 else 1,3))
        self.uv_buffer = np.full((h,w,2),np.nan) #if there is a valid uv to be applied for a pixel then np.isfinite(u) and np.isfinite(v)
        self.sampleId_buffer = np.ones((h,w)) * -1 #The sample you should be pulling from for each pixel. 

    def getUV(self):
        return self.uv_buffer
    def getSamples(self):
        return self.sampleId_buffer

    def applyTextures(self, newRGB : np.array):
        #Modulate math, just uses original interpolated color as albedo to apply to texture. 
        for h, datH in enumerate(newRGB):
            for w, datW in enumerate(datH):

                if not np.isfinite(self.uv_buffer[h][w][0]): 
                    continue

                if (self.msaa == 2):
                    self.color_buffer[h][w][0][0] *= datW[0]
                    self.color_buffer[h][w][0][1] *= datW[1]
                    self.color_buffer[h][w][0][2] *= datW[2]

                    self.color_buffer[h][w][1][0] *= datW[0]
                    self.color_buffer[h][w][1][1] *= datW[1]
                    self.color_buffer[h][w][1][2] *= datW[2]

                    self.screen[h][w][0] = (self.color_buffer[h][w][0][0] + self.color_buffer[h][w][1][0]) / 2
                    self.screen[h][w][1] = (self.color_buffer[h][w][0][1] + self.color_buffer[h][w][1][1]) / 2
                    self.screen[h][w][2] = (self.color_buffer[h][w][0][2] + self.color_buffer[h][w][1][2]) / 2
                else:
                    self.screen[h][w][0] *= datW[0]
                    self.screen[h][w][1] *= datW[1]
                    self.screen[h][w][2] *= datW[2]
            

    def render(self): #Attribute interpolator + rasterizer
        for i in range(0,len(self.vx1)):

            #Get primitives

            vertex1 = Vertex(self.vx1[i], self.vy1[i], self.vz1[i], self.col1[i], self.u[i][0], self.v[i][0])
            vertex2 = Vertex(self.vx2[i], self.vy2[i], self.vz2[i], self.col2[i], self.u[i][1], self.v[i][1])
            vertex3 = Vertex(self.vx3[i], self.vy3[i], self.vz3[i], self.col3[i], self.u[i][2], self.v[i][2])

            triangle = Triangle(vertex1, vertex2, vertex3)

            #Convert to screen space

            ss_v1 = self.project(triangle.A)
            ss_v2 = self.project(triangle.B)
            ss_v3 = self.project(triangle.C) 

            ss_tri = Triangle(ss_v1, ss_v2, ss_v3)

            ss_min = ss_tri.min().floor()
            ss_max = ss_tri.max().ceil()

            #Check winding.
            area = self.edge(ss_tri.A, ss_tri.B, ss_tri.C.x, ss_tri.C.y) / 2 #Edge equation is cross product, so divide by 2 to get area of triangle instead of parallelogram.
            if area < 0:
                ss_tri.B, ss_tri.C = ss_tri.C, ss_tri.B
                area = -area
            norm_factor = 1 / (2 * area)

            if (self.msaa == 2):
                x0 = ss_min.x + 0.25
                y0 = ss_min.y + 0.25
                x1 = ss_min.x + 0.75
                y1 = ss_min.y + 0.75

                e0_1 = self.edge(ss_tri.B, ss_tri.C, x0, y0) * norm_factor
                e0_2 = self.edge(ss_tri.C, ss_tri.A, x0, y0) * norm_factor
                e0_3 = self.edge(ss_tri.A, ss_tri.B, x0, y0) * norm_factor
                e1_1 = self.edge(ss_tri.B, ss_tri.C, x1, y1) * norm_factor
                e1_2 = self.edge(ss_tri.C, ss_tri.A, x1, y1) * norm_factor
                e1_3 = self.edge(ss_tri.A, ss_tri.B, x1, y1) * norm_factor

                e0_1_ini = e0_1
                e0_2_ini = e0_2
                e0_3_ini = e0_3
                e1_1_ini = e1_1
                e1_2_ini = e1_2
                e1_3_ini = e1_3

                de0_dx1 = self.de_dx(ss_tri.B, ss_tri.C) * norm_factor
                de0_dx2 = self.de_dx(ss_tri.C, ss_tri.A) * norm_factor
                de0_dx3 = self.de_dx(ss_tri.A, ss_tri.B) * norm_factor

                de0_dy1 = self.de_dy(ss_tri.B, ss_tri.C) * norm_factor
                de0_dy2 = self.de_dy(ss_tri.C, ss_tri.A) * norm_factor
                de0_dy3 = self.de_dy(ss_tri.A, ss_tri.B) * norm_factor
                
            
            bx = ss_min.x + 0.5
            by = ss_min.y + 0.5
            edge1 = self.edge(ss_tri.B, ss_tri.C, bx, by) * norm_factor #Similar logic. Divide by 2 to get triangle area and then divide by area to normalize the result. The cross product above gives unnormalized barycentric coordinates. 
            edge2 = self.edge(ss_tri.C, ss_tri.A, bx, by) * norm_factor
            edge3 = self.edge(ss_tri.A, ss_tri.B, bx, by) * norm_factor
            de_dx1 = self.de_dx(ss_tri.B, ss_tri.C) * norm_factor
            de_dx2 = self.de_dx(ss_tri.C, ss_tri.A) * norm_factor
            de_dx3 = self.de_dx(ss_tri.A, ss_tri.B) * norm_factor
            de_dy1 = self.de_dy(ss_tri.B, ss_tri.C) * norm_factor
            de_dy2 = self.de_dy(ss_tri.C, ss_tri.A) * norm_factor
            de_dy3 = self.de_dy(ss_tri.A, ss_tri.B) * norm_factor
            e_ini1 = edge1
            e_ini2 = edge2
            e_ini3 = edge3

            check1 = 0 if self.validEdge(ss_tri.B, ss_tri.C) else -1e-12 #adjust for subtle fp errors
            check2 = 0 if self.validEdge(ss_tri.C, ss_tri.A) else -1e-12
            check3 = 0 if self.validEdge(ss_tri.A, ss_tri.B) else -1e-12

            #Do edge testing
            for y in range(ss_min.y, ss_max.y):

                if (self.msaa == 2):
                    e0_1 = e0_1_ini
                    e0_2 = e0_2_ini
                    e0_3 = e0_3_ini
                    e1_1 = e1_1_ini
                    e1_2 = e1_2_ini
                    e1_3 = e1_3_ini
                
                edge1 = e_ini1
                edge2 = e_ini2
                edge3 = e_ini3
                    
                for j in range(ss_min.x, ss_max.x):
                    if area == 0:
                        continue

                    if (self.msaa == 2):
                        cov0 = 0
                        cov1 = 0

                        if ((e0_1 + check1 >= 0) and (e0_2 >= 0 + check2) and (e0_3 >= 0 + check3)):
                            cov0 = 1

                        if ((e1_1 >= 0 + check1) and (e1_2 >= 0 + check2) and (e1_3 >= 0 + check3)):
                            cov1 = 1

                        z0 = (ss_tri.A.z * e0_1 + ss_tri.B.z * e0_2 + ss_tri.C.z * e0_3)
                        z1 = (ss_tri.A.z * e1_1 + ss_tri.B.z * e1_2 + ss_tri.C.z * e1_3)

                        pass0 = (cov0 and z0 <= self.z_buffer[y][j][0])
                        pass1 = (cov1 and z1 <= self.z_buffer[y][j][1])

                        if (pass0 or pass1):
                            r0 = self.color_buffer[y][j][0][0]
                            g0 = self.color_buffer[y][j][0][1]
                            b0 = self.color_buffer[y][j][0][2]

                            r1 = self.color_buffer[y][j][1][0]
                            g1 = self.color_buffer[y][j][1][1]
                            b1 = self.color_buffer[y][j][1][2]

                            self.sampleId_buffer[y][j] = self.tex_ids[i] #due to per pixel nature of uv, last triangle to shade this pixel owns it outright
                            
                            accum1 = ss_tri.A.R * edge1 + ss_tri.B.R * edge2 + ss_tri.C.R * edge3
                            accum2 = ss_tri.A.G * edge1 + ss_tri.B.G * edge2 + ss_tri.C.G * edge3
                            accum3 = ss_tri.A.B * edge1 + ss_tri.B.B * edge2 + ss_tri.C.B * edge3
                            
                            accumu = ss_tri.A.u * edge1 + ss_tri.B.u * edge2 + ss_tri.C.u * edge3
                            accumv = ss_tri.A.v * edge1 + ss_tri.B.v * edge2 + ss_tri.C.v * edge3

                            if (pass0 and not pass1):
                                accum1 = ss_tri.A.R * e0_1 + ss_tri.B.R * e0_2 + ss_tri.C.R * e0_3
                                accum2 = ss_tri.A.G * e0_1 + ss_tri.B.G * e0_2 + ss_tri.C.G * e0_3
                                accum3 = ss_tri.A.B * e0_1 + ss_tri.B.B * e0_2 + ss_tri.C.B * e0_3
                                accumu = ss_tri.A.u * e0_1 + ss_tri.B.u * e0_2 + ss_tri.C.u * e0_3
                                accumv = ss_tri.A.v * e0_1 + ss_tri.B.v * e0_2 + ss_tri.C.v * e0_3
                            elif (not pass0 and pass1):
                                accum1 = ss_tri.A.R * e1_1 + ss_tri.B.R * e1_2 + ss_tri.C.R * e1_3
                                accum2 = ss_tri.A.G * e1_1 + ss_tri.B.G * e1_2 + ss_tri.C.G * e1_3
                                accum3 = ss_tri.A.B * e1_1 + ss_tri.B.B * e1_2 + ss_tri.C.B * e1_3
                                accumu = ss_tri.A.u * e1_1 + ss_tri.B.u * e1_2 + ss_tri.C.u * e1_3
                                accumv = ss_tri.A.v * e1_1 + ss_tri.B.v * e1_2 + ss_tri.C.v * e1_3

                            self.uv_buffer[y][j][0] = accumu
                            self.uv_buffer[y][j][1] = accumv

                            if (pass0):
                                self.z_buffer[y][j][0] = z0
                                r0 = accum1
                                g0 = accum2
                                b0 = accum3

                            self.color_buffer[y][j][0][0] = r0
                            self.color_buffer[y][j][0][1] = g0
                            self.color_buffer[y][j][0][2] = b0

                            if (pass1):
                                self.z_buffer[y][j][1] = z1
                                r1 = accum1
                                g1 = accum2
                                b1 = accum3

                            self.color_buffer[y][j][1][0] = r1
                            self.color_buffer[y][j][1][1] = g1
                            self.color_buffer[y][j][1][2] = b1

                            self.screen[y][j][0] = (r0 + r1) / 2
                            self.screen[y][j][1] = (g0 + g1) / 2
                            self.screen[y][j][2] = (b0 + b1) / 2

                    else:
                        z = ss_tri.A.z * edge1 + ss_tri.B.z * edge2 + ss_tri.C.z * edge3

                        if ((edge1 + check1 >= 0) and (edge2 + check2 >= 0) and (edge3 + check3 >= 0) and z <= self.z_buffer[y][j][0]):
                            self.screen[y][j][0] = ss_tri.A.R * edge1 + ss_tri.B.R * edge2 + ss_tri.C.R * edge3
                            self.screen[y][j][1] = ss_tri.A.G * edge1 + ss_tri.B.G * edge2 + ss_tri.C.G * edge3
                            self.screen[y][j][2] = ss_tri.A.B * edge1 + ss_tri.B.B * edge2 + ss_tri.C.B * edge3
                            self.sampleId_buffer[y][j] = self.tex_ids[i]
                            self.uv_buffer[y][j][0] = ss_tri.A.u * edge1 + ss_tri.B.u * edge2 + ss_tri.C.u * edge3
                            self.uv_buffer[y][j][1] = ss_tri.A.v * edge1 + ss_tri.B.v * edge2 + ss_tri.C.v * edge3

                            self.z_buffer[y][j][0] = z
                        
                    if (self.msaa == 2):
                        e0_1 += de0_dx1
                        e0_2 += de0_dx2
                        e0_3 += de0_dx3
                        e1_1 += de0_dx1
                        e1_2 += de0_dx2
                        e1_3 += de0_dx3
                    
                    edge1 += de_dx1
                    edge2 += de_dx2
                    edge3 += de_dx3
                
                if (self.msaa == 2):
                    e0_1_ini += de0_dy1
                    e0_2_ini += de0_dy2
                    e0_3_ini += de0_dy3
                    e1_1_ini += de0_dy1
                    e1_2_ini += de0_dy2
                    e1_3_ini += de0_dy3
                
                e_ini1 += de_dy1
                e_ini2 += de_dy2
                e_ini3 += de_dy3
                    
                    

    def showScreen(self):
        plt.imshow(np.clip(self.screen, 0.0, 1.0))
        plt.axis('off')
        plt.show()

    def saveScreen(self):
        #Save image
        img_unit8 = (self.screen * 255).astype(np.uint8)
        img = Image.fromarray(img_unit8)
        img.save('lossless.png', mode='RGB')