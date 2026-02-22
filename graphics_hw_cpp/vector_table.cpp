#include "vector_table.hpp"
#include "graphics_lib.hpp"

VectorTable::VectorTable(int maxSize) {
	this->maxSize = maxSize;
	this->table = this->makeTable(maxSize);
}

int VectorTable::addVertex(Vertex vertex) {
	for (int i = 0; i < this->maxSize; i++) {
		if (this->table[i].color[0] == -1) { //Color -1 means invalid vertex always.
			this->table[i] = vertex;
			return i;
		}
	}

	return -1;
}

Vertex* VectorTable::makeTable(int maxSize) {
	return new Vertex[maxSize]{};
}

void VectorTable::invalidateVertex(int handle) {
	this->table[handle] = Vertex{};
}

Triangle VectorTable::getTriangle(std::array<int16_t, 3> indices) {
	std::array<Vertex, 3> tri;

	for (int i = 0; i < 3; i++) {
		if (this->table[indices[i]].color[0] == -1) {
			return Triangle{};
		}
		else {
			tri[i] = this->table[indices[i]];
		}
		
	}

	return Triangle(tri);
}

VectorTable::~VectorTable() {
	delete[] this->table; // Free the memory when the class is destroyed
}