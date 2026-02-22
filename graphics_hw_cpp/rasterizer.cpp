#include "rasterizer.hpp"
#include "vector_table.hpp"


Fetch::Fetch() {}

void Fetch::addTriangle(std::array<int, 3> tri) {
	this->indices.push(tri);
}

std::array<std::array<int, 3>, 2> Fetch::forward() {
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

void BoundingBox::addTriangle(std::array<int, 3> tri) {
	this->indices.push(tri);
}

void BoundingBox::forward(VectorTable* table) {
	std::array<std::array<int, 3>, 2> out;
	if (!this->indices.empty()) {
		out[0] = this->indices.front();
		this->indices.pop();
	}
	else {
		return;
	}

	if (!this->indices.empty()) {
		out[1] = this->indices.front();
		this->indices.pop();
	}
	else {
		return;
	}

	Triangle tri0 = table->getTriangle(out[0]);
	Triangle tri1 = table->getTriangle(out[1]);


	f16Vector2 min0 = tri0.getMin();
	f16Vector2 max0 = tri0.getMax();

	f16Vector2 min1 = tri1.getMin();
	f16Vector2 max1 = tri1.getMax();

	std::array<f16Vector2, 2> t0;
	std::array<f16Vector2, 2> t1;
	
	t0[0] = min0;
	t0[1] = max0;

	t1[0] = min1;
	t1[1] = max1;

	this->bounding_box.push({t0,t1});
}

std::array<std::array<f16Vector2, 2>, 2> BoundingBox::getBB() {
	std::array<std::array<f16Vector2, 2>, 2> out = this->bounding_box.front();
	this->bounding_box.pop();
	return out;
}

Dispatch::Dispatch() {}


PreEdge::PreEdge() {}


EdgeTest::EdgeTest() {}