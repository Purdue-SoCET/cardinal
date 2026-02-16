#include "graphics_lib.h"
#include <vector>
#include <iostream>
#include <queue>

class Rasterizer {
private:
	std::queue<Triangle*> jobs;
public:
	Rasterizer(std::vector<Triangle>* triangles = NULL
		, int msaa = 0, int w = 1280, int h = 720, int near = 1, int far = 10)
	{
		if (&triangles != NULL) {
			for (int i = 0; i < (*triangles).size(); i++) {
				jobs.push(&(*triangles)[i]); //Holy type conversion
			}
		}
	}
};