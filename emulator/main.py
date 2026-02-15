from rasterizer import Rasterizer
from time import perf_counter

'''
v0 = (-0.8, -0.8, -2)  # bottom left
v1 = ( 0.8, -0.8, -2)  # bottom right
v2 = ( 0.8,  0.8, -2)  # top right
v3 = (-0.8,  0.8, -2)  # top left

# Colors per corner
c0 = [1,0,0]  # red
c1 = [0,1,0]  # green
c2 = [0,0,1]  # blue
c3 = [1,1,1]  # white

vx1 = [v0[0], v1[0]]
vy1 = [v0[1], v1[1]]
vz1 = [v0[2], v1[2]]

vx2 = [v1[0], v3[0]]
vy2 = [v1[1], v3[1]]
vz2 = [v1[2], v3[2]]

vx3 = [v3[0], v2[0]]
vy3 = [v3[1], v2[1]]
vz3 = [v3[2], v2[2]]

col1 = [c0, c1]
col2 = [c1, c3]
col3 = [c3, c2]
'''

#I recommend sticking to this test case. It's relatively simple while also testing z and top left rule well enough.
#The test above is extremely strict for msaa, even hardware is expected to fail it at lower resolutions with msaa. Use at your own discretion.

vx1 = [-0.8, -1.4, 0.8]
vy1 = [-0.6, -0.4, -0.6]
vz1  = [-2,   -2,   -2]

vx2 = [0.8, -0.8, 1.4]
vy2 = [-0.6, -0.6, 0.4]
vz2  = [-2,   -2,   -2]

vx3 = [0.0, 0.0, -0.4]
vy3 = [0.6, 0.6, 1]
vz3  = [-2,  -2,  -3]

col1 = [[1,0,0], [0,0,1], [1,1,1]]
col2 = [[0,1,0], [0,1,0], [1,1,1]]
col3 = [[0,0,1], [1,0,0], [1,1,1]]


'''
Invalid state is what indicates that that pixel wasn't touched.

General:
h = height of screen
w = width of screen

WHAT YOU NEED TO PASS ON INSTANTIATION:

------------------------------------------------------
tex_id -> list with sampleID or sample string for intended texture you will be using. This will be used to 
generate an array the size of the screen, with each element containing the sample you should use at that pixel.

len : number of triangles
invalid state : -1

triangles can share same samples.
------------------------------------------------------
u -> list of list with u values for each vertex for each triangle. This will be used to generate your uv buffer. 

len_outer : number of triangles
len_inner : 3
------------------------------------------------------
v -> list of list with v values for each vertex for each triangle. This will be used to generate your uv buffer. 

len_outer : number of triangles
len_inner : 3
invalid state : np.nan // use (np.isfinite(u) and np.isfinite(v)) to check if valid.
------------------------------------------------------


WHAT FUNCTIONS YOU NEED TO CALL TO GET WHAT YOU NEED FOR TMU:
ONLY CALL THESE AFTER YOU HAVE RUN rasterEngine.render()

------------------------------------------------------
rasterEngine.getUV() -> Returns uv buffer. Each element is uv at that pixel such that [0] = u, [1] = v.

len : h * w * 2, [0] = u, [1] = v

invalid state : np.nan // use (np.isfinite(u) and np.isfinite(v)) to check if valid. 
If it is not valid that means none of the triangles touched that pixel.
------------------------------------------------------
rasterEngine.getSamples() -> Returns sample buffer. Each element is the sample that owns that pixel.

len : h * w

invalid state : -1
If it is not valid that means none of the triangles own that pixel.
------------------------------------------------------

**IMPORTANT** rasterEngine.showScreen() will NOT show you your textures yet.
------------------------------------------------------
rasterEngine.applyTextures(newRGB) -> Returns void. Updates screen with texture RGB sampled values you provide.

expected argument : np.array((h, w, 3))
len : void

invalid state : NA
------------------------------------------------------

After running above you can run rasterEngine.showScreen() and it will show you your image with the texture map applied. 
'''

rasterEngine = Rasterizer(
    vx1, vy1, vz1,
    vx2, vy2, vz2,
    vx3, vy3, vz3,
    col1, col2, col3
) #defaults to 720p, msaa = 0, near = 1, far = 10

start = perf_counter()
rasterEngine.render()
end = perf_counter()

print("Time to render:", end - start)

rasterEngine.showScreen()