#ifndef RASTERIZER_H
#define RASTERIZER_H

#include <array>
#include <iostream>
#include <queue>
#include "vector_table.hpp"
#include "hardware_lib.hpp"

class Fetch {
private:
	std::queue<std::array<int, 3>> indices;
	Clock* clk;
public:

	std::array<std::array<int, 3>, 2> forward(Status* FE_BB, std::array<std::array<int, 3>, 2> batch);
	void comb(Status* FE_BB, std::array<int, 3> tri);

	Fetch(Clock* clk);

};

class BoundingBox {
private:
	std::queue<std::array<int, 3>> indices;
	std::queue<std::array<std::array<f16Vector2, 2>, 2>> bounding_box;
	Clock* clk;
public:

	std::array<std::array<int, 3>, 2> forward(Status* BB_DP, Status* FE_BB, std::array<std::array<int, 3>, 2> batch);
	void comb(Status* FE_BB, std::array<std::array<int, 3>, 2> tris, VectorTable* table);
	std::array<std::array<f16Vector2, 2>, 2> getBB();

	BoundingBox(Clock* clk);

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