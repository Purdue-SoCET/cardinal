#include "../../kernels/include/graphics_lib.h"

void barycentric_coordinates(vector_t*, vector_t, vector_t[3]);
void get_texture(vector_t*, texture_t, float, float);
int matrix_inversion(const float*, float*);
void loadbin(char *fname, model_t *model); //https://github.com/sexton34/Graphics-Pipeline/tree/master
vector_t findCenter(model_t model);
