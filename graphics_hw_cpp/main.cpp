#include "graphics_lib.hpp"
#include "vector_table.hpp"
#include "rasterizer.hpp"
#include <vector>

using namespace std;

int main()
{
	//---------- TRIANGLE SETUP ----------
	fVector3 point1{ -0.8f, 0.6f, -2.0f };
	fVector3 point2{ 0.8f, 0.6f, -2.0f };
	fVector3 point3{ 0.0f, -0.6f, -5.0f };
	fVector3 point4{ -0.8f, 0.6f, -2.0f };
	fVector3 point5{ 0.8f, 0.6f, -2.0f };


	Vertex v1{ point1 };
	Vertex v2{ point2 };
	Vertex v3{ point3 };
	Vertex v4{ point4 };
	Vertex v5{ point5 };

	v1.color = {255,0,0};
	v2.color = { 255,0,0 };
	v3.color = { 255,0,0 };
	v4.color = { 255,0,0 };
	v5.color = { 255,0,0 };

	int numTri = 2;
	Triangle t1{ v1, v2, v3 };
	Triangle t2{ v4, v5, v3 };

	std::vector<Triangle> tris;
	tris.push_back(t1);
	tris.push_back(t2);

	std::vector<std::array<int, 3>> indexBatches;

	Projector projector{};
	VectorTable vector_table = VectorTable(48);

	for (int i = 0; i < numTri; i++) { //Triangle loop.
		projector.toNearPlane(&tris[i]);
		projector.toNDC(&tris[i]);
		projector.toScreenSpace(&tris[i]);
		projector.depth(&tris[i]);
		tris[i].update(); //Make sure updated A B C vertices reflect everywhere in struct.

		std::array<int, 3> indices;
		for (int j = 0; j < 3; j++) { //Vertices loop for table setup.
			indices[j] = vector_table.addVertex(tris[i].vertices[j]);
		}
		indexBatches.push_back(indices);
	}

	//---------- FETCH ----------
	Fetch fetch = Fetch();
	for (int i = 0; i < numTri; i++) { //Add triangles to queue.
		fetch.addTriangle(indexBatches[i]);
	}
	for (int i = 0; i < numTri; i++) { //Clear queue
		indexBatches.pop_back();
	}

	std::array<std::array<int, 3>, 2> batch = fetch.forward(); //Forward stage.
	indexBatches.push_back(batch[0]);
	indexBatches.push_back(batch[1]);

	//---------- BOUNDING BOX ----------
	BoundingBox bounding_box = BoundingBox();
	for (int i = 0; i < numTri; i++) { //Add triangles to queue.
		bounding_box.addTriangle(indexBatches[i]);
	}

	bounding_box.forward(&vector_table); //Forward bounding box stage. Will calculate bounding boxes.

	//---------- DEBUG ----------
	indexBatches.pop_back();
	indexBatches.pop_back();
	std::array<std::array<f16Vector2, 2>, 2> bb_batch = bounding_box.getBB();

	bb_batch[0][0].print(); //From triangle 1 get min.
	bb_batch[0][1].print(); //From triangle 1 get max.

	bb_batch[1][0].print(); //From triangle 2 get min.
	bb_batch[1][1].print(); //From triangle 2 get max.

	return 0;
}
