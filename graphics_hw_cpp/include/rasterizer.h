#ifndef RASTERIZER_H

#include <array>
#include <iostream>
#include <queue>

class Rasterizer {
private:
	std::queue<int> indices;
public:

	void addTriangle(std::array<int, 3> tri);

	Rasterizer(int msaa = 0, int w = 1280, int h = 720, int nearPlane = 1, int farPlane = 10);
};

#endif