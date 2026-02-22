#include "rasterizer.hpp"
#include "vector_table.hpp"


Fetch::Fetch(Clock* clk) {
	this->clk = clk;
}

std::array<std::array<int, 3>, 2> Fetch::forward(Status* FE_BB, std::array<std::array<int, 3>, 2> batch) {
	std::array<std::array<int, 3>, 2> out;
	out[0] = batch[0];
	out[1] = batch[1];

	if (FE_BB->ready && this->clk->isLatch()) {
		if (!this->indices.empty()) {
			out[0] = this->indices.front();
			this->indices.pop();
		}
		else {
			FE_BB->valid = 0;
			return out;
		}

		if (!this->indices.empty()) {
			out[1] = this->indices.front();
			this->indices.pop();
		}
		else {
			FE_BB->valid = 0;
			this->indices.push(out[0]);
			return out;
		}
		FE_BB->valid = 1;
		return out;
	}
	else if (FE_BB->ready && this->clk->isComb()) {
		return out;
	}

	FE_BB->valid = 0;
	return out;
}

void Fetch::comb(Status* FE_BB, std::array<int, 3> tri) {
	if (this->clk->isComb()) {
		this->indices.push(tri);
	}
}


BoundingBox::BoundingBox(Clock* clk) {
	this->clk = clk;
}

std::array<std::array<int, 3>, 2> BoundingBox::forward(Status* BB_DP, Status* FE_BB, std::array<std::array<int, 3>, 2> batch) {
	std::array<std::array<int, 3>, 2> out;
	out[0] = batch[0];
	out[1] = batch[1];
	FE_BB->ready = 1;

	if (BB_DP->ready && this->clk->isLatch()) {
		if (!this->indices.empty()) {
			out[0] = this->indices.front();
			this->indices.pop();
		}
		else {
			BB_DP->valid = 0;
			return out;
		}

		if (!this->indices.empty()) {
			out[1] = this->indices.front();
			this->indices.pop();
		}
		else {
			BB_DP->valid = 0;
			this->indices.push(out[0]);
			return out;
		}
		BB_DP->valid = 1;
		return out;
	}
	else if (BB_DP->ready && this->clk->isComb()) return out;

	BB_DP->valid = 0;
	return out;
}

void BoundingBox::comb(Status* FE_BB, std::array<std::array<int, 3>, 2> tris, VectorTable* table) {
	FE_BB->ready = 0;

	if (FE_BB->valid && this->clk->isComb()) {
		this->indices.push(tris[0]);
		this->indices.push(tris[1]);

		Triangle tri0 = table->getTriangle(tris[0]);
		Triangle tri1 = table->getTriangle(tris[1]);

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

		this->bounding_box.push({ t0,t1 });
	}
}

std::array<std::array<f16Vector2, 2>, 2> BoundingBox::getBB() {
	std::array<std::array<f16Vector2, 2>, 2> out = this->bounding_box.front();
	this->bounding_box.pop();
	return out;
}

Dispatch::Dispatch() {}


PreEdge::PreEdge() {}


EdgeTest::EdgeTest() {}