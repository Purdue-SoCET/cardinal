#include <cstdint>

//Icache_scheduler stage
    // still need icache_scheduler_fwif? <= filler_decode = {DecodeType.MOP, warp_id, pc}.
    // Or seperate forward_data_packets?
struct icache_sched_packet{ // ready/stalled signals to sched
    bool val;
    bool eop;
    int warp_id; //could be uint_8?
};

//Decode_scheduler stage
    //Decode_scheduler_pckt <= push_pkt = {"type" = packet_market, inst.warp_id, inst.pc}


//Icache_Decode stage
    // from both "req in flight to memory" (self.pending) and "stalled waiting on memory"
    // resp and fetch respectively, identical (afaik)
struct instr_packet{
    uint8_t opcode;
    uint8_t rd;
    uint8_t rs1;
    uint8_t rs2;
    uint8_t pred;
    bool EOP;
    bool SOP;
};

struct icache_decode_packet{
    uint32_t pc;            
    uint8_t warp_id;        
    uint8_t warp_group_id;  
    uint32_t active_mask;   
    instr_packet instr;        // will this be int32 or instr_packet? If latter, decode stage is just passthrough with a 1cycle stall
};
    // LatchIF<icache_decode_packet> icache_decode_if("ICache-Decode Latch");

//Decode_Issue stage
    //consists of decode_issue_if, ahead_latch of DecodeStage <= inst. Inst holds warp_id and pc??
struct decode_issue_packet{
    uint32_t pc;            
    uint8_t warp_id;        
    uint8_t warp_group_id;  
    uint32_t active_mask;
    instr_packet instr;
};

