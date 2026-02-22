#ifndef RASTERIZER_H
#define RASTERIZER_H

#include <array>
#include <iostream>
#include <queue>
#include "vector_table.hpp"

class Fetch {
private:
	std::queue<std::array<int, 3>> indices;
public:

	void addTriangle(std::array<int, 3> tri);
	std::array<std::array<int, 3>, 2> forward();

	Fetch();

};

class BoundingBox {
private:
	std::queue<std::array<int, 3>> indices;
	std::queue<std::array<std::array<f16Vector2, 2>, 2>> bounding_box;
public:

	void addTriangle(std::array<int, 3> tri);
	void forward(VectorTable* table);
	std::array<std::array<f16Vector2, 2>, 2> getBB();

	BoundingBox();

};

class Dispatch {
private:
	std::queue<std::array<int, 3>> indices;
public:

	Dispatch();

};

class PreEdge {
private:
	std::queue<std::array<int, 3>> indices;
public:

	PreEdge();

};

class EdgeTest {
private:
	std::queue<std::array<int, 3>> indices;
public:

	EdgeTest();

};

#endif