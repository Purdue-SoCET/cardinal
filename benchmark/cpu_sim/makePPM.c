#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>

void createPPMFile(char* fileName, float (*pixels)){
    FILE* file = fopen(fileName, "w");

    if (!file) {
        perror("fopen");
        return;
    }
    
    fputs("P3\n", file);
    fputs("640 480\n", file);
    fputs("255\n", file);

    char R[4], G[4], B[4];

    for(int i = 0; i < 480; i++){     // Top to Bottom
        for(int j = 0; j < 640; j++){ // Left to Right
            int idx = 1920 * i + 3 * j;
                sprintf(R, "%d", (int)(pixels[idx + 0] * 255));
                sprintf(G, "%d", (int)(pixels[idx + 1] * 255));
                sprintf(B, "%d", (int)(pixels[idx + 2] * 255));
                fputs(R, file);
                fputs(" ", file);
                fputs(G, file);
                fputs(" ", file);
                fputs(B, file);
                fputs("\n", file);
        }
    }
    fclose(file);
}


int main()
{
    float (*pixel) = malloc(480 * 640 * 3 * sizeof(float));

    for(int i = 0; i < 480; i++){     // Top to Bottom
        for(int j = 0; j < 640; j++){ // Left to Right
            int idx = 1920 * i + 3 * j;
                    //R G B
                if(j < 213){
                    pixel[idx + 0] = 1.0;
                    pixel[idx + 1] = 0;
                    pixel[idx + 2] = 0;
                }
                else if (j < 426){
                    pixel[idx + 0] = 0;
                    pixel[idx + 1] = 1.0;
                    pixel[idx + 2] = 0;
                }
                else{
                    pixel[idx + 0] = 0;
                    pixel[idx + 1] = 0;
                    pixel[idx + 2] = 1.0;
                }
        }
    }

    createPPMFile("output2.ppm", pixel);

    free(pixel);

    return 0;
}
