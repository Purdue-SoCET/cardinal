#ifndef RASTERIZER_H
#define RASTERIZER_H

#include <array>
#include <iostream>
#include <queue>

class Rasterizer {
private:
	std::queue<std::array<int, 3>> indices;
	int msaa;
public:

	void addTriangle(std::array<int, 3> tri);

	Rasterizer(int msaa = 0);

};

#endif