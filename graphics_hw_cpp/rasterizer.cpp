#include "rasterizer.h"

void Rasterizer::addTriangle(std::array<int, 3> tri) {
	this->indices.push(tri);
}

Rasterizer::Rasterizer(int msaa) {
	this->msaa = msaa;
}