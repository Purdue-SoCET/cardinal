from __future__ import annotations
from circular_buffer import CircularBuffer
from compact_queue import CompactQueue
from stack import Stack
from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union, List
from latch_forward_stage import LatchIF, Instruction
from performance_counter import PerfCount

class WritebackBufferCount(Enum):
    BUFFER_PER_FSU = 0
    BUFFER_PER_BANK = 1

class WritebackBufferSize(Enum):
    FIXED = 0
    VARIABLE = 1

class WritebackBufferStructure(Enum):
    STACK = 0
    QUEUE = 1
    CIRCULAR = 2

class WritebackBufferPolicy(Enum):
    AGE_PRIORITY = 0
    CAPACITY_PRIORITY = 1
    FSU_PRIORITY = 2  

@dataclass
class WritebackBufferConfig:
    count_scheme: WritebackBufferCount
    size_scheme: WritebackBufferSize
    structure: WritebackBufferStructure
    primary_policy: WritebackBufferPolicy
    secondary_policy: WritebackBufferPolicy
    size: Union[Dict[str, int], int]  # Can be a fixed size or a dict mapping FSU names to sizes
    fsu_priority: Optional[Dict[str, int]]  # Priority mapping for FSUs

    @classmethod
    def get_default_config(cls) -> WritebackBufferConfig:
        return cls(
            count_scheme=WritebackBufferCount.BUFFER_PER_FSU,
            size_scheme=WritebackBufferSize.FIXED,
            structure=WritebackBufferStructure.QUEUE,
            primary_policy=WritebackBufferPolicy.CAPACITY_PRIORITY,
            secondary_policy=WritebackBufferPolicy.AGE_PRIORITY,
            size=8,
            fsu_priority=None
        )

    @classmethod
    def get_config_type_one(cls) -> WritebackBufferConfig:
        return cls(
            count_scheme=WritebackBufferCount.BUFFER_PER_FSU,
            size_scheme=WritebackBufferSize.VARIABLE,
            structure=WritebackBufferStructure.CIRCULAR,
            primary_policy=WritebackBufferPolicy.FSU_PRIORITY,
            secondary_policy=WritebackBufferPolicy.CAPACITY_PRIORITY,
            size={
                "Alu_int_0": 16,
                "Mul_int_0": 8,
                "Div_int_0": 4,
                "AddSub_float_0": 16,
                "Mul_float_0": 8,
                "Div_float_0": 4,
                "Sqrt_float_0": 4,
                "Trig_float_0": 4,
                "InvSqrt_float_0": 4,
            },
            fsu_priority={ # 0 is highest priority
                "Alu_int_0": 6,
                "Mul_int_0": 5,
                "Div_int_0": 3,
                "AddSub_float_0": 7,
                "Mul_float_0": 4,
                "Div_float_0": 0,
                "Sqrt_float_0": 8,
                "Trig_float_0": 1,
                "InvSqrt_float_0": 2,
            }
        )
    
    @classmethod
    def get_config_type_two(cls) -> WritebackBufferConfig:
        return cls(
            count_scheme=WritebackBufferCount.BUFFER_PER_BANK,
            size_scheme=WritebackBufferSize.FIXED,
            structure=WritebackBufferStructure.STACK,
            primary_policy=WritebackBufferPolicy.AGE_PRIORITY,
            secondary_policy=WritebackBufferPolicy.FSU_PRIORITY,
            size=32,
            fsu_priority={
                "Alu_int_0": 5,
                "Mul_int_0": 4,
                "Div_int_0": 2,
                "AddSub_float_0": 6,
                "Mul_float_0": 3,
                "Div_float_0": 0,
                "Sqrt_float_0": 7,
                "Trig_float_0": 1,
                "InvSqrt_float_0": 2,
            }
        )

@dataclass
class RegisterFileConfig:
    num_banks: int

    @classmethod
    def get_default_config(cls) -> RegisterFileConfig:
        return cls(num_banks=2)

class WritebackBuffer:
    def __init__(
        self, 
        buffer_config: WritebackBufferConfig, 
        regfile_config: RegisterFileConfig, 
        behind_latches: Dict[str, LatchIF], 
        fsu_names: Optional[List[str]]
    ):
        if buffer_config.count_scheme == WritebackBufferCount.BUFFER_PER_FSU:
            self.count_scheme = WritebackBufferCount.BUFFER_PER_FSU
            self.num_buffers = len(fsu_names)
            self.buffer_names = fsu_names
        elif buffer_config.count_scheme == WritebackBufferCount.BUFFER_PER_BANK:
            self.count_scheme = WritebackBufferCount.BUFFER_PER_BANK
            self.num_buffers = regfile_config.num_banks
            self.buffer_names = [f"bank_{i}" for i in range(self.num_buffers)]
        else:
            raise ValueError("Invalid WritebackBufferCount configuration")
        
        if buffer_config.structure == WritebackBufferStructure.STACK:
            if buffer_config.size_scheme == WritebackBufferSize.FIXED:
                self.buffers = {name: Stack(capacity=buffer_config.size - 1, type_=Instruction) for name in self.buffer_names}
            elif buffer_config.size_scheme == WritebackBufferSize.VARIABLE:
                self.buffers = {name: Stack(capacity=buffer_config.size[name] - 1, type_=Instruction) for name in self.buffer_names}
            else:
                raise ValueError("Invalid WritebackBufferSize configuration for STACK")
            
        elif buffer_config.structure == WritebackBufferStructure.QUEUE:
            if buffer_config.size_scheme == WritebackBufferSize.FIXED:
                self.buffers = {name: CompactQueue(length=buffer_config.size, type_=Instruction) for name in self.buffer_names}
            elif buffer_config.size_scheme == WritebackBufferSize.VARIABLE:
                self.buffers = {name: CompactQueue(length=buffer_config.size[name], type_=Instruction) for name in self.buffer_names}
            else:
                raise ValueError("Invalid WritebackBufferSize configuration for QUEUE")
        
        elif buffer_config.structure == WritebackBufferStructure.CIRCULAR:
            if buffer_config.size_scheme == WritebackBufferSize.FIXED:
                self.buffers = {name: CircularBuffer(capacity=buffer_config.size - 1, type_=Instruction) for name in self.buffer_names}
            elif buffer_config.size_scheme == WritebackBufferSize.VARIABLE:
                self.buffers = {name: CircularBuffer(capacity=buffer_config.size[name] - 1, type_=Instruction) for name in self.buffer_names}
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

        self.behind_latches = behind_latches
        
        # Initialize performance counters for each buffer
        self.perf_counts = {name: PerfCount(name=name) for name in self.buffer_names}
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
        # Determine number of banks from regfile config
        num_banks = 2  # Default, should match regfile_config.num_banks
        
        buffers_to_writeback = {}
        values_to_writeback = {f"bank_{i}": None for i in range(num_banks)}
        
        # Track metrics for each buffer
        stores_this_cycle = {name: False for name in self.buffer_names}
        writebacks_this_cycle = {name: False for name in self.buffer_names}
        
        # Select buffers to writeback - for PER_BANK we iterate banks, for PER_FSU we iterate FSUs
        if self.count_scheme == WritebackBufferCount.BUFFER_PER_BANK:
            # Directly select one buffer per bank
            for bank_name in self.buffer_names:
                match self.primary_policy:
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        buffers_to_writeback[bank_name] = self._find_age_priority_for_writeback(target_bank=bank_name)
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        buffers_to_writeback[bank_name] =  self._find_capacity_priority_for_writeback(target_bank=bank_name)
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        buffers_to_writeback[bank_name] = self._find_fsu_priority_for_writeback(target_bank=bank_name)
                    case _:
                        raise NotImplementedError(f"WritebackBufferPolicy {self.primary_policy} needs tick() implementation")
        else:  # BUFFER_PER_FSU
            # Select best buffer for each target bank
            for i in range(num_banks):
                bank_name = f"bank_{i}"
                match self.primary_policy:
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        buffers_to_writeback[bank_name] = self._find_age_priority_for_writeback(target_bank=bank_name)
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        buffers_to_writeback[bank_name] =  self._find_capacity_priority_for_writeback(target_bank=bank_name)
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        buffers_to_writeback[bank_name] = self._find_fsu_priority_for_writeback(target_bank=bank_name)
                    case _:
                        raise NotImplementedError(f"WritebackBufferPolicy {self.primary_policy} needs tick() implementation")

        for bank, buffer in buffers_to_writeback.items():
            if buffer is not None:
                values_to_writeback[bank] = buffer.pop()
                for i in range(32):
                  values_to_writeback[bank].wdat[i] = None if values_to_writeback[bank].predicate[i].bin == '0' else values_to_writeback[bank].wdat[i]
                # Track writeback for the source buffer
                for buf_name, buf in self.buffers.items():
                    if buf is buffer:
                        writebacks_this_cycle[buf_name] = True
                        break

        data_to_buffers = {name: [] for name in self.buffer_names}
        for latch in self.behind_latches.values():
            in_data = latch.snoop()
            active_threads = 0
            for i in range(32):
                if in_data is not None and in_data.predicate[i].bin == '1':
                    active_threads += 1
            if active_threads == 0:
                # No active threads, just pop to clear latch
                latch.pop()
                continue
            if in_data is not None and in_data.target_bank is not None:
                match self.count_scheme:
                    case WritebackBufferCount.BUFFER_PER_FSU:
                        target_buffer = in_data.intended_FSU
                    case WritebackBufferCount.BUFFER_PER_BANK:
                        target_buffer = f"bank_{in_data.target_bank}"
                    case _:
                        raise NotImplementedError(f"WritebackBufferCount {self.count_scheme} needs tick() implementation")
                
                # Handle both property and method
                buf = self.buffers[target_buffer]
                is_full = buf.is_full() if callable(buf.is_full) else buf.is_full
                if is_full:
                    continue
                #  else
                data_to_buffers[target_buffer].append({'latch': latch, 'in_data': in_data})
            else:
                latch.pop()  # Remove None data so that new data can be pushed next cycle

              
        for target_buffer, in_data_list in data_to_buffers.items():
            if len(in_data_list) == 0:
                continue
            #  else
            if len(in_data_list) == 1:
                in_data = in_data_list[0]['latch'].pop()

                if in_data is None or in_data != in_data_list[0]['in_data']:
                    raise ValueError("Data mismatch during writeback")

                self.buffers[target_buffer].push(in_data)
                stores_this_cycle[target_buffer] = True
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

                self.buffers[target_buffer].push(in_data)
                stores_this_cycle[target_buffer] = True
        
        # Update performance counters for each buffer
        for buffer_name in self.buffer_names:
            buffer = self.buffers[buffer_name]
            buffer_occupancy = len(buffer)
            buffer_capacity = buffer.capacity + 1  # +1 because capacity is stored as (size - 1)
            
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
                stored_this_cycle=stores_this_cycle[buffer_name],
                writeback_this_cycle=writebacks_this_cycle[buffer_name],
                instructions_in_buffer=instructions_in_buffer
            )
        
        self.cycle += 1
                
        return values_to_writeback
    
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
    
    def _find_age_priority_for_writeback(self, target_bank: str):  # -> Buffer
        buffer_with_oldest = None
        for buffer_name, buffer in self.buffers.items():
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
                # Convert bank number to bank name for comparison
                if f"bank_{data.target_bank}" != target_bank:
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

    def _find_capacity_priority_for_writeback(self, target_bank: str):  # -> Buffer
        buffer_with_least_space = None
        for buffer_name, buffer in self.buffers.items():
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
                if f"bank_{data.target_bank}" != target_bank:
                    continue
            #  else
            if buffer_with_least_space is None:
                buffer_with_least_space = buffer
            elif len(buffer) > len(buffer_with_least_space):
                buffer_with_least_space = buffer
            elif len(buffer) == len(buffer_with_least_space):
                match self.secondary_policy:
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        buffer_with_least_space = self._find_age_priority_for_writeback(target_bank, [buffer, buffer_with_least_space])
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        buffer_with_least_space = self._find_fsu_priority_for_writeback(target_bank, [buffer, buffer_with_least_space])
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        buffer_with_least_space = buffer_with_least_space
                    case _:
                        raise NotImplementedError(f"Secondary WritebackBufferPolicy {self.secondary_policy} not implemented")
        
        return buffer_with_least_space

    def _find_fsu_priority_for_store(self, target_buffer: str, data_list: List[Dict[str, Instruction]]) -> Instruction:
        highest_priority_data = None
        highest_priority_value = float('inf')
        
        for data in data_list:
            fsu_name = data['in_data'].intended_FSU
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

    def _find_fsu_priority_for_writeback(self, target_bank: str):  # -> Buffer
        buffer_with_highest_priority = None
        highest_priority_value = float('inf')
        
        for buffer_name, buffer in self.buffers.items():
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
                if f"bank_{data.target_bank}" != target_bank:
                    continue
            #  else
            fsu_name = data.intended_FSU
            priority_value = self.fsu_priority.get(fsu_name, float('inf'))
            
            if priority_value < highest_priority_value:
                highest_priority_value = priority_value
                buffer_with_highest_priority = buffer
            elif priority_value == highest_priority_value:
                match self.secondary_policy:
                    case WritebackBufferPolicy.AGE_PRIORITY:
                        buffer_with_highest_priority = self._find_age_priority_for_writeback(target_bank, [buffer, buffer_with_highest_priority])
                    case WritebackBufferPolicy.CAPACITY_PRIORITY:
                        buffer_with_highest_priority = self._find_capacity_priority_for_writeback(target_bank, [buffer, buffer_with_highest_priority])
                    case WritebackBufferPolicy.FSU_PRIORITY:
                        buffer_with_highest_priority = buffer_with_highest_priority
                    case _:
                        raise NotImplementedError(f"Secondary WritebackBufferPolicy {self.secondary_policy} not implemented")
        
        return buffer_with_highest_priority
