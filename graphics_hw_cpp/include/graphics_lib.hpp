#ifndef GRAPHICS_LIB_H
#define GRAPHICS_LIB_H

#include <array>
#include <iostream>
#include "half.hpp"
using half_float::half;
using namespace half_float::literal;

const half HALF_MAX = std::numeric_limits<half_float::half>::max();
const half HALF_MIN = std::numeric_limits<half_float::half>::lowest();

struct f16Vector2 {
	half x, y;

	f16Vector2(half_float::half x = 0.0_h, half_float::half y = 0.0_h) :
		x(x), y(y) {}

	f16Vector2 operator-(const f16Vector2 &v) {
		return f16Vector2{x - v.x, y - v.y};
	}

	void print() {
		std::cout << "(" << x << ", " << y << ")\n";
	}
};

struct fVector3 {
	float x, y, z;

	fVector3(float x = 0, float y = 0, float z = 0) :
		x(x), y(y), z(z) {}

	fVector3 operator-(const fVector3 &v) {
		return fVector3{x - v.x, y - v.y, z - v.z};
	}

	f16Vector2 toVec2f16() {
		return f16Vector2{half(x), half(y)};
	}

	void print() {
		std::cout << "(" << x << ", " << y << ", " << z << ")\n";
	}
};

struct Vertex{
	float u, v;
	std::array<int, 3> color;
	fVector3 point;
	f16Vector2 screenSpacePoint;

	Vertex(fVector3 point = fVector3{}, float u = -1, float v = -1, std::array<int, 3> c = { -1,-1,-1 }) :
		point(point), u(u), v(v), color(c) {}

	Vertex* floor() {
		point.x = std::floor(point.x);
		point.y = std::floor(point.y);
		return this;
	}

	Vertex* ceil() {
		point.x = std::ceil(point.x);
		point.y = std::ceil(point.y);
		return this;
	}

	void setScreenSpacePoint(f16Vector2 half_point) {
		this->screenSpacePoint = half_point;
	}
};

struct Triangle {
	Vertex A, B, C;
	std::array<Vertex, 3> vertices = { this->A, this->B, this->C };

	void update() {
		this->vertices = { this->A, this->B, this->C };
	}

	f16Vector2 getMin() {
		half minX = HALF_MAX;
		half minY = HALF_MAX;
		for (int i = 0; i < 3; i++) {
			half currX = this->vertices[i].screenSpacePoint.x;
			half currY = this->vertices[i].screenSpacePoint.y;

			if (currX < minX) minX = currX;
			if (currY < minY) minY = currY;
		}

		return f16Vector2(minX, minY);
	}

	f16Vector2 getMax() {
		half maxX = HALF_MIN;
		half maxY = HALF_MIN;
		for (int i = 0; i < 3; i++) {
			half currX = this->vertices[i].screenSpacePoint.x;
			half currY = this->vertices[i].screenSpacePoint.y;

			if (currX > maxX) maxX = currX;
			if (currY > maxY) maxY = currY;
		}

		return f16Vector2(maxX, maxY);
	}

	Triangle(Vertex A = Vertex{}, Vertex B = Vertex{}, Vertex C = Vertex{}) :
		A(A), B(B), C(C) {}

	Triangle(std::array<Vertex, 3> tri) :
		A(tri[0]), B(tri[1]), C(tri[2]) {}
};

class Projector {
private:
	int width;
	int height;
	int nearPlane;
	int farPlane;
	float aspect;
public:
	void toNearPlane(Triangle* tri);
	void toNDC(Triangle* tri);
	void depth(Triangle* tri);
	void toScreenSpace(Triangle* tri);

	Projector(int w = 1280, int h = 720, int nearPlane = 1, int farPlane = 10);

};

#endif // !graphics_lib.h
