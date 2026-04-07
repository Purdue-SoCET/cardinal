from __future__ import annotations

from bitstring import Bits
from simulator.utils.data_structures.circular_buffer import CircularBuffer
from simulator.utils.data_structures.compact_queue import CompactQueue
from simulator.utils.data_structures.stack import Stack
from typing import Any, Dict, Optional, Union, List
from common.custom_enums_multi import H_Op, I_Op, B_Op, P_Op, S_Op
from simulator.interfaces import LatchIF
from simulator.instruction import Instruction
from simulator.utils.performance_counter.writeback import WritebackPerfCount as PerfCount
from simulator.writeback.config import (
    WritebackBufferCount,
    WritebackBufferSize,
    WritebackBufferStructure,
    WritebackBufferPolicy,
    WritebackBufferConfig,
    RegisterFileConfig,
    PredicateRegisterFileConfig,
)

class WritebackBuffer:
    def __init__(
        self, 
        buffer_config: WritebackBufferConfig, 
        regfile_config: RegisterFileConfig, 
        pred_regfile_config: PredicateRegisterFileConfig,
        behind_latches: Dict[str, LatchIF], 
        fsu_names: Optional[List[str]]
    ):
        if buffer_config.count_scheme == WritebackBufferCount.BUFFER_PER_FSU:
            self.count_scheme = WritebackBufferCount.BUFFER_PER_FSU
            self.num_buffers = len(fsu_names)
            buffer_names = fsu_names
        elif buffer_config.count_scheme == WritebackBufferCount.BUFFER_PER_BANK:
            self.count_scheme = WritebackBufferCount.BUFFER_PER_BANK
            self.num_buffers = regfile_config.num_banks + pred_regfile_config.num_banks
            buffer_names = [f"regfile_bank_{i}" for i in range(regfile_config.num_banks)] + \
                                [f"pred_regfile_bank_{i}" for i in range(pred_regfile_config.num_banks)]
        else:
            raise ValueError("Invalid WritebackBufferCount configuration")
        
        if buffer_config.structure == WritebackBufferStructure.STACK:
            if buffer_config.size_scheme == WritebackBufferSize.FIXED:
                self.buffers = {name: Stack(capacity=buffer_config.size - 1, type_=Instruction) for name in buffer_names}
            elif buffer_config.size_scheme == WritebackBufferSize.VARIABLE:
                self.buffers = {name: Stack(capacity=buffer_config.size[name] - 1, type_=Instruction) for name in buffer_names}
            else:
                raise ValueError("Invalid WritebackBufferSize configuration for STACK")
            
        elif buffer_config.structure == WritebackBufferStructure.QUEUE:
            if buffer_config.size_scheme == WritebackBufferSize.FIXED:
                self.buffers = {name: CompactQueue(length=buffer_config.size, type_=Instruction) for name in buffer_names}
            elif buffer_config.size_scheme == WritebackBufferSize.VARIABLE:
                self.buffers = {name: CompactQueue(length=buffer_config.size[name], type_=Instruction) for name in buffer_names}
            else:
                raise ValueError("Invalid WritebackBufferSize configuration for QUEUE")
        
        elif buffer_config.structure == WritebackBufferStructure.CIRCULAR:
            if buffer_config.size_scheme == WritebackBufferSize.FIXED:
                self.buffers = {name: CircularBuffer(capacity=buffer_config.size - 1, type_=Instruction) for name in buffer_names}
            elif buffer_config.size_scheme == WritebackBufferSize.VARIABLE:
                self.buffers = {name: CircularBuffer(capacity=buffer_config.size[name] - 1, type_=Instruction) for name in buffer_names}
            else:
                raise ValueError("Invalid WritebackBufferSize configuration for CIRCULAR")

        else:
            raise ValueError("Invalid WritebackBufferStructure configuration")

        if buffer_config.primary_policy == buffer_config.secondary_policy:
            raise ValueError("Primary and secondary policies must be different")
        self.primary_policy = buffer_config.primary_policy
        self.secondary_policy = buffer_config.secondary_policy

        if self.primary_policy == WritebackBufferPolicy.FSU_PRIORITY or self.secondary_policy == WritebackBufferPolicy.FSU_PRIORITY:
            if buffer_config.fsu_priority is None:
                raise ValueError("FSU priority mapping must be provided for FSU_PRIORITY policy")
            self.fsu_priority = buffer_config.fsu_priority
        
        self.bank_names = []
        for i in range(regfile_config.num_banks):
            self.bank_names.append(f"regfile_bank_{i}")
        for i in range(pred_regfile_config.num_banks):
            self.bank_names.append(f"pred_regfile_bank_{i}")
              

        self.behind_latches = behind_latches
        self.total_banks = regfile_config.num_banks + pred_regfile_config.num_banks

        # Initialize performance counters for each buffer
        self.perf_counts = {name: PerfCount(name=name) for name in buffer_names}
        self.cycle = 0
            
    def push(self, buffer: str, in_data: Instruction) -> None:
        """Push data to buffer at <buffer>."""
        self.buffers[buffer].push(in_data)

    def pop(self, buffer: str) -> Instruction:
        return self.buffers[buffer].pop()

    def is_full(self, buffer: str) -> bool:
        """Check if buffer at <buffer> is full."""
        buf = self.buffers[buffer]
        # Handle both property and method
        if callable(buf.is_full):
            return buf.is_full()
        else:
            return buf.is_full

    def is_empty(self, buffer: str) -> bool:
        """Check if buffer at <buffer> is empty."""
        buf = self.buffers[buffer]
        # Handle both property and method
        if callable(buf.is_empty):
            return buf.is_empty()
        else:
            return buf.is_empty
    
    def export_perf_counts(self, directory: str = ".") -> None:
        """Export all performance counters to CSV files."""
        # Export individual buffer stats
        for buffer_name, perf_count in self.perf_counts.items():
            perf_count.to_csv(directory=directory)
        
        # Export combined stats
        PerfCount.to_combined_csv(list(self.perf_counts.values()), directory=directory)
    
    def clear_all_buffers(self) -> None:
        """Clear all buffers and reset cycle counter (useful for testing)."""
        for buffer in self.buffers.values():
            # Clear based on buffer type
            if hasattr(buffer, 'queue'):
                # CompactQueue
                buffer.queue = [None for _ in range(buffer.length)]
            elif hasattr(buffer, 'items'):
                # Stack
                buffer.items = []
            elif hasattr(buffer, 'buffer'):
                # CircularBuffer
                buffer.head = 0
                buffer.tail = 0
                buffer.size = 0
                buffer.buffer = [None for _ in range(buffer.capacity + 1)]
    
    def tick(self) -> Dict[str, Optional[Instruction]]:
        """Tick all buffers and return data based on policy, organized by target bank."""
        # For BUFFER_PER_BANK, buffer_names are bank names
        # For BUFFER_PER_FSU, buffer_names are FSU names, but we need to return data keyed by bank

        values_to_store = {} # data coming from the execute stage that will be stored into the writeback buffer
        buffers_to_writeback = {} # buffers that have been selected to pop from and write back to the register file this cycle, keyed by buffer name
        values_to_writeback = {} # data from the buffers that will be written back to the register file this cycle, keyed by bank name

        values_to_store = self._select_values_to_store()
        buffers_to_writeback = self._select_buffers_for_writeback()
        values_to_writeback = self._get_values_from_buffers(buffers_to_writeback)

        for buffer_name, data in values_to_store.items():
            if data is not None:
                self.buffers[buffer_name].push(data)

        self._update_perf_counts(values_to_writeback=values_to_writeback, values_to_store = values_to_store)

        self.cycle += 1
        
        return values_to_writeback
           
    def _update_perf_counts(self, values_to_writeback: Dict[str, Optional[Instruction]], values_to_store: Dict[str, Optional[Instruction]]) -> None:
         # Update performance counters for each buffer
        for buffer_name, buffer in self.buffers.items():
            writeback_this_cycle = False
            store_this_cycle = False
            
            buffer_occupancy = len(buffer)
            buffer_capacity = buffer.capacity + 1  # +1 because capacity is stored as (size - 1)

            if buffer_name in values_to_writeback.keys() and values_to_writeback[buffer_name] is not None:
                writeback_this_cycle = True
            if buffer_name in values_to_store.keys() and values_to_store[buffer_name] is not None:
                store_this_cycle = True
            
            # Get instructions in buffer for age tracking
            instructions_in_buffer = []
            if hasattr(buffer, 'queue'):
                instructions_in_buffer = [instr for instr in buffer.queue if instr is not None]
            elif hasattr(buffer, 'stack'):
                instructions_in_buffer = [instr for instr in buffer.stack if instr is not None]
            elif hasattr(buffer, 'buffer'):
                instructions_in_buffer = [instr for instr in buffer.buffer if instr is not None]
            
            self.perf_counts[buffer_name].increment(
                cycle=self.cycle,
                buffer_occupancy=buffer_occupancy,
                buffer_capacity=buffer_capacity,
                stored_this_cycle=store_this_cycle,
                writeback_this_cycle=writeback_this_cycle,
                instructions_in_buffer=instructions_in_buffer
            )
                            
    def _get_values_from_buffers(self, buffers_to_writeback: Dict[str, Any]) -> Dict:
        
        values = {bank_name:None for bank_name in self.bank_names} 

        for bank, buffer in buffers_to_writeback.items():
            if buffer is not None:
                values[bank] = buffer.pop()

                if values[bank] is None:
                    continue

                for i in range(32):
                    values[bank].wdat[i] = None if values[bank].predicate[i].bin == "0" else values[bank].wdat[i]


        return values

    def _select_values_to_store(self) -> List[Instruction]:
        # Select values to store - for PER_BANK we iterate banks, for PER_FSU we iterate FSUs
        values_to_store = {}
        data_to_buffers = {name: [] for name in self.buffers.keys()}

        for latch in self.behind_latches.values():
            in_data = latch.snoop()
            if in_data is None:
                # No instruction, just pop to clear latch
                latch.pop()
                continue
            match self.count_scheme:
                case WritebackBufferCount.BUFFER_PER_FSU:
                    target_buffer = in_data.intended_FU
                case WritebackBufferCount.BUFFER_PER_BANK:
                    if isinstance(in_data.target_bank, int):
                        if in_data.target_regfile is not None and "pred" in in_data.target_regfile:
                            target_buffer = f"pred_regfile_bank_{in_data.target_bank}"
                        elif in_data.target_regfile is not None:
                            target_buffer = f"regfile_bank_{in_data.target_bank}"
                        else:
                            raise ValueError("For BUFFER_PER_BANK scheme, target_bank must be an integer (or string) and target_regfile must be specified to determine the correct buffer.")
                    elif isinstance(in_data.target_bank, str):
                        target_buffer = in_data.target_bank
                    else:
                        raise ValueError("For BUFFER_PER_BANK scheme, target_bank must be an integer (or string) and target_regfile must be specified to determine the correct buffer.")
                case _:
                    raise NotImplementedError(f"WritebackBufferCount {self.count_scheme} needs tick() implementation")
            
            # Handle both property and method
            buf = self.buffers[target_buffer]
            is_full = buf.is_full() if callable(buf.is_full) else buf.is_full
            if is_full:
                continue
            #  else
            data_to_buffers[target_buffer].append({'latch': latch, 'in_data': in_data}) # use append here because in BUFFER_PER_BANK scheme, multiple FSUs might attemp to write to the same buffer, so we need to consider all instructions targeting the same bank together for selection based on policy

              
        for target_buffer, in_data_list in data_to_buffers.items():
            if len(in_data_list) == 0:
                continue
            #  else
            if len(in_data_list) == 1:
                in_data = in_data_list[0]['latch'].pop()

                if in_data is None or in_data != in_data_list[0]['in_data']:
                    raise ValueError("Data mismatch during writeback")

                values_to_store[target_buffer] = in_data
            else:
                match self.primary_policy:
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        highest_priority_data= self._find_age_priority_for_store(target_buffer, in_data_list) 
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                       highest_priority_data = self._find_capacity_priority_for_store(target_buffer, in_data_list)
                    case WritebackBufferPolicy.FSU_PRIORITY:
                       highest_priority_data = self._find_fsu_priority_for_store(target_buffer, in_data_list)
                    case _:
                        raise NotImplementedError(f"WritebackBufferPolicy {self.primary_policy} needs store() implementation")
                
                in_data = highest_priority_data['latch'].pop()

                if in_data is None or in_data != highest_priority_data['in_data']:
                    raise ValueError("Data mismatch during writeback")

                values_to_store[target_buffer] = in_data
          
        return values_to_store


    def _select_buffers_for_writeback(self) -> Dict[str, Any]:
        # Select buffers to writeback - for PER_BANK we iterate banks, for PER_FSU we iterate FSUs
        buffers_to_writeback = {}
        
        for bank_name in self.bank_names:
            match self.primary_policy:
                case WritebackBufferPolicy.AGE_PRIORITY:
                    buffers_to_writeback[bank_name] = self._find_age_priority_for_writeback(target_bank=bank_name)
                case WritebackBufferPolicy.CAPACITY_PRIORITY:
                    buffers_to_writeback[bank_name] = self._find_capacity_priority_for_writeback(target_bank=bank_name)
                case WritebackBufferPolicy.FSU_PRIORITY:
                    buffers_to_writeback[bank_name] = self._find_fsu_priority_for_writeback(target_bank=bank_name)
                case _:
                    raise NotImplementedError(f"WritebackBufferPolicy {self.primary_policy} needs tick() implementation")
        
        return buffers_to_writeback
    
    def _find_age_priority_for_store(self, target_buffer: str, data_list: List[Dict[str, Instruction]]) -> Instruction:
        """Store data based on AGE_PRIORITY policy."""
        oldest_data = None
        for data in data_list:
            if oldest_data is None:
                oldest_data = data

            elif data['in_data'].issued_cycle < oldest_data['in_data'].issued_cycle:
                oldest_data = data
            
            elif data['in_data'].issued_cycle == oldest_data['in_data'].issued_cycle:
                match self.secondary_policy:
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        oldest_data = self._find_capacity_priority_for_store(target_buffer, [data, oldest_data])
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        oldest_data = self._find_fsu_priority_for_store(target_buffer, [data, oldest_data])
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        oldest_data = oldest_data
                    case _:
                        raise NotImplementedError(f"Secondary WritebackBufferPolicy {self.secondary_policy} not implemented") 
                        
        return oldest_data
    
    def _find_age_priority_for_writeback(self, target_bank: str, buffers: List[Dict[str, Any]] = None):  # -> Buffer
        buffer_with_oldest = None

        if buffers is None:
            buffers = self.buffers

        for buffer_name, buffer in buffers.items():
            # Skip buffers that don't match the target
            if self.count_scheme == WritebackBufferCount.BUFFER_PER_BANK:
                # For per-bank scheme, target_bank IS the buffer name
                if buffer_name != target_bank:
                    continue
                
            # For BUFFER_PER_FSU, we need to check the instruction's target bank
            data = buffer.snoop()
            if data is None:
                continue
                
            # For per-FSU scheme, check if instruction targets the right bank
            if self.count_scheme == WritebackBufferCount.BUFFER_PER_FSU:
                if data.target_bank is None:
                    continue
                
                if data.target_bank > 9:
                    raise NotImplementedError("Only single digit bank ID numbers are supported in the Writeback Buffer. (why do you even have more than 10 banks??? the crossbar would be huge...)")
                    
                if data.target_bank != int(target_bank[-1]): # ONLY SUPPORTS SINGLE DIGIT BANK ID NUMBERS
                    continue
            
            #  else
            if buffer_with_oldest is None:
                buffer_with_oldest = buffer
            elif data.issued_cycle < buffer_with_oldest.snoop().issued_cycle:
                buffer_with_oldest = buffer
            elif data.issued_cycle == buffer_with_oldest.snoop().issued_cycle:
                match self.secondary_policy:
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        buffer_with_oldest = self._find_capacity_priority_for_writeback(target_bank, [buffer, buffer_with_oldest])
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        buffer_with_oldest = self._find_fsu_priority_for_writeback(target_bank, [buffer, buffer_with_oldest])
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        buffer_with_oldest = buffer_with_oldest
                    case _:
                        raise NotImplementedError(f"Secondary WritebackBufferPolicy {self.secondary_policy} not implemented")

        return buffer_with_oldest
        
    def _find_capacity_priority_for_store(self, target_buffer: str, data_list: List[Dict[str, Instruction]]) -> Instruction:
        highest_priority_data = None
        match self.secondary_policy:
            case WritebackBufferPolicy.FSU_PRIORITY:
                highest_priority_data = self._find_fsu_priority_for_store(target_buffer, data_list)
            case WritebackBufferPolicy.AGE_PRIORITY:
                highest_priority_data = self._find_age_priority_for_store(target_buffer, data_list)
            case WritebackBufferPolicy.CAPACITY_PRIORITY:
                highest_priority_data = data_list[0]
            case _:
                raise NotImplementedError("Capacity priority with secondary policy not implemented")
        
        return highest_priority_data

    def _find_capacity_priority_for_writeback(self, target_bank: str, buffers: List[Dict[str, Any]] = None):  # -> Buffer
        buffer_with_least_space = None

        if buffers is None:
            buffers = self.buffers

        for buffer_name, buffer in buffers.items():  # Only consider specific file type for writeback
            # Skip buffers that don't match the target
            if self.count_scheme == WritebackBufferCount.BUFFER_PER_BANK:
                if buffer_name != target_bank:
                    continue
            
            data = buffer.snoop()
            if data is None:
                continue
                
            # For per-FSU scheme, check if instruction targets the right bank
            if self.count_scheme == WritebackBufferCount.BUFFER_PER_FSU:
                if data.target_bank is None:
                    continue
                if data.target_bank > 9:
                    raise NotImplementedError("Only single digit bank ID numbers are supported in the Writeback Buffer. (why do you even have more than 10 banks??? the crossbar would be huge...)")
                
                if data.target_bank != int(target_bank[-1]):
                    continue
            #  else
            if buffer_with_least_space is None:
                buffer_with_least_space = buffer
                buffer_with_least_space_name = buffer_name
            elif len(buffer) > len(buffer_with_least_space):
                buffer_with_least_space = buffer
            elif len(buffer) == len(buffer_with_least_space):
                match self.secondary_policy:
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        buffer_with_least_space = self._find_age_priority_for_writeback(target_bank, {buffer_name: buffer, buffer_with_least_space_name: buffer_with_least_space})
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        buffer_with_least_space = self._find_fsu_priority_for_writeback(target_bank, {buffer_name: buffer, buffer_with_least_space_name: buffer_with_least_space})
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        buffer_with_least_space = buffer_with_least_space
                    case _:
                        raise NotImplementedError(f"Secondary WritebackBufferPolicy {self.secondary_policy} not implemented")
        
        return buffer_with_least_space

    def _find_fsu_priority_for_store(self, target_buffer: str, data_list: List[Dict[str, Instruction]]) -> Instruction:
        highest_priority_data = None
        highest_priority_value = float('inf')
        
        for data in data_list:
            fsu_name = data['in_data'].intended_FU
            priority_value = self.fsu_priority.get(fsu_name, float('inf'))
            
            if priority_value < highest_priority_value:
                highest_priority_value = priority_value
                highest_priority_data = data
            elif priority_value == highest_priority_value:
                match self.secondary_policy:
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        highest_priority_data = self._find_age_priority_for_store(target_buffer, [data, highest_priority_data])
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        highest_priority_data = self._find_capacity_priority_for_store(target_buffer, [data, highest_priority_data])
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        highest_priority_data = highest_priority_data
                    case _:
                        raise NotImplementedError(f"Secondary WritebackBufferPolicy {self.secondary_policy} not implemented")
            
        return highest_priority_data

    def _find_fsu_priority_for_writeback(self, target_bank: str, buffers: List[Dict[str, Any]] = None):  # -> Buffer
        buffer_with_highest_priority = None
        highest_priority_value = float('inf')

        if buffers is None:
            buffers = self.buffers
        
        for buffer_name, buffer in buffers.items():
            # Skip buffers that don't match the target
            if self.count_scheme == WritebackBufferCount.BUFFER_PER_BANK:
                if buffer_name != target_bank:
                    continue
            
            data = buffer.snoop()
            if data is None:
                continue
                
            # For per-FSU scheme, check if instruction targets the right bank
            if self.count_scheme == WritebackBufferCount.BUFFER_PER_FSU:
                if data.target_bank is None:
                    continue
                
                if data.target_bank > 9:
                    raise NotImplementedError("Only single digit bank ID numbers are supported in the Writeback Buffer. (why do you even have more than 10 banks??? the crossbar would be huge...)")
                
                if data.target_bank != int(target_bank[-1]):
                    continue
            #  else
            fsu_name = data.intended_FU
            priority_value = self.fsu_priority.get(fsu_name, float('inf'))
            
            if priority_value < highest_priority_value:
                highest_priority_value = priority_value
                buffer_with_highest_priority = buffer
                buffer_with_highest_priority_name = buffer_name
            elif priority_value == highest_priority_value:
                match self.secondary_policy:
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        buffer_with_highest_priority = self._find_age_priority_for_writeback(target_bank, {buffer_name: buffer, buffer_with_highest_priority_name: buffer_with_highest_priority})
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        buffer_with_highest_priority = self._find_capacity_priority_for_writeback(target_bank, {buffer_name: buffer, buffer_with_highest_priority_name: buffer_with_highest_priority})
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        buffer_with_highest_priority = buffer_with_highest_priority
                    case _:
                        raise NotImplementedError(f"Secondary WritebackBufferPolicy {self.secondary_policy} not implemented")
        
        return buffer_with_highest_priority
    