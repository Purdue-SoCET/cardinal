#include "graphics_lib.h"
#include <vector>

using namespace std;

int main()
{
	fVector3 point1{ -0.8, 0.6, -2};
	fVector3 point2{ 0.8, 0.6, -2 };
	fVector3 point3{ 0.0, -0.6, -5};

	Vertex v1{ point1 };
	Vertex v2{ point2 };
	Vertex v3{ point3 };

	Triangle t1{ v1, v2, v3 };

	Projector projector{};
	projector.toNearPlane(&t1);
	projector.toNDC(&t1);
	projector.toScreenSpace(&t1);
	projector.depth(&t1);

	t1.A.screenSpacePoint.print();
	t1.B.screenSpacePoint.print();
	t1.C.screenSpacePoint.print();

	std::cout << t1.A.point.z << "\n";
	std::cout << t1.B.point.z << "\n";
	std::cout << t1.C.point.z;

	return 0;
}
