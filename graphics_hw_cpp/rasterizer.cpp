#include "rasterizer.h"


Fetch::Fetch() {}

void Fetch::addTriangle(std::array<int, 3> tri) {
	this->indices.push(tri);
}

std::array<std::array<int, 3>, 2> Fetch::forward(std::array<int, 3> tri) {
	this->addTriangle(tri);

	std::array<std::array<int, 3>, 2> out;
	if (!this->indices.empty()) {
		out[0] = this->indices.front();
		this->indices.pop();
	}
	else {
		out[0] = { -1,-1,-1 };
		out[1] = { -1,-1,-1 };
		return out;
	}

	if (!this->indices.empty()) {
		out[1] = this->indices.front();
		this->indices.pop();
	}
	else {
		out[0] = { -1,-1,-1 };
		out[1] = { -1,-1,-1 };
		return out;
	}

	return out;
}


BoundingBox::BoundingBox() {}


Dispatch::Dispatch() {}


PreEdge::PreEdge() {}


EdgeTest::EdgeTest() {}