#include <cstdint>

// Array sizes match the checked-in configuration.

//TBS_scheduler stage
struct tbs_sched_packet{
    uint32_t block_id;
    uint32_t block_thread_count;
    uint32_t start_pc;
};

//Scheduler_TBS stage
struct sched_tbs_packet{
    uint32_t completed_block_ids[32];
    uint8_t completed_block_count;
};

//Scheduler_Icache stage
struct sched_icache_packet{
    uint32_t pc;
    uint8_t warp_id;
    uint8_t warp_group_id;
    uint32_t active_mask;
};

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
enum class decode_type : uint8_t{
    halt = 0,
    EOP = 1,
    MOP = 2,
    EOS = 3,
    empty = 4,
};

struct decode_sched_packet{
    decode_type type;
    uint8_t warp_id;
    uint32_t pc;
};

//Icache_Decode stage
    // from both "req in flight to memory" (self.pending) and "stalled waiting on memory"
    // resp and fetch respectively, identical (afaik)
struct instr_packet{
    uint8_t opcode;
    uint8_t rd;
    uint8_t rs1;
    uint8_t rs2;
    uint8_t pred;
    bool SOP; //start of packet
    bool EOP; //end of packet
    uint8_t dest_pred;
    uint32_t imm;
    uint8_t imm_width;
    uint8_t num_operands;
};

struct icache_decode_packet{
    uint32_t pc;            
    uint8_t warp_id;        
    uint8_t warp_group_id;  
    uint32_t active_mask;   
    uint32_t instr;        // will this be int32 or instr_packet? If latter, decode stage is just passthrough with a 1cycle stall
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
    uint32_t raw_instr;
    bool predicate[32];
    uint32_t intended_FU; // FSU index
    uint32_t target_bank;
    uint8_t target_regfile; // 0: RF, 1: PRF
    uint8_t csr_param;
    uint32_t csr_value;
    uint32_t rdat1[32];
    uint32_t rdat2[32];
};

//Issue_scheduler stage
struct issue_sched_packet{
    bool full_flags[16];
};

//Issue_Decode stage
using issue_decode_packet = issue_sched_packet;

//Issue_Execute stage
struct issue_execute_packet{
    decode_issue_packet decoded;
    uint64_t issued_cycle;
};

//Execute_Writeback stage
struct execute_writeback_packet{
    issue_execute_packet issued;
    uint32_t wdat[32];
    bool wdat_pred[32];
    uint64_t wb_entry_cycle;
    uint64_t wb_cycle;
};

//Writeback_scheduler stage
struct writeback_retirement{
    uint8_t warp_group_id;
    uint8_t warp_id;
    uint32_t new_mask;
};

struct writeback_sched_packet{
    writeback_retirement retired[3];
    uint8_t retired_count;
};

//Jump_scheduler stage
struct jump_sched_packet{
    uint8_t warp;
    int64_t dest;
};

//Scheduler_LSU stage
struct sched_lsu_packet{
    bool halt;
};

//LSU_scheduler stage
struct lsu_sched_packet{
    bool flush_complete;
};

//LSU_Dcache stage
enum class memory_rw : uint8_t{
    read,
    write,
};

enum class memory_size : uint8_t{
    byte = 1,
    half = 2,
    word = 4,
};

struct lsu_dcache_packet{
    int64_t addr_val;
    memory_rw rw_mode;
    memory_size size;
    uint32_t store_value;
    bool halt;
};

//Dcache_LSU stage
enum class dcache_response_type : uint8_t{
    MISS_ACCEPTED,
    HIT_COMPLETE,
    MISS_COMPLETE,
    HIT_STALL,
    FLUSH_COMPLETE,
};

struct dcache_lsu_packet{
    dcache_response_type type;
    lsu_dcache_packet req;
    int64_t address;
    bool replay;
    bool is_secondary;
    uint32_t data;
    bool miss;
    bool hit;
    bool stall;
    uint64_t uuid;
    bool flushed;
};

//Icache_MemoryController stage
struct icache_mem_packet{
    uint32_t addr;
    uint32_t size;
    uint64_t uuid;
    sched_icache_packet inst;
};

//MemoryController_Icache stage
struct mem_icache_packet{
    sched_icache_packet inst;
    uint8_t packet[4];
};

//Dcache_MemoryController stage
struct dcache_mem_packet{
    uint32_t addr;
    uint32_t size;
    uint64_t uuid;
    uint32_t bank_id;
    memory_rw rw_mode;
    uint32_t data[32];
};

//MemoryController_Dcache stage
enum class memory_response_type : uint8_t{
    READ_COMPLETE,
    WRITE_DONE,
};

struct mem_dcache_packet{
    uint32_t bank_id;
    memory_response_type status;
    uint8_t packet[128];
};
