import numpy as np
from PIL import Image

class texture_unit():
    def __init__(self, textures):
        self.textures = textures



    def tex_map(self, uv, texture):
    
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
    
                     u_scaled = int(uv[row][col][0] *(tex_width-1))
                     v_scaled = int(uv[row][col][1] *(tex_height-1))
    
                     out[row][col] = current_texture[v_scaled][u_scaled]
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









