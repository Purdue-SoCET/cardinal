#ifndef RASTERIZER_H
#define RASTERIZER_H

#include <array>
#include <iostream>
#include <queue>

class Fetch {
private:
	std::queue<std::array<int, 3>> indices;
public:

	void addTriangle(std::array<int, 3> tri);
	std::array<std::array<int, 3>, 2> forward(std::array<int, 3> tri);

	Fetch();

};

class BoundingBox {
private:
	std::queue<std::array<int, 3>> indices;
public:

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