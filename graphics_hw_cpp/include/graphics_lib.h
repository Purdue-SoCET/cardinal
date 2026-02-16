#ifndef graphics_lib.h

#include <array>
#include <iostream>
#include "half.hpp"
using half_float::half;
using namespace half_float::literal;

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

	Vertex(fVector3 point, float u = -1, float v = -1, std::array<int, 3> c = { -1,-1,-1 }) :
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

	Triangle(Vertex A, Vertex B, Vertex C) :
		A(A), B(B), C(C) {}
};

class Projector {
private:
	int width;
	int height;
	int near;
	int far;
	float aspect;
public:
	void toNearPlane(Triangle* tri) {
		std::array<Vertex*, 3> vertices = { &tri->A, &tri->B, &tri->C };

		for (int i = 0; i < 3; i++) {
			float x = vertices[i]->point.x;
			float y = vertices[i]->point.y;
			float z = vertices[i]->point.z;

			vertices[i]->point.x = (x * near) / (-z);
			vertices[i]->point.y = (y * near) / (-z);
		}
	}
	void toNDC(Triangle* tri) {
		std::array<Vertex*, 3> vertices = { &tri->A, &tri->B, &tri->C };

		for (int i = 0; i < 3; i++) {
			float x = vertices[i]->point.x;
			float y = vertices[i]->point.y;

			vertices[i]->point.x = x / (near * aspect);
			vertices[i]->point.y = y / near;
		}
	}
	void depth(Triangle* tri) {
		std::array<Vertex*, 3> vertices = { &tri->A, &tri->B, &tri->C };

		for (int i = 0; i < 3; i++) {
			float z = vertices[i]->point.z;

			vertices[i]->point.z = (-(far + near) / ((far - near) * z)) - ((2 * near * far) / (near - far));
		}
	}
	void toScreenSpace(Triangle* tri) {
		std::array<Vertex*, 3> vertices = { &tri->A, &tri->B, &tri->C };

		for (int i = 0; i < 3; i++) {
			f16Vector2 ndc = vertices[i]->point.toVec2f16();

			ndc.x = (ndc.x + 1) * 0.5 * width;
			ndc.y = (ndc.y + 1) * 0.5 * height;

			vertices[i]->setScreenSpacePoint(ndc);
		}
	}

	Projector(int w = 1280, int h = 720, int near = 1, int far = 10) {
		this->width = w;
		this->near = near;
		this->height = h;
		this->far = far;
		this->aspect = float(w) / float(h);
	}

};

#endif // !graphics_lib.h
