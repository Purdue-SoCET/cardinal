#include "graphics_lib.hpp"
#include "vector_table.hpp"
#include "rasterizer.hpp"
#include "hardware_lib.hpp"
#include <vector>
#include <chrono>

using namespace std;

int main()
{
	//---------- TRIANGLE SETUP (FRONT-END) ----------
	fVector3 point1{ -0.8f, 0.6f, -2.0f };
	fVector3 point2{ 0.8f, 0.6f, -2.0f };
	fVector3 point3{ 0.0f, -0.6f, -5.0f };
	fVector3 point4{ -1.0f, 0.4f, -3.0f };
	fVector3 point5{ 0.8f, 0.6f, -2.0f };
	fVector3 point6{ 1.0f, -0.6f, -5.0f };
	fVector3 point7{ -0.8f, 0.6f, -2.0f };
	fVector3 point8{ -0.1f, 0.5f, -2.0f };
	fVector3 point9{ 0.0f, -0.6f, -5.0f };
	fVector3 point10{ -0.8f, 0.6f, -2.0f };
	fVector3 point11{ 0.8f, 0.6f, -2.0f };


	Vertex v1{ point1 };
	Vertex v2{ point2 };
	Vertex v3{ point3 };
	Vertex v4{ point4 };
	Vertex v5{ point5 };
	Vertex v6{ point6 };
	Vertex v7{ point7 };
	Vertex v8{ point8 };
	Vertex v9{ point9 };
	Vertex v10{ point10 };
	Vertex v11{ point11 };

	v1.color = {255,0,0};
	v2.color = { 255,0,0 };
	v3.color = { 255,0,0 };
	v4.color = { 255,0,0 };
	v5.color = { 255,0,0 };
	v6.color = { 255,0,0 };
	v7.color = { 255,0,0 };
	v8.color = { 255,0,0 };
	v9.color = { 255,0,0 };
	v10.color = { 255,0,0 };
	v11.color = { 255,0,0 };

	int numTri = 4;
	Triangle t1{ v1, v2, v3 };
	Triangle t2{ v4, v5, v3 };
	Triangle t3{ v6, v7, v8 };
	Triangle t4{ v10, v9, v11 };

	std::vector<Triangle> tris;
	tris.push_back(t1);
	tris.push_back(t2);
	tris.push_back(t3);
	tris.push_back(t4);

	std::queue<primIndices> indexBatches;

	Projector projector{};
	VectorTable vector_table = VectorTable(48);

	for (int i = 0; i < numTri; i++) { //Triangle loop.
		projector.toNearPlane(&tris[i]);
		projector.toNDC(&tris[i]);
		projector.toScreenSpace(&tris[i]);
		projector.depth(&tris[i]);
		tris[i].update(); //Make sure updated A B C vertices reflect everywhere in struct.

		primIndices indices;
		for (int j = 0; j < 3; j++) { //Vertices loop for table setup.
			indices.primitive[j] = vector_table.addVertex(tris[i].vertices[j]);
		}
		indexBatches.push(indices);
	}

	//---------- CLOCK + STAGE GEN ----------
	Clock clk = Clock{};
	const uint32_t MAX_CLK = 100;
	Status IN_FE = Status();
	Fetch fetch = Fetch(&clk);
	Status FE_BB = Status();
	BoundingBox bounding_box = BoundingBox(&clk);
	Status BB_DP = Status();
	Buffer buffer0 = Buffer<primIndices, 3>(&clk);
	Buffer buffer1 = Buffer<primIndices, 3>(&clk);

	std::array<primIndices, 2> batch = {primIndices(), primIndices()};

	auto start = std::chrono::steady_clock::now();
	primIndices input = primIndices();
	bool stop = false;

	for (int halfs = 0; halfs < MAX_CLK*2; halfs++) {
		IN_FE.valid = 0;
		if (stop) {
			break;
		}
		else if (!indexBatches.empty() && IN_FE.ready && clk.isComb()) {
			input = indexBatches.front();
			indexBatches.pop();
			IN_FE.valid = 1;
		}
		//---------- FETCH ----------
		fetch.comb(&FE_BB, &IN_FE, input);
		batch = fetch.forward(&FE_BB, &IN_FE, batch); //Forward stage.

		//---------- BOUNDING BOX ----------
		bounding_box.comb(&FE_BB, batch, &vector_table);
		batch = bounding_box.forward(&BB_DP, &FE_BB, batch); //Forward bounding box stage.

		//---------- DISPATCH ----------
		if (BB_DP.valid) { //BUFFER DEBUG
			buffer0._en();
			buffer1._en();
			stop = indexBatches.empty();
		}
		else {
			buffer0.n_en();
			buffer1.n_en();
		}

		buffer0.comb(batch[0]);
		buffer1.comb(batch[1]);

		primIndices* val0 = buffer0.latch();
		primIndices* val1 = buffer1.latch();

		if (val0 != nullptr) val0->print();
		if (val1 != nullptr) val1->print();

		batch[0] = val0 != nullptr ? *val0 : batch[0];
		batch[1] = val1 != nullptr ? *val1 : batch[1];

		//---------- DEBUG ----------
		/*if (BB_DP.valid) {
			std::array<std::array<f16Vector2, 2>, 2> bb_batch = bounding_box.getBB();

			bb_batch[0][0].print(); //From triangle 1 get min.
			bb_batch[0][1].print(); //From triangle 1 get max.

			std::cout << "\n";

			bb_batch[1][0].print(); //From triangle 2 get min.
			bb_batch[1][1].print(); //From triangle 2 get max.
			
			std::cout << "Cycles: " << clk.cycle << "\n";
			std::cout << "\n";

			stop = indexBatches.empty();
		}*/

		clk.edge();
	}

	auto end = std::chrono::steady_clock::now();
	std::chrono::duration<double> duration_seconds = end - start;
	std::cout << "Time: " << duration_seconds << "\n";
	//std::cin.get();

	return 0;
}
