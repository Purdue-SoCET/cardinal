from __future__ import annotations
from fileinput import input
from dataclasses import dataclass
from typing import Dict

from aenum import Enum
from bitstring import Bits
from common.custom_enums_multi import H_Op, I_Op, B_Op, P_Op, S_Op
from simulator.issue.regfile import RegisterFile
from simulator.decode.predicate_reg_file import PredicateRegFile
from simulator.instruction import Instruction
from simulator.stage import Stage
from simulator.interfaces import LatchIF, ForwardingIF
from simulator.writeback.writeback_buffer import WritebackBuffer
from simulator.writeback.config import (
    WritebackBufferCount,
    WritebackBufferSize,
    WritebackBufferStructure,
    WritebackBufferPolicy,
    WritebackBufferConfig,
    RegisterFileConfig,
    PredicateRegisterFileConfig,
    WritebackFile,
)
from typing import Union, Optional, Tuple, List

class WritebackStage(Stage):
    def __init__(self, 
        wb_config: WritebackBufferConfig, 
        rf_config: RegisterFileConfig, 
        pred_rf_config: PredicateRegisterFileConfig,
        behind_latches: Dict[str, LatchIF], 
        reg_file: RegisterFile,
        pred_reg_file: PredicateRegFile,
        forward_ifs_write: Dict[str, ForwardingIF] = None,
        forward_ifs_read = None,
        fsu_names: list[str] = None
    ):
        super().__init__(name="Writeback_Stage")
        self.behind_latches = behind_latches
        self.ahead_latch = None
        self.forward_ifs_read = forward_ifs_read
        self.forward_ifs_write = forward_ifs_write
        self.values_to_writeback = {}
        self.total_banks = rf_config.num_banks + pred_rf_config.num_banks
        self.reg_file = reg_file
        self.pred_reg_file = pred_reg_file

        # have to initalize for this to work but the keys will be overwritten by the tick() method when the writeback buffer returns the values to writeback for the cycle, so the initial values don't actually matter
        self.values_to_writeback = {f"bank_{i}":None for i in range(self.total_banks)}

        functional_units_list = []

        self.wb_buffer = WritebackBuffer(
            buffer_config=wb_config,
            regfile_config=rf_config,
            pred_regfile_config=pred_rf_config,
            behind_latches=behind_latches,
            fsu_names=fsu_names
        )

    def compute(self) -> None:
        # Writeback stage does not have functional units to compute
        pass
    
    def tick(self) -> None:
        self._write_to_reg_file()
        self._update_halt_mask_and_decrement_counter()
        self.values_to_writeback = self.wb_buffer.tick()
        if self.values_to_writeback is not None and len(self.values_to_writeback) != self.total_banks:
            # print(f"Error: Expected {self.total_banks} banks, but got {len(self.values_to_writeback)}")
            print(f"Num total banks (reg + pred): {self.total_banks}")
            print(f"Dict length: {len(self.values_to_writeback)}")
            raise ValueError("Number of banks in values_to_writeback does not match total_banks.")
        
    def get_data(self):
        raise NotImplementedError()
    
    def send_output(self) -> None:
        raise NotImplementedError()
    
    def _update_halt_mask_and_decrement_counter(self):
        data_to_scheduler = []
       
        for bank_name, instr in self.values_to_writeback.items():
            if instr is None:
                continue
            print(instr.pc)
            if instr.opcode == H_Op.HALT:
                print("HALT OPCODE")
                #check if the instruction is predicated, if it is then we only want to update the halt mask for the threads that are active based on the predicate bits, if it is not predicated then we want to update the halt mask for all threads in the warp
                pred_bits = Bits(bin=''.join(p.bin for p in instr.predicate))
                new_mask = instr.active_mask & ~pred_bits
            else:
                new_mask = instr.active_mask
            
            data_to_scheduler.append({"warp_group_id": instr.warp_group_id, "warp_id": instr.warp_id, "new_mask": new_mask})
            

        if self.forward_ifs_write is not None and "Writeback_Scheduler" in self.forward_ifs_write:
            self.forward_ifs_write["Writeback_Scheduler"].push(data_to_scheduler)
        else:
            raise ValueError("Forward IF to Scheduler is not set up in WritebackStage.")
        
    def _write_to_reg_file(self):
        if self.values_to_writeback is None:
            return
        for bank_name, instr in self.values_to_writeback.items():
            if instr is None:
                continue
            if instr.opcode == H_Op.HALT:
                continue
            
            for i in range(32):
                if instr.predicate[i].bin == "0" and instr.opcode != B_Op.BEQ and instr.opcode != B_Op.BNE:
                    continue
                
                if isinstance(instr.target_bank, int):
                    if instr.target_regfile is not None and "pred" in instr.target_regfile:
                        # write to predicate reg file
                
                        self.pred_reg_file.write_predicate_thread_gran(
                            prf_wr_en=1,
                            prf_wr_wsel=instr.warp_id,
                            prf_wr_psel=instr.dest_pred,
                            prf_wr_tsel=i,
                            prf_wr_data=(instr.wdat_pred[i])
                        )
                    elif instr.target_regfile is not None:
                        # write to normal reg file
                        self.reg_file.write_thread_gran(
                            dest_operand=instr.rd,
                            data=instr.wdat[i],
                            thread_id=i,
                            warp_id=instr.warp_id
                        )
                    else:
                        raise ValueError("For BUFFER_PER_BANK scheme, target_bank must be an integer (or string) and target_regfile must be specified to determine the correct buffer.")
                    
                elif isinstance(instr.target_bank, str):
                    if "pred" in instr.target_bank:
                        # write to pred reg file
                        self.pred_reg_file.write_predicate_thread_gran(
                            prf_wr_en=1,
                            prf_wr_wsel=instr.warp_id,
                            prf_wr_psel=instr.pred_dest,
                            prf_wr_tsel=i,
                            prf_wr_data=(instr.wdat_pred[i])
                        )
                    else:
                        # write to normal reg file
                        self.reg_file.write_thread_gran(
                            dest_operand=instr.rd,
                            data=instr.wdat[i],
                            thread_id=i,
                            warp_id=instr.warp_id
                        )
                else:
                    raise ValueError("For BUFFER_PER_BANK scheme, target_bank must be an integer (or string) and target_regfile must be specified to determine the correct buffer.")              

    @classmethod
    def create_pipeline_stage(
        cls, 
        wb_config: WritebackBufferConfig, 
        rf_config: RegisterFileConfig, 
        pred_rf_config: PredicateRegisterFileConfig, 
        ex_stage_ahead_latches: Dict[str, LatchIF], 
        reg_file: RegisterFile, 
        pred_reg_file: PredicateRegFile, 
        forward_ifs_write: Dict[str, ForwardingIF],
        fsu_names: list[str]
    ) -> WritebackStage:
        return cls(
            wb_config=wb_config, 
            rf_config=rf_config, 
            pred_rf_config=pred_rf_config, 
            behind_latches=ex_stage_ahead_latches, 
            reg_file=reg_file, 
            pred_reg_file=pred_reg_file, 
            forward_ifs_write=forward_ifs_write, 
            fsu_names=fsu_names
        )