
=== Cycle 0 ===
[DEBUG] Cycle Start: QueueLen=0, LatchValid=True
LDST_FU: Accepting instruction from latch pc: Instruction(pc=0, intended_FU='ldst', warp_id=0, warp_group_id=0, rs1=Bits('0x00000000'), rs2=Bits('0x00000000'), rd=0, opcode=Bits('0b0110000'), predicate=[Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1')], issued_cycle=None, stage_entry={}, stage_exit={}, fu_entries=[], wb_cycle=None, target_bank=None, rdat1=[Bits('0x00000000'), Bits('0x00000020'), Bits('0x00000040'), Bits('0x00000060'), Bits('0x00000080'), Bits('0x000000a0'), Bits('0x000000c0'), Bits('0x000000e0'), Bits('0x00000100'), Bits('0x00000120'), Bits('0x00000140'), Bits('0x00000160'), Bits('0x00000180'), Bits('0x000001a0'), Bits('0x000001c0'), Bits('0x000001e0'), Bits('0x00000200'), Bits('0x00000220'), Bits('0x00000240'), Bits('0x00000260'), Bits('0x00000280'), Bits('0x000002a0'), Bits('0x000002c0'), Bits('0x000002e0'), Bits('0x00000300'), Bits('0x00000320'), Bits('0x00000340'), Bits('0x00000360'), Bits('0x00000380'), Bits('0x000003a0'), Bits('0x000003c0'), Bits('0x000003e0')], rdat2=[Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000')], wdat=[Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000')])
=== Latch State at End of Cycle 0 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 1 ===
Cache: Received new request: dCacheRequest(addr_val=0x0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 1 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 2 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 2 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 3 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x807D01D8)
=== Latch State at End of Cycle 3 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x20, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 4 ===
Cache: Received new request: dCacheRequest(addr_val=0x20, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 4 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 5 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 5 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 6 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x8001E2A0)
=== Latch State at End of Cycle 6 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x40, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 7 ===
Cache: Received new request: dCacheRequest(addr_val=0x40, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 7 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 8 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 8 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 9 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0xFFFFFFFF)
=== Latch State at End of Cycle 9 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x60, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 10 ===
Cache: Received new request: dCacheRequest(addr_val=0x60, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 10 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 11 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 11 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 12 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0xC4598680)
=== Latch State at End of Cycle 12 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x80, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 13 ===
Cache: Received new request: dCacheRequest(addr_val=0x80, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 13 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 14 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 14 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 15 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00004040)
=== Latch State at End of Cycle 15 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0xA0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 16 ===
Cache: Received new request: dCacheRequest(addr_val=0xA0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 16 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 17 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 17 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 18 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00003041)
=== Latch State at End of Cycle 18 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0xC0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 19 ===
Cache: Received new request: dCacheRequest(addr_val=0xC0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 19 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 20 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 20 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 21 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00009841)
=== Latch State at End of Cycle 21 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0xE0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 22 ===
Cache: Received new request: dCacheRequest(addr_val=0xE0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 22 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 23 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 23 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 24 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x0000D841)
=== Latch State at End of Cycle 24 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x100, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 25 ===
Cache: Received new request: dCacheRequest(addr_val=0x100, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 25 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 26 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 26 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 27 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00000C42)
=== Latch State at End of Cycle 27 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x120, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 28 ===
Cache: Received new request: dCacheRequest(addr_val=0x120, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 28 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 29 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 29 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 30 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00002C42)
=== Latch State at End of Cycle 30 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x140, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 31 ===
Cache: Received new request: dCacheRequest(addr_val=0x140, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 31 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 32 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 32 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 33 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00004C42)
=== Latch State at End of Cycle 33 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x160, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 34 ===
Cache: Received new request: dCacheRequest(addr_val=0x160, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 34 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 35 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 35 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 36 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00006C42)
=== Latch State at End of Cycle 36 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x180, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 37 ===
Cache: Received new request: dCacheRequest(addr_val=0x180, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 37 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 38 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 38 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 39 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00008642)
=== Latch State at End of Cycle 39 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x1A0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 40 ===
Cache: Received new request: dCacheRequest(addr_val=0x1A0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 40 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 41 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 41 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 42 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00009642)
=== Latch State at End of Cycle 42 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x1C0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 43 ===
Cache: Received new request: dCacheRequest(addr_val=0x1C0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 43 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 44 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 44 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 45 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x0000A642)
=== Latch State at End of Cycle 45 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x1E0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 46 ===
Cache: Received new request: dCacheRequest(addr_val=0x1E0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 46 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 47 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 47 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 48 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x0000B642)
=== Latch State at End of Cycle 48 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x200, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 49 ===
Cache: Received new request: dCacheRequest(addr_val=0x200, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 49 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 50 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 50 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 51 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x0000C642)
=== Latch State at End of Cycle 51 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x220, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 52 ===
Cache: Received new request: dCacheRequest(addr_val=0x220, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 52 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 53 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 53 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 54 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x0000D642)
=== Latch State at End of Cycle 54 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x240, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 55 ===
Cache: Received new request: dCacheRequest(addr_val=0x240, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 55 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 56 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 56 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 57 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x0000E642)
=== Latch State at End of Cycle 57 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x260, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 58 ===
Cache: Received new request: dCacheRequest(addr_val=0x260, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 58 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 59 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 59 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 60 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x0000F642)
=== Latch State at End of Cycle 60 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x280, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 61 ===
Cache: Received new request: dCacheRequest(addr_val=0x280, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 61 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 62 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 62 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 63 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00000343)
=== Latch State at End of Cycle 63 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x2A0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 64 ===
Cache: Received new request: dCacheRequest(addr_val=0x2A0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 64 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 65 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 65 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 66 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00000B43)
=== Latch State at End of Cycle 66 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x2C0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 67 ===
Cache: Received new request: dCacheRequest(addr_val=0x2C0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 67 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 68 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 68 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 69 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00001343)
=== Latch State at End of Cycle 69 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x2E0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 70 ===
Cache: Received new request: dCacheRequest(addr_val=0x2E0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 70 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 71 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 71 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 72 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00001B43)
=== Latch State at End of Cycle 72 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x300, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 73 ===
Cache: Received new request: dCacheRequest(addr_val=0x300, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 73 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 74 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 74 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 75 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00002343)
=== Latch State at End of Cycle 75 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x320, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 76 ===
Cache: Received new request: dCacheRequest(addr_val=0x320, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 76 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 77 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 77 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 78 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00002B43)
=== Latch State at End of Cycle 78 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x340, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 79 ===
Cache: Received new request: dCacheRequest(addr_val=0x340, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 79 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 80 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 80 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 81 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00003343)
=== Latch State at End of Cycle 81 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x360, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 82 ===
Cache: Received new request: dCacheRequest(addr_val=0x360, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 82 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 83 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 83 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 84 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00003B43)
=== Latch State at End of Cycle 84 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x380, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 85 ===
Cache: Received new request: dCacheRequest(addr_val=0x380, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 85 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 86 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 86 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 87 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00004343)
=== Latch State at End of Cycle 87 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x3A0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 88 ===
Cache: Received new request: dCacheRequest(addr_val=0x3A0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 88 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 89 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 89 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 90 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00004B43)
=== Latch State at End of Cycle 90 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x3C0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 91 ===
Cache: Received new request: dCacheRequest(addr_val=0x3C0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 91 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 92 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 92 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 93 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00005343)
=== Latch State at End of Cycle 93 ===
  [issue_lsu_req] Empty
  [LSU_dCache] VALID: dCacheRequest(addr_val=0x3E0, rw_mode='write', size='word', store_value=-559087616, halt=False)
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 94 ===
Cache: Received new request: dCacheRequest(addr_val=0x3E0, rw_mode='write', size='word', store_value=-559087616, halt=False)
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 94 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 95 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
=== Latch State at End of Cycle 95 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] Empty
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===

=== Cycle 96 ===
[DEBUG] Cycle Start: QueueLen=1, LatchValid=False
[LSU] Received: HIT COMPLETE (Data: 0x00005B43)
LDST_FU: Finished processing Instruction pc: 0
LDST_FU: Pushing Instruction for WB pc: 0
=== Latch State at End of Cycle 96 ===
  [issue_lsu_req] Empty
  [LSU_dCache] Empty
  [dcache_mem] Empty
  [mem_dcache] Empty
  [lsu_wb_resp] VALID: Instruction(pc=0, intended_FU='ldst', warp_id=0, warp_group_id=0, rs1=Bits('0x00000000'), rs2=Bits('0x00000000'), rd=0, opcode=Bits('0b0110000'), predicate=[Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1'), Bits('0b1')], issued_cycle=None, stage_entry={}, stage_exit={}, fu_entries=[], wb_cycle=None, target_bank=None, rdat1=[Bits('0x00000000'), Bits('0x00000020'), Bits('0x00000040'), Bits('0x00000060'), Bits('0x00000080'), Bits('0x000000a0'), Bits('0x000000c0'), Bits('0x000000e0'), Bits('0x00000100'), Bits('0x00000120'), Bits('0x00000140'), Bits('0x00000160'), Bits('0x00000180'), Bits('0x000001a0'), Bits('0x000001c0'), Bits('0x000001e0'), Bits('0x00000200'), Bits('0x00000220'), Bits('0x00000240'), Bits('0x00000260'), Bits('0x00000280'), Bits('0x000002a0'), Bits('0x000002c0'), Bits('0x000002e0'), Bits('0x00000300'), Bits('0x00000320'), Bits('0x00000340'), Bits('0x00000360'), Bits('0x00000380'), Bits('0x000003a0'), Bits('0x000003c0'), Bits('0x000003e0')], rdat2=[Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000'), Bits('0xdead0000')], wdat=[Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000'), Bits('0x00000000')])
  [icache_mem_req] Empty
  [mem_icache_resp] Empty

Forward latches:
  [dcache_lsu_forward_if] Empty
  [lsu_sched_forward_if] Empty
=== Test ended ===
WB Received instruction from LSU!

======== Bank 0 ========
  ---- Set 0 ----
    LRU Order: [7, 0, 1, 2, 3, 4, 5, 6] (Front=MRU, Back=LRU)
    [Way 7] V:1 D Tag: 0x0    (Addr: 0x00000000)
        Block[00:03]: 0xDEAD0000 0x807D2258 0x807D42D8 0xC0206182
        Block[04:07]: 0xC0286180 0x800D87D1 0x8001E220 0x800E07D1
        Block[08:11]: 0xDEAD0000 0x800E87D1 0x8001E320 0x800E87D1
        Block[12:15]: 0x800027D2 0x8001E3A0 0xC0206144 0xC0222860
        Block[16:19]: 0xDEAD0000 0x80100710 0x8070618D 0x4418C400
        Block[20:23]: 0x8418E480 0x44010520 0x840125A0 0x84294602
        Block[24:27]: 0xDEAD0000 0xC449A030 0xC0022860 0x00040000
        Block[28:31]: 0x00000040 0x00000000 0x0000803F 0x00000040
  ---- Set 1 ----
    LRU Order: [7, 0, 1, 2, 3, 4, 5, 6] (Front=MRU, Back=LRU)
    [Way 7] V:1 D Tag: 0x0    (Addr: 0x00000100)
        Block[00:03]: 0xDEAD0000 0x00001042 0x00001442 0x00001842
        Block[04:07]: 0x00001C42 0x00002042 0x00002442 0x00002842
        Block[08:11]: 0xDEAD0000 0x00003042 0x00003442 0x00003842
        Block[12:15]: 0x00003C42 0x00004042 0x00004442 0x00004842
        Block[16:19]: 0xDEAD0000 0x00005042 0x00005442 0x00005842
        Block[20:23]: 0x00005C42 0x00006042 0x00006442 0x00006842
        Block[24:27]: 0xDEAD0000 0x00007042 0x00007442 0x00007842
        Block[28:31]: 0x00007C42 0x00008042 0x00008242 0x00008442
  ---- Set 2 ----
    LRU Order: [7, 0, 1, 2, 3, 4, 5, 6] (Front=MRU, Back=LRU)
    [Way 7] V:1 D Tag: 0x0    (Addr: 0x00000200)
        Block[00:03]: 0xDEAD0000 0x0000C842 0x0000CA42 0x0000CC42
        Block[04:07]: 0x0000CE42 0x0000D042 0x0000D242 0x0000D442
        Block[08:11]: 0xDEAD0000 0x0000D842 0x0000DA42 0x0000DC42
        Block[12:15]: 0x0000DE42 0x0000E042 0x0000E242 0x0000E442
        Block[16:19]: 0xDEAD0000 0x0000E842 0x0000EA42 0x0000EC42
        Block[20:23]: 0x0000EE42 0x0000F042 0x0000F242 0x0000F442
        Block[24:27]: 0xDEAD0000 0x0000F842 0x0000FA42 0x0000FC42
        Block[28:31]: 0x0000FE42 0x00000043 0x00000143 0x00000243
  ---- Set 3 ----
    LRU Order: [7, 0, 1, 2, 3, 4, 5, 6] (Front=MRU, Back=LRU)
    [Way 7] V:1 D Tag: 0x0    (Addr: 0x00000300)
        Block[00:03]: 0xDEAD0000 0x00002443 0x00002543 0x00002643
        Block[04:07]: 0x00002743 0x00002843 0x00002943 0x00002A43
        Block[08:11]: 0xDEAD0000 0x00002C43 0x00002D43 0x00002E43
        Block[12:15]: 0x00002F43 0x00003043 0x00003143 0x00003243
        Block[16:19]: 0xDEAD0000 0x00003443 0x00003543 0x00003643
        Block[20:23]: 0x00003743 0x00003843 0x00003943 0x00003A43
        Block[24:27]: 0xDEAD0000 0x00003C43 0x00003D43 0x00003E43
        Block[28:31]: 0x00003F43 0x00004043 0x00004143 0x00004243

======== Bank 1 ========
  ---- Set 0 ----
    LRU Order: [7, 0, 1, 2, 3, 4, 5, 6] (Front=MRU, Back=LRU)
    [Way 7] V:1 D Tag: 0x0    (Addr: 0x00000080)
        Block[00:03]: 0xDEAD0000 0x00008040 0x0000A040 0x0000C040
        Block[04:07]: 0x0000E040 0x00000041 0x00001041 0x00002041
        Block[08:11]: 0xDEAD0000 0x00004041 0x00005041 0x00006041
        Block[12:15]: 0x00007041 0x00008041 0x00008841 0x00009041
        Block[16:19]: 0xDEAD0000 0x0000A041 0x0000A841 0x0000B041
        Block[20:23]: 0x0000B841 0x0000C041 0x0000C841 0x0000D041
        Block[24:27]: 0xDEAD0000 0x0000E041 0x0000E841 0x0000F041
        Block[28:31]: 0x0000F841 0x00000042 0x00000442 0x00000842
  ---- Set 1 ----
    LRU Order: [7, 0, 1, 2, 3, 4, 5, 6] (Front=MRU, Back=LRU)
    [Way 7] V:1 D Tag: 0x0    (Addr: 0x00000180)
        Block[00:03]: 0xDEAD0000 0x00008842 0x00008A42 0x00008C42
        Block[04:07]: 0x00008E42 0x00009042 0x00009242 0x00009442
        Block[08:11]: 0xDEAD0000 0x00009842 0x00009A42 0x00009C42
        Block[12:15]: 0x00009E42 0x0000A042 0x0000A242 0x0000A442
        Block[16:19]: 0xDEAD0000 0x0000A842 0x0000AA42 0x0000AC42
        Block[20:23]: 0x0000AE42 0x0000B042 0x0000B242 0x0000B442
        Block[24:27]: 0xDEAD0000 0x0000B842 0x0000BA42 0x0000BC42
        Block[28:31]: 0x0000BE42 0x0000C042 0x0000C242 0x0000C442
  ---- Set 2 ----
    LRU Order: [7, 0, 1, 2, 3, 4, 5, 6] (Front=MRU, Back=LRU)
    [Way 7] V:1 D Tag: 0x0    (Addr: 0x00000280)
        Block[00:03]: 0xDEAD0000 0x00000443 0x00000543 0x00000643
        Block[04:07]: 0x00000743 0x00000843 0x00000943 0x00000A43
        Block[08:11]: 0xDEAD0000 0x00000C43 0x00000D43 0x00000E43
        Block[12:15]: 0x00000F43 0x00001043 0x00001143 0x00001243
        Block[16:19]: 0xDEAD0000 0x00001443 0x00001543 0x00001643
        Block[20:23]: 0x00001743 0x00001843 0x00001943 0x00001A43
        Block[24:27]: 0xDEAD0000 0x00001C43 0x00001D43 0x00001E43
        Block[28:31]: 0x00001F43 0x00002043 0x00002143 0x00002243
  ---- Set 3 ----
    LRU Order: [7, 0, 1, 2, 3, 4, 5, 6] (Front=MRU, Back=LRU)
    [Way 7] V:1 D Tag: 0x0    (Addr: 0x00000380)
        Block[00:03]: 0xDEAD0000 0x00004443 0x00004543 0x00004643
        Block[04:07]: 0x00004743 0x00004843 0x00004943 0x00004A43
        Block[08:11]: 0xDEAD0000 0x00004C43 0x00004D43 0x00004E43
        Block[12:15]: 0x00004F43 0x00005043 0x00005143 0x00005243
        Block[16:19]: 0xDEAD0000 0x00005443 0x00005543 0x00005643
        Block[20:23]: 0x00005743 0x00005843 0x00005943 0x00005A43
        Block[24:27]: 0xDEAD0000 0x00005C43 0x00005D43 0x00005E43
        Block[28:31]: 0x00005F43 0x00006043 0x00006143 0x00006243
