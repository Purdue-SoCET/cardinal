#include "graphics_lib.h"

class Projector {
private:
	int width;
	int height;
	int nearPlane;
	int farPlane;
	float aspect;
public:
	void toNearPlane(Triangle* tri) {
		std::array<Vertex*, 3> vertices = { &tri->A, &tri->B, &tri->C };

		for (int i = 0; i < 3; i++) {
			float x = vertices[i]->point.x;
			float y = vertices[i]->point.y;
			float z = vertices[i]->point.z;

			vertices[i]->point.x = (x * nearPlane) / (-z);
			vertices[i]->point.y = (y * nearPlane) / (-z);
		}
	}
	void toNDC(Triangle* tri) {
		std::array<Vertex*, 3> vertices = { &tri->A, &tri->B, &tri->C };

		for (int i = 0; i < 3; i++) {
			float x = vertices[i]->point.x;
			float y = vertices[i]->point.y;

			vertices[i]->point.x = x / (nearPlane * aspect);
			vertices[i]->point.y = y / nearPlane;
		}
	}
	void depth(Triangle* tri) {
		std::array<Vertex*, 3> vertices = { &tri->A, &tri->B, &tri->C };

		for (int i = 0; i < 3; i++) {
			float z = vertices[i]->point.z;

			vertices[i]->point.z = (-(farPlane + nearPlane) / ((farPlane - nearPlane) * z)) - ((2 * nearPlane * farPlane) / (farPlane - nearPlane));
		}
	}
	void toScreenSpace(Triangle* tri) {
		std::array<Vertex*, 3> vertices = { &tri->A, &tri->B, &tri->C };

		for (int i = 0; i < 3; i++) {
			f16Vector2 ndc = vertices[i]->point.toVec2f16();

			ndc.x = (ndc.x + 1) * 0.5 * width;
			ndc.y = (1 - ndc.y) * 0.5 * height;

			vertices[i]->setScreenSpacePoint(ndc);
		}
	}

	Projector(int w = 1280, int h = 720, int nearPlane = 1, int farPlane = 10) {
		this->width = w;
		this->nearPlane = nearPlane;
		this->height = h;
		this->farPlane = farPlane;
		this->aspect = float(w) / float(h);
	}

};