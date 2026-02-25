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
		std::cout << "(" << primitive[0] << ", " << primitive[1] << ", " << primitive[2] << ")\n";
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
public:
	T out;
	bool readyIn = 1;

	uint8_t getSize() {
		return this->currSize;
	}

	void _en() {
		this->en = 1;
	}

	void n_en() {
		this->en = 0;
	}

	void comb(T in) {
		if (this->clk->isComb() && this->en) {

			filled = this->buffer[0] == T() || this->buffer.size() == 0 ? 0 : 1;

			if (currSize < this->buffer.size()) {
				this->buffer.push_back(in);
				currSize++;
			}
			else if (currSize == this->buffer.size()) {
				nextOut = this->buffer[0];
				readyOut = 1;
				this->buffer.erase(this->buffer.begin());
				currSize--;
			}

			readyIn = currSize < this->buffer.size() ? 1 : 0;
		}
	}
	
	T* latch() {
		if (this->clk->isLatch() && this->en && this->readyOut) {
			this->out = this->nextOut;
			this->readyOut = 0;
			return &(this->out);
		}
		return nullptr;
	}

	Buffer(Clock* clk) : clk(clk) {
		this->buffer = this->buffer(this->len);
	}
};

#endif // !HARDWARE_LIB_H
