#include "../../kernels/include/graphics_lib.h"

void barycentric_coordinates(vector_t*, vector_t, vector_t[3]);
void get_texture(vector_t*, texture_t, float, float);
int matrix_inversion(const float*, float*);
void loadbin(char *fname, model_t *model); //https://github.com/sexton34/Graphics-Pipeline/tree/master
vector_t findCenter(model_t model);
texture_t load_jpg(char* FileName, int id);
texture_t load_png(char* FileName, int id);
void dump_memory(const char* filename, uint8_t* host_memory_ptr, uint32_t simulated_base_address, size_t num_bytes);
