import numpy as np
from PIL import Image

class texture_unit():
    def __init__(self, textures):
        self.textures = textures



    def tex_map(self, uv, texture, mode =0):

        # uv: len : h * w * 2, [0] = u, [1] = v
        #texture: len : h * w

        #values are row, column starting in top left

        out = np.zeros((uv.shape[0],uv.shape[1],3), dtype=np.float32)

        for row in range(len(texture)):
            for col in range(len(texture[row])):

                if texture[row][col] != -1:
                    current_texture = self.textures[int(texture[row][col]-1)]
                    tex_width = current_texture.shape[1]
                    tex_height = current_texture.shape[0]
                    u = uv[row][col][0] * (tex_width - 1)
                    v = uv[row][col][1] * (tex_height - 1)

                    if (mode == 0):
                        out[row][col] = current_texture[int(v)][int(u)]
                    elif (mode == 1):
                        u1 = int(np.floor(uv[row][col][0] * (tex_width - 1)))
                        v1 = int(np.floor(uv[row][col][1] * (tex_height - 1)))
                        u2 = int(np.ceil(uv[row][col][0] * (tex_width - 1)))
                        v2 = int(np.ceil(uv[row][col][1] * (tex_height - 1)))

                        du = u - u1
                        dv = v - v1

                        #weight of each pixel used
                        w11 = (1 - du) * (1 - dv)
                        w12 = du * (1 - dv)
                        w21 = (1-du) * dv
                        w22 = du * dv

                        #collect colors for each of four points
                        Q11 = current_texture[v1][u1]
                        Q12 = current_texture[v1][u2]
                        Q21 = current_texture[v2][u1]
                        Q22 = current_texture[v2][u2]

                        r = (Q11[0] * w11) + (Q21[0] * w21) + (Q12[0] * w12) + (Q22[0] * w22)
                        g = (Q11[1] * w11) + (Q21[1] * w21) + (Q12[1] * w12) + (Q22[1] * w22)
                        b = (Q11[2] * w11) + (Q21[2] * w21) + (Q12[2] * w12) + (Q22[2] * w22)

                        out[row][col] = np.array([r,g,b])




        return out
    






    # def tex_map(self, uv, texture,mode = 0):

    #     # uv: len : h * w * 2, [0] = u, [1] = v
    #     #texture: len : h * w

    #     #values are row, column starting in top left

    #     out = np.zeros((uv.shape[0],uv.shape[1],3), dtype=np.float32)


    #     for i in range(len(self.textures)):
    #         current_texture = self.textures[i]
    #         tex_width = current_texture.shape[1]
    #         tex_height = current_texture.shape[0]

    #         mask = (texture == i+1)

    #         #extract masked uvs
    #         uv_masked = uv[mask]

    #         if mode == 0:
    #             u_scaled = (np.round(uv_masked[:, 0] * (tex_width - 1))).astype(int)
    #             v_scaled = (np.round(uv_masked[:, 1] * (tex_height - 1))).astype(int)
    #             out[mask] = current_texture[v_scaled,u_scaled]

    #         if mode == 1:
    #             u_floor = (np.floor(uv_masked[:, 0] * (tex_width - 1))).astype(int)
    #             v_floor = (np.floor(uv_masked[:, 1] * (tex_height - 1))).astype(int)
    #             u_ceil = (np.ceil(uv_masked[:, 0] * (tex_width - 1))).astype(int)
    #             v_ceil = (np.ceil(uv_masked[:, 1] * (tex_height - 1))).astype(int)

    #             out[mask] = (current_texture[v_floor,u_floor] + current_texture[v_ceil,u_ceil] +
    #                         current_texture[v_floor,u_ceil] + current_texture[v_ceil,u_floor])/4



    #     return out








        # for row in range(len(texture)):
        #     for col in range(len(texture[row])):
        #
        #         if texture[row][col] != -1:
        #             current_texture = self.textures[int(texture[row][col]-1)]
        #             tex_width = current_texture.shape[1]
        #             tex_height = current_texture.shape[0]
        #
        #             u_scaled = int(uv[row][col][0] *(tex_width-1))
        #             v_scaled = int(uv[row][col][1] *(tex_height-1))
        #
        #             out[row][col] = current_texture[v_scaled][u_scaled]
        # return out









