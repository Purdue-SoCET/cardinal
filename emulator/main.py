from rasterizer import Rasterizer
from time import perf_counter


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

rasterEngine = Rasterizer(
    vx1, vy1, vz1,
    vx2, vy2, vz2,
    vx3, vy3, vz3,
    col1, col2, col3,
    msaa=2
) #defaults to 720p

start = perf_counter()
rasterEngine.render()
end = perf_counter()

print("Time to render:", end - start)

rasterEngine.showScreen()