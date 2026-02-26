#ifndef HARDWARE_LIB_H
#define HARDWARE_LIB_H

#include <cstdint>

class Clock {
private:
	uint64_t phase = 0; //0 is comb, 1 is push/latch
public:
	uint64_t half = 0;
	uint32_t cycle = 0;

	void edge() {
		(this->cycle) += isLatch();
		(this->phase)++;
		(this->half)++;
	}

	bool isComb() {
		return this->phase % 2 == 0;
	}

	bool isLatch() {
		return this->phase % 2 == 1;
	}

	Clock() {};
};

struct Status {
	bool valid = 0;
	bool ready = 1;
};

struct primIndices {
	std::array<int8_t, 3> primitive = {-1,-1,-1}; 
	void print() {
		std::cout << "(" << (int) primitive[0] << ", " << (int) primitive[1] << ", " << (int) primitive[2] << ")\n";
	}
};

template<typename T, std::size_t len>
class Buffer {
private:
	Clock* clk;
	uint16_t size = len;
	std::vector<T> buffer;
	bool en = 0;
	bool readyOut = 0;
	T nextOut;
	uint8_t currSize = 0;
	bool filled = 0;
	uint32_t clkPassed = 0;
public:
	T out;
	bool readyIn = 1;
	bool noIn = 0;

	uint8_t getSize() {
		return this->currSize;
	}

	bool isFilled() {
		return this->filled;
	}

	void _en() {
		this->en = 1;
	}

	void n_en() {
		this->en = 0;
	}

	void comb(T in) {
		if (this->clk->isComb() && this->en) {

			if (this->buffer.size() == 0) {
				filled = 0;
				this->clkPassed = 1;
			}
			else {
				this->clkPassed++;
			}

			if (currSize == 0 && !this->noIn) {
				this->buffer.push_back(in);
				currSize++;
			}
			else if (currSize < this->size && !this->noIn) {
				this->buffer.push_back(in);
				currSize++;
			}
			
			if (this->clkPassed == this->size && !this->noIn) {
				filled = 1;
			}

			if (filled) {
				nextOut = this->buffer[0];
				readyOut = 1;
				this->buffer.erase(this->buffer.begin());
				currSize--;
			}
			else {
				readyOut = 0;
			}

			readyIn = currSize < this->size ? 1 : 0;
		}
	}
	
	T* latch() {
		if (this->clk->isLatch() && this->readyOut) {
			this->out = this->nextOut;
			this->readyOut = 0;
			return &(this->out);
		}
		return nullptr;
	}

	Buffer(Clock* clk) : clk(clk) {
		this->buffer.reserve(this->size);
	}
};

#endif // !HARDWARE_LIB_H
