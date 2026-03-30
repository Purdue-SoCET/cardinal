#ifndef lavaMD_H
#define lavaMD_H

# define NUMBER_PAR_PER_BOX 100

typedef struct nei_str
{
	// neighbor box
	int x, y, z;
	int number;
	long offset;
} nei_str;

typedef struct dim_str
{ 
	int cur_arg;
	int arch_arg;
	int cores_arg;
	int boxes1d_arg;

	// system memory
	float number_boxes;
	float box_mem;
	float space_elem;
	float space_mem;
	float space_mem2;

} dim_str;

typedef struct box_str
{
    // box coordinates
	int x, y, z;
	int number;
	long offset;
	// neighbor boxes
	int nn;
	nei_str nei[26];
} box_str;

typedef struct
{
	float v, x, y, z;

} four_vec;

typedef struct
{
	float x, y, z;
} three_vec;

typedef struct {
    float alpha;  
    dim_str dim;  // meta data about sim 
    box_str* box; // box data
    four_vec* rv; // particle positions
    float* qv;    // particle charges

    /*Output*/
	four_vec* fv; // particle forces 
} lavaMD_kernel_arg_t;

void kernel_lavaMD_init(void*);
void kernel_lavaMD_calc(void*);

#endif