#ifndef graphics_lib.h

#include <array>

struct Vector3 {
	float x, y, z;
};

struct Vertex{
	float x, y, z, u, v;
	std::array<int, 3> color;

	Vertex(float x = 0, float y = 0, float z = 0, float u = -1, float v = -1, std::array<int, 3> c = {-1,-1,-1}) :
		x(x), y(y), z(z), u(u), v(v), color(c) {}
};

#endif // !graphics_lib.h
