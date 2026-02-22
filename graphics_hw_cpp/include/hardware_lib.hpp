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

#endif // !HARDWARE_LIB_H
