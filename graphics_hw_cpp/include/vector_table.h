#ifndef VECTOR_TABLE_H
#define VECTOR_TABLE_H

#include <array>
#include "graphics_lib.h"

class VectorTable {
private:
	int maxSize;
	Vertex* table = NULL;
public:

	Triangle getTriangle(std::array<int, 3> indices);
	int addVertex(Vertex vertex);
	void invalidateVertex(int handle);
	Vertex* makeTable(int maxSize);

	VectorTable(int maxSize = 48);

};

#endif