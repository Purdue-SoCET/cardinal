import math

import numpy as np
from PIL import Image
import os
import sys
from sympy import false


class texture_unit():
    def __init__(self, textures):
        self.textures = self.extract_textures(textures)





    def tex_map(self, uv, texture,gradient, filtering =0, mipmap = False):

        if (filter == 2 and not mipmap):
            print("Invalid argument combination")
            return

        # uv: len : h * w * 2, [0] = u, [1] = v
        #texture: len : h * w

        #values are row, column starting in top left

        out = np.zeros((uv.shape[0],uv.shape[1],3), dtype=np.float32)
        dfdx = gradient[0]
        dfdy = gradient[1]
        #iterating over every pixel in the screenspace
        for row in range(len(texture)):
            for col in range(len(texture[row])):


                if texture[row][col] != -1:
                    base_texture = self.textures[int(texture[row][col])][0]
                    base_width = base_texture.shape[1]
                    base_height = base_texture.shape[0]
                    if not mipmap:
                        u = uv[row][col][0] * (base_width - 1)
                        v = uv[row][col][1] * (base_height - 1)

                        if (filtering == 0):
                            out[row][col] = base_texture[int(v)][int(u)]
                        elif (filtering == 1):
                            out[row][col] = self.bilinear_filter(u,v,base_texture)
                    else:
                        # s_x and t_x (dfdx)
                        s_x = dfdx[row, col, 0] * base_width
                        t_x = dfdx[row, col, 1] * base_height

                        # s_y and t_y (dfdy)
                        s_y = dfdy[row, col, 0] * base_width
                        t_y = dfdy[row, col, 1] * base_height

                        j = math.sqrt(max(s_x ** 2 + t_x ** 2, s_y ** 2 + t_y ** 2))
                        if j > 0:
                            lod = max(math.log2(j), 0)
                        else:
                            lod = 0

                        #clamping lod to highest mip available
                        lod = min(lod,len(self.textures[int(texture[row][col])]) - 1)

                        current_texture = self.textures[int(texture[row][col])][lod.__round__()]
                        tex_width = current_texture.shape[1]
                        tex_height = current_texture.shape[0]
                        u = uv[row][col][0] * (tex_width - 1)
                        v = uv[row][col][1] * (tex_height - 1)
                        if (filtering == 0):
                            out[row][col] = current_texture[int(v)][int(u)]
                        elif (filtering == 1):
                            out[row][col] = self.bilinear_filter(u,v,current_texture)
                        elif (filtering == 2):
                            f = (j - 2**math.floor(lod))/2**(math.floor(lod)) #trilinear interpolation fraction

                            lo = int(math.floor(lod))
                            hi = min(math.ceil(lod),len(self.textures[int(texture[row][col])]) - 1)
                            lo_tex = self.textures[int(texture[row][col])][lo]
                            hi_tex = self.textures[int(texture[row][col])][hi]

                            u_lo = uv[row][col][0] * (lo_tex.shape[1] - 1)
                            v_lo = uv[row][col][1] * (lo_tex.shape[0] - 1)

                            u_hi = uv[row][col][0] * (hi_tex.shape[1] - 1)
                            v_hi = uv[row][col][1] * (hi_tex.shape[0] - 1)


                            lo_bilinear = self.bilinear_filter(u_lo,v_lo,lo_tex)
                            hi_bilinear = self.bilinear_filter(u_hi, v_hi, hi_tex)
                            out[row][col] = lo_bilinear * (1-f) + hi_bilinear * (f)







        return out


    #in the future, this should be implemented to not pull every texture immediately (to better mimic hardware)
    def extract_textures(self, tex_names):

        all_textures = []
        for tex in tex_names:
            tex_dir = os.path.join("textures", tex)
            current_texture_mipmaps = []

            mipmap_index = 0
            while True:
                filepath = os.path.join(tex_dir, f"mip_{mipmap_index}.png")

                if not os.path.exists(filepath):
                    break
                image = Image.open(filepath)
                image_array = np.array(image)[:, :, :3]
                image_array = image_array / 255.0
                current_texture_mipmaps.append(image_array)
                mipmap_index += 1
            all_textures.append(current_texture_mipmaps)
        return all_textures

    def bilinear_filter(self, u,v, texture):

        u1 = int(np.floor(u))
        v1 = int(np.floor(v))
        u2 = int(np.ceil(u))
        v2 = int(np.ceil(v))

        du = u - u1
        dv = v - v1

        # weight of each pixel used
        w11 = (1 - du) * (1 - dv)
        w12 = du * (1 - dv)
        w21 = (1 - du) * dv
        w22 = du * dv

        # collect colors for each of four points
        Q11 = texture[v1][u1]
        Q12 = texture[v1][u2]
        Q21 = texture[v2][u1]
        Q22 = texture[v2][u2]

        r = (Q11[0] * w11) + (Q21[0] * w21) + (Q12[0] * w12) + (Q22[0] * w22)
        g = (Q11[1] * w11) + (Q21[1] * w21) + (Q12[1] * w12) + (Q22[1] * w22)
        b = (Q11[2] * w11) + (Q21[2] * w21) + (Q12[2] * w12) + (Q22[2] * w22)

        return np.array([r, g, b])


















    # def tex_map(self, uv, texture, filtering =0, mipmap = False):
    #
    #     # uv: len : h * w * 2, [0] = u, [1] = v
    #     #texture: len : h * w
    #
    #     #values are row, column starting in top left
    #
    #     out = np.zeros((uv.shape[0],uv.shape[1],3), dtype=np.float32)
    #
    #     for row in range(len(texture)):
    #         for col in range(len(texture[row])):
    #
    #             if texture[row][col] != -1:
    #                 current_texture = self.textures[int(texture[row][col]-1)]
    #                 tex_width = current_texture.shape[1]
    #                 tex_height = current_texture.shape[0]
    #                 u = uv[row][col][0] * (tex_width - 1)
    #                 v = uv[row][col][1] * (tex_height - 1)
    #
    #                 if (filtering == 0):
    #                     out[row][col] = current_texture[int(v)][int(u)]
    #                 elif (filtering == 1):
    #                     u1 = int(np.floor(uv[row][col][0] * (tex_width - 1)))
    #                     v1 = int(np.floor(uv[row][col][1] * (tex_height - 1)))
    #                     u2 = int(np.ceil(uv[row][col][0] * (tex_width - 1)))
    #                     v2 = int(np.ceil(uv[row][col][1] * (tex_height - 1)))
    #
    #                     du = u - u1
    #                     dv = v - v1
    #
    #                     #weight of each pixel used
    #                     w11 = (1 - du) * (1 - dv)
    #                     w12 = du * (1 - dv)
    #                     w21 = (1-du) * dv
    #                     w22 = du * dv
    #
    #                     #collect colors for each of four points
    #                     Q11 = current_texture[v1][u1]
    #                     Q12 = current_texture[v1][u2]
    #                     Q21 = current_texture[v2][u1]
    #                     Q22 = current_texture[v2][u2]
    #
    #                     r = (Q11[0] * w11) + (Q21[0] * w21) + (Q12[0] * w12) + (Q22[0] * w22)
    #                     g = (Q11[1] * w11) + (Q21[1] * w21) + (Q12[1] * w12) + (Q22[1] * w22)
    #                     b = (Q11[2] * w11) + (Q21[2] * w21) + (Q12[2] * w12) + (Q22[2] * w22)
    #
    #                     out[row][col] = np.array([r,g,b])
    #
    #     return out
    #












