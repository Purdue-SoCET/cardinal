#include <cstdint>

struct decode_packet{
    uint8_t opcode;
    uint8_t rd;
    uint8_t rs1;
    uint8_t rs2;
    uint8_t pred;
    bool EOP;
    bool SOP;
} decode_packet;

LatchIF<decode_packet> decode_latch;