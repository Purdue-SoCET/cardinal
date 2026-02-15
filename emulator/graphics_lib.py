import numpy as np
from math import floor, ceil

class Vec3:
    def __init__(self, x = 0.0, y = 0.0, z = 0.0):
        self.x = x
        self.y = y
        self.z = z
        self.vector = np.array([self.x,self.y,self.z])
    
    def __sub__(self, other):
        res = self.vector - other.vector
        return Vec3(res[0], res[1], res[2])
    
    def __str__(self):
        return f"[{self.x},{self.y},{self.z}]"
    
    def floor(self):
        self.x = floor(self.x)
        self.y = floor(self.y)
        return self

    def getP(self):
        return self

    def ceil(self):
        self.x = ceil(self.x)
        self.y = ceil(self.y)
        return self

class Vertex(Vec3):
    def __init__(self, x = 0.0, y = 0.0, z = 0.0, color= [0, 0, 0], u = 0.0, v = 0.0):
        super().__init__(x, y, z)
        self.R = color[0]
        self.G = color[1]
        self.B = color[2]
        self.u = u
        self.v = v
        self.color = color

class Triangle:
    def __init__(self, A : Vertex, B : Vertex, C : Vertex):
        self.A = A
        self.B = B
        self.C = C
        self.triangle = [self.A, self.B, self.C]
        self.bb = [[],[]]
    
    #Note how max and min are flipped here for the z direction. The z axis is the axis the camera looks down. Everything in front of the camera is a -ve z value. So, the z value closest to the camera is the max, not the min.
    def min(self):
        self.bb[0] = Vec3(min(vert.x for vert in self.triangle), min(vert.y for vert in self.triangle), max(vert.z for vert in self.triangle))
        return self.bb[0]
    def max(self):
        self.bb[1] = Vec3(max(vert.x for vert in self.triangle), max(vert.y for vert in self.triangle), min(vert.z for vert in self.triangle))
        return self.bb[1]
    

class Projector:
    def __init__(self, width, height, near, far):
        self.width = width
        self.height = height
        self.near = near
        self.far = far
        self.aspect = width / height
    
    def toNearPlane(self, point : Vertex):
        return Vertex((point.x * self.near) / (-point.z), (point.y * self.near) / (-point.z), point.z, point.color)
    def toNDC(self, point : Vertex):
        return Vertex(point.x / (self.near * self.aspect), point.y / self.near, point.z, point.color)
    def depth(self, point : Vertex):
        z = point.z
        point.z = (-(self.far + self.near) / (self.far - self.near)*z) - (2*self.far*self.near / (self.near - self.far))
        return point.z
    
    def toScreenSpace(self, ndc : Vertex):
        x_ndc = ndc.x
        y_ndc = ndc.y

        x_pixel = (x_ndc + 1) * 0.5 * self.width
        y_pixel = (1 - y_ndc) * 0.5 * self.height

        return Vertex(x_pixel, y_pixel, ndc.z, ndc.color)