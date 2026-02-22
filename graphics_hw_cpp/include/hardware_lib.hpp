#ifndef HARDWARE_LIB_H
#define HARDWARE_LIB_H

class Clock {
private:
	int phase = 0; //0 is comb, 1 is push/latch
public:
	int half = 0;
	int cycle = 0;

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
	int valid = 0;
	int ready = 1;
};

#endif // !HARDWARE_LIB_H
