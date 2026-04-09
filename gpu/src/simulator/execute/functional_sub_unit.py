from builtins import range
from abc import ABC, abstractmethod
import logging
from typing import Optional, List
from bitstring import Bits
from simulator.utils.performance_counter.telemeter import Telemeter
from common.custom_enums_multi import Op, R_Op, I_Op, F_Op, B_Op, P_Op, J_Op, C_Op, H_Op, U_Op, S_Op
from simulator.utils.performance_counter.execute import ExecutePerfCount as PerfCount
from simulator.interfaces import LatchIF, ForwardingIF
from simulator.instruction import Instruction
from simulator.mem.dMemPackets import dMemResponse
from simulator.mem_types import dCacheRequest, BLOCK_SIZE_WORDS, WORD_SIZE_BYTES

logger = logging.getLogger(__name__)

class FunctionalSubUnit(ABC):
    def __init__(self, num: int, telemeter: Telemeter = None):
        self.name = f"{self.__class__.__name__}_{num}"
        self.ready_out = True
        self.perf_count = PerfCount(name=self.name)
        self.telemeter = telemeter

        if telemeter:
            telemeter.register_unit(self.perf_count)
        else:
            print(f"Warning: No telemeter provided for {self.name}. Performance data will not be recorded.")

        # the way stages are connected in the SM class, we need (latency - 1) latches
        self.ex_wb_interface = LatchIF(name=f"{self.name}_EX_WB_Interface")
    
    @abstractmethod
    def tick(self):
        pass
    
    @abstractmethod
    def compute(self):
        pass
    
    # This method can be overridden in subclasses if they want to record additional custom performance data beyond the standard data.
    def _record_cycle(
        self,
        *,
        instr: Instruction,
        ex_wb_interface_ready: bool,
        ready_out: bool,
        trace_kwargs: dict | None = None,
        trigger_kwargs: dict | None = None,
        record_kwargs: dict | None = None,
    ):
        cycle = self.perf_count.total_cycles

        if trace_kwargs is None:
            trace_kwargs = {}

        if trigger_kwargs is None:
            trigger_kwargs = {}
        
        if record_kwargs is None:
            record_kwargs = {}

        if self.telemeter and self.telemeter.is_trace_active(cycle):
            self.telemeter.record_trace(
                cycle=cycle, 
                unit_name=self.name,
                warp_id=instr.warp_group_id if instr is not None else None,
                opcode=instr.opcode if instr is not None else None,
                pc=instr.pc.uint if instr is not None else None,
                is_stalled=not ex_wb_interface_ready,
                pipeline_full=not ready_out,
                **trace_kwargs,
            )

        # 3. Flight recorder trigger evaluation
        if self.telemeter:
            self.telemeter.check_triggers(
                unit_name=self.name,
                cycle=cycle,
                warp_id=instr.warp_id if instr is not None else None,
                opcode=instr.opcode if instr is not None else None,
                pc=instr.pc.uint if instr is not None else None,
                is_stalled=not ex_wb_interface_ready,
                pipeline_full=not ready_out,
                **trigger_kwargs,
            )

        self.perf_count.record_cycle(
            cycle=cycle,
            is_stalled=not ex_wb_interface_ready,
            is_busy=instr is not None and ready_out,
            pipeline_full=not ready_out,
            instr=instr,
            **record_kwargs,
        )

class Ldst_Fu(FunctionalSubUnit):
    def __init__(self, num, ldst_q_size=4, wb_buffer_size=1, telemeter=None):
        self.ldst_q: list[pending_mem] = []
        self.ldst_q_size: int = ldst_q_size
        self.wb_buffer_size = wb_buffer_size

        self.wb_buffer = [] #completed dcache access buffer

        self.outstanding = False #Whether we have an outstanding dcache request

        # Trackers for halt instruction
        self.halting = False
        self.waiting_for_flush = False

        super().__init__(num, telemeter=telemeter)

        #Manually instantiate interfaces while doing integration
        self.dcache_if = LatchIF()
        self.dcache_if.forward_if = ForwardingIF()
        self.sched_ldst_if = ForwardingIF()
        self.ldst_sched_if = ForwardingIF()

    def connect_interfaces(self, dcache_if: LatchIF, sched_ldst_if = ForwardingIF, ldst_sched_if = ForwardingIF):
        self.dcache_if: LatchIF = dcache_if
        # self.issue_if: LatchIF = issue_if
        # self.wb_if: LatchIF = wb_if replaced with self.ex_wb_interface
        self.sched_ldst_if: ForwardingIF = sched_ldst_if
        self.ldst_sched_if: ForwardingIF = ldst_sched_if
    
    # def forward_miss(self, instr: Instruction):
    #     self.sched_if.push(instr)

    def compute(self):
        pass
    
    def print_dcache_resp(self, dcache_response):
        if dcache_response:
            msg_type = dcache_response.type
            uuid = dcache_response.uuid
            data = dcache_response.data

            # --- Helper: Format Data as Hex ---
            data_hex = data
            if isinstance(data, int):
                data_hex = f"0x{data:08X}" # Format as 8-digit Hex
            elif isinstance(data, list):
                data_hex = [f"0x{x:X}" for x in data] # Format list items
            # ----------------------------------

            if (msg_type == 'MISS_ACCEPTED'):
                print(f"[LSU] Received: MISS ACCEPTED (UUID: {uuid})")
            elif (msg_type == 'HIT_COMPLETE'):
                print(f"[LSU] Received: HIT COMPLETE (Data: {data_hex})")
            elif (msg_type == 'MISS_COMPLETE'):
                print(f"[LSU] Received: MISS COMPLETE (UUID: {uuid}) - Data is in cache")
            elif (msg_type == 'HIT_STALL'):
                print(f"[LSU] Received: HIT STALL")
        
    def tick(self, issue_if: Optional[LatchIF]) -> Optional[Instruction]:
        return_instr = False
        if issue_if and hasattr(issue_if, 'valid'):
            print(f"[DEBUG] Cycle Start: QueueLen={len(self.ldst_q)}, LatchValid={issue_if.valid}")

        if issue_if and len(self.ldst_q) < self.ldst_q_size:
            instr = issue_if.pop()
            if instr != None:
                print(f"LDST_FU: Accepting instruction from latch pc: {instr.pc}")
                print(f"Servicing instruction: op: {instr.opcode} rd: {instr.rd} rs1: {instr.rs1} rs2: {instr.rs2} rdat1: {instr.rdat1} rdat2: {instr.rdat2}")
                pm = pending_mem(instr)
                print(f"Formatting the instr into a pending mem type..: {pm.__dict__}")
                self.ldst_q.append(pending_mem(instr))
        
        # Accept halt signal from the scheduler
        if self.sched_ldst_if.payload != None:
            sched_payload = self.sched_ldst_if.pop()
            if sched_payload.get('halt', False):
                print("[LSU] Received HALT command from Scheduler.")
                self.halting = True

        #apply backpressure if ldst_q full
        if len(self.ldst_q) == self.ldst_q_size:
            print(f"[LSU]: The queue is full")
            # issue_if.forward_if.set_wait(True)
            self.ready_out = False
        else:
            # issue_if.forward_if.set_wait(False)
            self.ready_out = True
        
        #handle dcache packet
        payload: dMemResponse = self.dcache_if.forward_if.pop()
        
        if payload:
            self.dcache_if.forward_if.payload = None
            if len(self.ldst_q) == 0 and payload.type != 'FLUSH_COMPLETE':
                print(f"LSQ is length 0 and recieved a dcache response. Should never happen!")

            self.print_dcache_resp(payload)
            match payload.type:
                case 'MISS_ACCEPTED':
                    # logger.info("Handling dcache MISS_ACCEPTED")
                    self.ldst_q[0].parseMiss(payload)     
                    self.outstanding = False                   
                case 'HIT_STALL':
                    pass
                case 'MISS_COMPLETE':
                    # logger.info("Handling dcache MISS_COMPLETE")
                    self.ldst_q[0].parseMshrHit(payload)
                case 'FLUSH_COMPLETE':
                    self.outstanding = False
                    self.waiting_for_flush = False
                    self.ldst_sched_if.push({'flush_complete': True})
                case 'HIT_COMPLETE':
                    # logger.info("Handling dcache HIT_COMPLETE")
                    self.ldst_q[0].parseHit(payload)
                    self.outstanding = False
        
        #move mem_req to wb_buffer if finished
        if self.outstanding == False and len(self.ldst_q) > 0 and  self.ldst_q[0].readyWB() and len(self.wb_buffer) < self.wb_buffer_size:
            print(f"LDST_FU: Finished processing Instruction pc: {self.ldst_q[0].instr.pc}")
            self.wb_buffer.append(self.ldst_q.pop(0).instr)
        
        #send req to cache if not waiting for response
        if self.outstanding == False and self.dcache_if.ready_for_push():
            if self.halting and len(self.ldst_q) == 0:
                halt_req = dCacheRequest(addr_val=0, rw_mode='read', size='word', halt=True)
                self.dcache_if.push(halt_req)
                self.outstanding = True
                self.halting = False
                self.waiting_for_flush = True
            
            elif len(self.ldst_q) > 0:
                req = self.ldst_q[0].genReq()
                if req:
                    print(f"Sending request to dcache {req}")
                    self.dcache_if.push(req)
                    self.outstanding = True

        #send instr to wb if ready
        if self.ex_wb_interface.ready_for_push() and len(self.wb_buffer) > 0:
            return_instr = self.wb_buffer.pop(0)
            # self.ex_wb_interface.push(return_instr) # REMOVE THIS LATER, JUST FOR TESTING
            if (return_instr):
                print(f"LDST_FU: Pushing Instruction for WB pc: {return_instr.pc}")
    
        return return_instr

class pending_mem():
    def __init__(self, instr) -> None:
        self.instr: Instruction = instr
        self.finished_idx: List[int] = [0 for i in range(32)]
        self.write: bool
        self.mshr_idx: List[int] = [0 for i in range(32)]
        self.addrs = [0 for i in range(32)]
        
        self.write = False
        self.size = "word"
        self.is_signed = False

        match self.instr.opcode:
            case I_Op.LW:
                self.write = False
                self.size = "word"
                self.is_signed = True
            case I_Op.LH:
                self.write = False
                self.size = "half"
                self.is_signed = True
            case I_Op.LB:
                self.write = False
                self.size = "byte"
                self.is_signed = True
            
            case S_Op.SW:
                self.write = True
                self.size = "word"
            case S_Op.SH:
                self.write = True
                self.size = "half"
            case S_Op.SB:
                self.write = True
                self.size = "byte"

            case P_Op.PRSW:
                self.write = True
                self.size = "word"
            case P_Op.PRLW:
                self.write = False
                self.size = "word"
            
            case _:
                logger.error(f"Err: instr in ldst cannot be decoded")
                print(f"\t{instr}")
        
        offset = 0
        if hasattr(self.instr, 'imm') and self.instr.imm is not None:
            offset = self.instr.imm.int

        for i in range(32):
            self.finished_idx[i] = 1-self.instr.predicate[i].uint #iirc pred=1'b1
            if self.instr.predicate[i].uint == 1:
                # self.addrs[i] = (self.instr.rdat1[i].uint + offset) & 0xFFFFFFFF
                self.addrs[i] = (self.instr.rdat1[i].uint + offset)

    def readyWB(self):
        return all(self.finished_idx)
    
    def genReq(self):
        for i in range(32):
            if self.finished_idx[i] == 0 and self.mshr_idx[i] == 0:
                st_val = 0
                if self.write:
                    raw_val = self.instr.rdat2[i].int

                    if self.size == "byte":
                        st_val = raw_val & 0xFF
                    elif self.size == "half":
                        st_val = raw_val & 0xFFFF
                    else:
                        st_val = raw_val & 0xFFFFFFFF

                return dCacheRequest(
                    addr_val=self.addrs[i],
                    rw_mode='write' if self.write else 'read',
                    size=self.size,
                    store_value=st_val
                )
        return None
    
    def parseHit(self, payload):
        if self.write == False and not self.instr.wdat:
            self.instr.wdat = [None for _ in range(32)]
        
        for i in range(32):
            if self.addrs[i] == payload.address:
                self.finished_idx[i] = 1

                #set wdat if instr is a read
                if self.write == False:
                    # Convert to signed if applicable
                    raw_val = payload.data

                    if self.size == "byte":
                        raw_val = raw_val & 0xFF
                        # if self.is_signed and (raw_val & 0x80):
                        #     raw_val = raw_val - 0x100

                    elif self.size == "half":
                        raw_val = raw_val & 0xFFFF
                        # if self.is_signed and (raw_val & 0x8000):
                        #     raw_val = raw_val - 0x10000
                    
                    else:
                        raw_val = raw_val & 0xFFFFFFFF
                        # if self.is_signed and (raw_val & 0x80000000):
                        #     raw_val = raw_val - 0x10000000

                    # if raw_val < 0:
                    #     self.instr.wdat[i] = Bits(int = raw_val, length=32)
                    # else:
                    #     self.instr.wdat[i] = Bits(uint = raw_val, length=32)
                    self.instr.wdat[i] = Bits(uint = raw_val, length=32)

    
    def parseMshrHit(self, payload):
        num_bytes_block = BLOCK_SIZE_WORDS * WORD_SIZE_BYTES
        block_mask = ~(num_bytes_block - 1)
        incoming_block_addr = payload.address & block_mask

        for i in range(32):
            thread_addr = self.addrs[i]
            thread_block_addr = thread_addr & block_mask
            if (thread_block_addr == incoming_block_addr) and (self.mshr_idx[i] == 1):
                if self.write:
                    self.mshr_idx[i] = 0
                    self.finished_idx[i] = 1
                else:
                    print(f"[LSU] Wakeup thread {i} (Addr {hex(thread_addr)}) due to Block Match")
                    self.mshr_idx[i] = 0
                
    
    def parseMiss(self, payload: dMemResponse):
        for i in range(32):
            if self.addrs[i] == payload.address:
                self.mshr_idx[i] = 1 # The ldst needs to wait for the cache to retrieve the data from main memory

class Branch(FunctionalSubUnit):
    SUPPORTED_OPS = [
        B_Op.BEQ, B_Op.BNE, H_Op.HALT
    ]
    def __init__(self, num: int, telemeter=None):
        super().__init__(num=num, telemeter=telemeter)
        self.data = None
    
    def compute(self):
        instr = self.data

        if instr is None or not isinstance(instr, Instruction):
            return
        
        if instr.opcode not in self.SUPPORTED_OPS:
            raise ValueError(f"Branch does not support operation {instr.opcode}")
        
        # FIX: initializng w-dat predicabtee becaue it yelling
        instr.wdat_pred = [Bits(uint=0, length=1) for _ in range(32)]
        for i in range(32):
            if instr.predicate[i].bin == "0":
                continue
            match instr.opcode:
                case B_Op.BEQ:
                    instr.wdat_pred[i] = Bits(uint=(instr.rdat1[i].uint == instr.rdat2[i].uint), length=1)
                case B_Op.BNE:
                    instr.wdat_pred[i] = Bits(uint=(instr.rdat1[i].uint != instr.rdat2[i].uint), length=1)
                case H_Op.HALT:
                    continue
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in Branch.")
        self.data = instr
        
    def tick(self, behind_latch: LatchIF) -> Instruction:
        # Branch unit is assumed to have single-cycle latency for simplicity
        if isinstance(behind_latch, LatchIF):
            in_data = behind_latch.snoop()
        else:
            in_data = None

        if self.ex_wb_interface.ready_for_push():
            if isinstance(in_data, Instruction):
                in_data.mark_fu_enter(self.name, self.perf_count.total_cycles)

            out_data = self.data
            self.data = in_data

            if isinstance(out_data, Instruction):
                out_data.mark_fu_exit(self.name, self.perf_count.total_cycles)

            if isinstance(behind_latch, LatchIF):
                behind_latch.pop()

            self.ready_out = True
        else:
            out_data = False
            self.ready_out = False            

        self._record_cycle(
            instr=in_data, 
            ready_out=self.ready_out, 
            ex_wb_interface_ready=self.ex_wb_interface.ready_for_push(),
        )
        
        return out_data

class Jump(FunctionalSubUnit):
    SUPPORTED_OPS = [
        P_Op.JPNZ, J_Op.JAL, I_Op.JALR
    ]
    def __init__(self, num: int, schedule_if: ForwardingIF = None, telemeter=None):
        super().__init__(num=num, telemeter=telemeter)

        self.schedule_if = schedule_if
        self.data = None
    
    def compute(self):
        if self.schedule_if is None:
            raise ValueError("Jump unit requires a forwarding interface to the Schedule stage for correct operation.")
        instr = self.data
        schedule_if_value = None # defaults to PC + 4, this is signified by pusing None to Schedule Stage Forwarding Interface

        if instr is None or not isinstance(instr, Instruction):
            return
        
        if instr.opcode not in self.SUPPORTED_OPS:
            raise ValueError(f"Jump does not support operation {instr.opcode}")
        
        match instr.opcode:
            case J_Op.JAL:
                schedule_if_value = {"warp": instr.warp_id, "dest": instr.pc.uint + instr.imm.int}
                instr.wdat = [Bits(uint=(instr.pc.uint + 4) & 0xFFFFFFFF, length=32) for x in range(32)]
            case I_Op.JALR:
                if not all(data == instr.rdat1[0] for data in instr.rdat1):
                      raise ValueError("JALR requires all rdat1 values to be the same for correct scheduling.")
                schedule_if_value = {"warp": instr.warp_id, "dest": instr.rdat1[0].uint + instr.imm.int}
                instr.wdat = [Bits(uint=(instr.pc.uint + 4) & 0xFFFFFFFF, length=32) for x in range(32)]
            case P_Op.JPNZ:
                schedule_if_value = {"warp": instr.warp_id, "dest": instr.pc.uint + instr.imm.int if not all(x == Bits(uint=0, length=1) for x in instr.predicate) else instr.pc.uint + 4}
            case _:
                raise ValueError(f"Unsupported operation {instr.opcode} in Jump.")
            
        self.schedule_if.push(schedule_if_value)
        
    def tick(self, behind_latch: LatchIF) -> Instruction:
        if self.schedule_if is None:
            raise ValueError("Jump unit requires a forwarding interface to the Schedule stage for correct operation.")
        # Jump unit is assumed to have single-cycle latency for simplicity
        if isinstance(behind_latch, LatchIF):
            in_data = behind_latch.snoop()
        else:
            in_data = None

        if self.ex_wb_interface.ready_for_push():
            if isinstance(in_data, Instruction):
                in_data.mark_fu_enter(self.name, self.perf_count.total_cycles)

            out_data = self.data
            self.data = in_data
            if isinstance(out_data, Instruction):
                out_data.mark_fu_exit(self.name, self.perf_count.total_cycles)

            if isinstance(behind_latch, LatchIF):
                behind_latch.pop()

            self.ready_out = True
        else:
            out_data = False
            self.ready_out = False            

        self._record_cycle(
            instr=in_data,
            ready_out=self.ready_out,
            ex_wb_interface_ready=self.ex_wb_interface.ready_for_push(),
        )

        return out_data
