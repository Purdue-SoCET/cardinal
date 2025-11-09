#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>

void createPPMFile(char* fileName, int (*pixels)[640][3]){
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
                sprintf(R, "%d", pixels[i][j][0]);
                sprintf(G, "%d", pixels[i][j][1]);
                sprintf(B, "%d", pixels[i][j][2]);
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

/*
int main()
{
    int (*pixel)[640][3] = malloc(480 * 640 * 3 * sizeof(int));

    for(int i = 0; i < 480; i++){     // Top to Bottom
        for(int j = 0; j < 640; j++){ // Left to Right
                    //R G B
                if(j < 213){
                    pixel[i][j][0] = 255;
                    pixel[i][j][1] = 0;
                    pixel[i][j][2] = 0;
                }
                else if (j < 426){
                    pixel[i][j][0] = 0;
                    pixel[i][j][1] = 255;
                    pixel[i][j][2] = 0;
                }
                else{
                    pixel[i][j][0] = 0;
                    pixel[i][j][1] = 0;
                    pixel[i][j][2] = 255;
                }
        }
    }

    createPPMFile("output2.ppm", pixel);

    free(pixel);

    return 0;
}
*/