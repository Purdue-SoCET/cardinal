#!/usr/bin/env python3
"""
Custom ISA Assembler
Translates assembly (.s) files to binary machine code
Supports predication, packet start/end bits, and little-endian encoding
"""

import re
import sys
from typing import Dict, List, Tuple, Optional

# Instruction format categorization
R_TYPE = {'add', 'sub', 'mul', 'div', 'and', 'xor', 'or', 'slt', 'sltu',
          'addf', 'subf', 'mulf', 'divf', 'sll', 'srl', 'sra'}
I_TYPE = {'addi', 'subi', 'xori', 'ori', 'slti', 'sltiu', 'slli', 'srli', 'srai',
          'lw', 'lh', 'lb'}
F_TYPE = {'isqrt', 'sin', 'cos', 'itof', 'ftoi'}
S_TYPE = {'sw', 'sh', 'sb'}
B_TYPE = {'beq', 'bne', 'bge', 'bgeu', 'blt', 'bltu', 'beqf', 'bnef', 'bgef', 'bltf'}
U_TYPE = {'auipc', 'lli', 'lmi', 'lui'}
C_TYPE = {'csrr'}
J_TYPE = {'jal'}
P_TYPE = {'jpnz', 'prr', 'prw'}
H_TYPE = {'halt'}

# Instructions without predication
NO_PREDICATE = {'halt', 'prw', 'prr', 'jpnz', 'jal', 'jalr'}


def load_opcodes(opcode_file: str) -> Dict[str, str]:
    """Load opcodes from specification file"""
    opcodes = {}
    with open(opcode_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                mnemonic = parts[0].lower()
                binary = parts[1]
                opcodes[mnemonic] = binary
    return opcodes


class Assembler:
    def __init__(self, opcodes: Dict[str, str]):
        self.opcodes = opcodes
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[int, str, List[str]]] = []
        self.pc = 0x0000
        
    def parse_register(self, reg: str) -> int:
        """Parse register name (x0-x63) to register number"""
        reg = reg.strip().lower()
        if reg.startswith('x'):
            num = int(reg[1:])
            if 0 <= num <= 63:
                return num
        raise ValueError(f"Invalid register: {reg}")
    
    def parse_csr(self, reg: str) -> int:
        """Parse csr name (x0-x1023) to register number"""
        reg = reg.strip().lower()
        if reg.startswith('x'):
            num = int(reg[1:])
            if 0 <= num <= 1023:
                return num
        raise ValueError(f"Invalid register: {reg}")
    
    def parse_predicate(self, pred: str) -> int:
        """Parse predicate (p0-p31 or 0-31) to predicate number"""
        pred = pred.strip().lower()
        if pred.startswith('p'):
            num = int(pred[1:])
        else:
            num = int(pred)
        if 0 <= num <= 31:
            return num
        raise ValueError(f"Invalid predicate: {pred}")
    
    def parse_immediate(self, imm: str) -> int:
        """Parse immediate value (decimal or hex)"""
        imm = imm.strip()
        if imm.startswith('0x'):
            return int(imm, 16)
        elif imm.startswith('0b'):
            return int(imm, 2)
        else:
            return int(imm)
    
    def parse_mem_operand(self, operand: str) -> Tuple[int, int]:
        """Parse memory operand like 'imm(rs)' and return (imm, rs)"""
        operand = operand.strip()
        match = re.match(r'(-?\d+|0x[0-9a-fA-F]+)\(x(\d+)\)', operand)
        if not match:
            raise ValueError(f"Invalid memory operand format: {operand}. Expected 'imm(xN)'")
        imm = self.parse_immediate(match.group(1))
        rs = int(match.group(2))
        if rs < 0 or rs > 63:
            raise ValueError(f"Invalid register in memory operand: x{rs}")
        return imm, rs
    
    def check_immediate_fits(self, value: int, bits: int, signed: bool = True):
        """Check if immediate value fits in specified number of bits"""
        if signed:
            min_val = -(1 << (bits - 1))
            max_val = (1 << (bits - 1)) - 1
        else:
            min_val = 0
            max_val = (1 << bits) - 1
        
        if value < min_val or value > max_val:
            raise ValueError(f"Immediate value {value} does not fit in {bits} bits (range: {min_val} to {max_val})")
    
    def to_binary(self, value: int, bits: int, signed: bool = True) -> str:
        """Convert integer to binary string of specified width"""
        if signed:
            # Two's complement for negative numbers
            if value < 0:
                value = (1 << bits) + value
        mask = (1 << bits) - 1
        return format(value & mask, f'0{bits}b')
    
    def parse_optional_operands(self, operands: List[str], opcode: str, required_operands: int) -> Tuple[int, int, int]:
        """
        Parse optional predicate, start, end operands from the end of operands list
        Returns: (predicate, start, end) and modifies operands list in place
        
        required_operands: number of mandatory operands before optional ones
        """
        predicate = 0
        start = 0
        end = 1
        
        # Instructions without predication support
        
        # Only look for optional operands if we have more than required
        if len(operands) <= required_operands:
            return predicate, start, end
        
        # Check if we have optional operands at the end
        # They can be: pred, start, end OR just pred, start OR just pred
        extra_count = 0
        temp_operands = operands[:]
        
        # Try to parse from the end, but only if we have extras
        if len(temp_operands) > required_operands:
            # Try parsing end bit (0 or 1)
            try:
                last = temp_operands[-1].strip()
                if last in ['0', '1'] and len(temp_operands) > required_operands + 1:
                    # Only consume if there are more operands after this
                    end = int(last)
                    temp_operands.pop()
                    extra_count += 1
            except:
                pass
        
        if len(temp_operands) > required_operands and extra_count > 0:
            # Try parsing start bit (0 or 1)
            try:
                last = temp_operands[-1].strip()
                if last in ['0', '1'] and len(temp_operands) > required_operands + 1:
                    start = int(last)
                    temp_operands.pop()
                    extra_count += 1
            except:
                pass
        
        if len(temp_operands) > required_operands:
            # Try parsing predicate (could be at the end even without start/end)
            try:
                last = temp_operands[-1].strip().lower()
                if last.startswith('p') or (last.isdigit() and int(last) <= 31):
                    predicate = self.parse_predicate(last)
                    temp_operands.pop()
                    extra_count += 1
            except:
                pass
        
        # Update original operands list
        for _ in range(extra_count):
            operands.pop()
        
        if opcode in NO_PREDICATE:
            return 0, start, end

        return predicate, start, end
    
    def first_pass(self, lines: List[str]):
        """First pass: collect labels and track addresses"""
        for line in lines:
            # Remove comments
            line = line.split('#')[0].split(';')[0].strip()
            if not line:
                continue
            
            # Check for label
            if ':' in line:
                parts = line.split(':', 1)
                label = parts[0].strip()
                self.labels[label] = self.pc
                line = parts[1].strip() if len(parts) > 1 else ''
                if not line:
                    continue
            
            # Check for org directive
            if line.startswith('org'):
                addr_str = line.split()[1]
                self.pc = self.parse_immediate(addr_str)
                continue
            
            # Parse instruction
            # Split on whitespace first to get opcode
            parts = line.split(None, 1)
            if not parts:
                continue
            
            opcode = parts[0].lower()
            
            if opcode in self.opcodes:
                # Parse operands more carefully to preserve zeros
                if len(parts) > 1:
                    operand_str = parts[1]
                    # Split on commas and strip whitespace from each operand
                    operands = [op.strip() for op in operand_str.split(',') if op.strip()]
                else:
                    operands = []
                
                self.instructions.append((self.pc, opcode, operands))
                self.pc += 4  # Each instruction is 4 bytes
        print(self.labels)
    
    def second_pass(self) -> List[str]:
        """Second pass: generate machine code"""
        machine_code = []
        
        for addr, opcode, operands in self.instructions:
            binary = self.encode_instruction(addr, opcode, operands)
            machine_code.append(binary)
        
        return machine_code
    
    def encode_instruction(self, addr: int, opcode: str, operands: List[str]) -> str:
        """Encode a single instruction to binary (little-endian with opcode at LSB)"""
        op_bits = self.opcodes[opcode]
        
        # Determine required operands count for each instruction type
        if opcode in R_TYPE:
            required_ops = 3  # rd, rs1, rs2
        elif opcode in I_TYPE:
            required_ops = 3  # rd, rs1, imm (or rd, imm(rs1))
        elif opcode == 'jalr':
            required_ops = 2  # rd, imm(rs1) or rd, rs1, imm -> actually 3 in second form
            # Check if memory syntax or register syntax
            if len(operands) > 0 and '(' in operands[1] if len(operands) > 1 else False:
                required_ops = 2
            else:
                required_ops = 3
        elif opcode in F_TYPE:
            required_ops = 2  # rd, rs1
        elif opcode in S_TYPE:
            required_ops = 3  # rs2, rs1, imm (or rs2, imm(rs1))
        elif opcode in B_TYPE:
            required_ops = 3  # pred_dest, rs1, rs2
        elif opcode in U_TYPE:
            required_ops = 2  # rd, imm
        elif opcode in C_TYPE:
            required_ops = 2  # rd, csr
        elif opcode in J_TYPE:
            required_ops = 2  # rd, imm/label
        elif opcode in P_TYPE:
            required_ops = 2  # rs1, rs2
        elif opcode in H_TYPE:
            required_ops = 0  # no operands
        else:
            required_ops = len(operands)  # fallback
        
        # Parse optional operands (modifies operands list)
        predicate, start, end = self.parse_optional_operands(operands, opcode, required_ops)
        
        if opcode in R_TYPE:
            # R-type: [end[31], start[30], pred[29:25], rs2[24:19], rs1[18:13], rd[12:7], opcode[6:0]]
            rd = self.parse_register(operands[0])
            rs1 = self.parse_register(operands[1])
            rs2 = self.parse_register(operands[2])
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   self.to_binary(predicate, 5) + self.to_binary(rs2, 6) + 
                   self.to_binary(rs1, 6) + self.to_binary(rd, 6) + op_bits)
        
        elif opcode in I_TYPE:
            # I-type: [end[31], start[30], pred[29:25], imm[24:19], rs1[18:13], rd[12:7], opcode[6:0]]
            rd = self.parse_register(operands[0])
            
            # Load instructions support both formats:
            # lw rd, imm(rs1) OR lw rd, rs1, imm
            if opcode in {'lw', 'lh', 'lb'}:
                # Check if second operand contains parentheses (memory syntax)
                if '(' in operands[1]:
                    imm, rs1 = self.parse_mem_operand(operands[1])
                else:
                    # Register-based syntax: rd, rs1, imm
                    rs1 = self.parse_register(operands[1])
                    imm = self.parse_immediate(operands[2])
            else:
                # Regular I-type: rd, rs1, imm
                rs1 = self.parse_register(operands[1])
                imm = self.parse_immediate(operands[2])
            
            self.check_immediate_fits(imm, 6, signed=True)
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   self.to_binary(predicate, 5) + self.to_binary(imm, 6) + 
                   self.to_binary(rs1, 6) + self.to_binary(rd, 6) + op_bits)
        
        elif opcode == 'jalr':
            # JALR is special I-type without predication: [end, start, 0s, imm[24:19], rs1, rd, opcode]
            # Supports both formats: jalr rd, imm(rs1) OR jalr rd, rs1, imm
            rd = self.parse_register(operands[0])
            if '(' in operands[1]:
                imm, rs1 = self.parse_mem_operand(operands[1])
            else:
                rs1 = self.parse_register(operands[1])
                imm = self.parse_immediate(operands[2])
            self.check_immediate_fits(imm, 6, signed=True)
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   '00000' + self.to_binary(imm, 6) + 
                   self.to_binary(rs1, 6) + self.to_binary(rd, 6) + op_bits)
        
        elif opcode in F_TYPE:
            # F-type: [end[31], start[30], pred[29:25], x[24:19], rs1[18:13], rd[12:7], opcode[6:0]]
            rd = self.parse_register(operands[0])
            rs1 = self.parse_register(operands[1])
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   self.to_binary(predicate, 5) + '000000' + 
                   self.to_binary(rs1, 6) + self.to_binary(rd, 6) + op_bits)
        
        elif opcode in S_TYPE:
            # S-type: [end[31], start[30], pred[29:25], rs2[24:19], rs1[18:13], imm[12:7], opcode[6:0]]
            # Store instructions support both formats:
            # sw rs2, imm(rs1) OR sw rs2, rs1, imm
            rs2 = self.parse_register(operands[0])
            
            # Check if second operand contains parentheses (memory syntax)
            if '(' in operands[1]:
                imm, rs1 = self.parse_mem_operand(operands[1])
            else:
                # Register-based syntax: rs2, rs1, imm
                rs1 = self.parse_register(operands[1])
                imm = self.parse_immediate(operands[2])
            
            self.check_immediate_fits(imm, 6, signed=True)
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   self.to_binary(predicate, 5) + self.to_binary(rs2, 6) + 
                   self.to_binary(rs1, 6) + self.to_binary(imm, 6) + op_bits)
        
        elif opcode in B_TYPE:
            # B-type: [end[31], start[30], pred[29:25], rs2[24:19], rs1[18:13], preddest[12:7], opcode[6:0]]
            pred_dest = self.parse_predicate(operands[0])
            rs1 = self.parse_register(operands[1])
            rs2 = self.parse_register(operands[2])
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   self.to_binary(predicate, 5) + self.to_binary(rs2, 6) + 
                   self.to_binary(rs1, 6) + self.to_binary(pred_dest, 6) + op_bits)
        
        elif opcode in U_TYPE:
            # U-type: [end[31], start[30], pred[29:25], imm[24:13], rd[12:7], opcode[6:0]]
            rd = self.parse_register(operands[0])
            imm = self.parse_immediate(operands[1])
            self.check_immediate_fits(imm, 12, signed=False)
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   self.to_binary(predicate, 5) + self.to_binary(imm, 12, signed=False) + 
                   self.to_binary(rd, 6) + op_bits)
        
        elif opcode in C_TYPE:
            # C-type (CSRR): [end, start, pred, x[24:23], rs2[22:19], rs1[18:13], rd[12:7], opcode]
            # csr1 = {rs2[3:0], rs1[5:0]} - 10 bit CSR address
            rd = self.parse_register(operands[0])
            csr = self.parse_csr(operands[1])
            if csr < 0 or csr > 1023:
                raise ValueError(f"CSR address {csr} out of range (0-1023)")
            # Split CSR into rs2[3:0] and rs1[5:0]
            rs1_bits = csr & 0x3F  # Lower 6 bits
            rs2_bits = (csr >> 6) & 0xF  # Upper 4 bits
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   self.to_binary(predicate, 5) + '00' + self.to_binary(rs2_bits, 4) + 
                   self.to_binary(rs1_bits, 6) + self.to_binary(rd, 6) + op_bits)
        
        elif opcode in J_TYPE:
            # J-type: [end, start, imm[29:13], rd[12:7], opcode[6:0]]
            # Note: No predication for JAL
            rd = self.parse_register(operands[0])
            # Handle label or immediate
            if operands[1] in self.labels:
                target = self.labels[operands[1]]
                imm = target - addr  # PC-relative offset
            else:
                imm = self.parse_immediate(operands[1])
            self.check_immediate_fits(imm, 17, signed=True)
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   self.to_binary(imm, 17) + self.to_binary(rd, 6) + op_bits)
        
        elif opcode in P_TYPE:
            # P-type: [end, start, pred, rs2[24:19], rs1[18:13], x[12:7], opcode[6:0]]
            # Note: No predication for these instructions
            rs1 = self.parse_register(operands[0])
            rs2 = self.parse_register(operands[1])
            return (self.to_binary(end, 1) + self.to_binary(start, 1) + 
                   '00000' + self.to_binary(rs2, 6) + 
                   self.to_binary(rs1, 6) + '000000' + op_bits)
        
        elif opcode in H_TYPE:
            # H-type (HALT): [end=1, start=0, 1s[29:7], opcode[6:0]]
            return '10' + '1' * 23 + op_bits
        
        else:
            raise ValueError(f"Unknown instruction format for {opcode}")
    
    def assemble(self, input_file: str, output_file: str, format: str = 'bin'):
        """Assemble input file to output file"""
        with open(input_file, 'r') as f:
            lines = f.readlines()
        
        # Reset state
        self.labels.clear()
        self.instructions.clear()
        self.pc = 0x0000
        
        # Two-pass assembly
        self.first_pass(lines)
        machine_code = self.second_pass()
        
        # Write output
        with open(output_file, 'w') as f:
            if format == 'bin':
                for code in machine_code:
                    f.write(code + '\n')
            elif format == 'hex':
                for code in machine_code:
                    hex_val = hex(int(code, 2))[2:].zfill(8)
                    f.write(hex_val + '\n')


def main():
    if len(sys.argv) < 3:
        print("Usage: python assembler.py <input.s> <output.bin> [format] [opcode_file]")
        print("  format: 'bin' (default) or 'hex'")
        print("  opcode_file: path to opcodes file (default: 'opcodes.txt')")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    format = sys.argv[3] if len(sys.argv) > 3 else 'bin'
    opcode_file = sys.argv[4] if len(sys.argv) > 4 else 'opcodes.txt'
    
    try:
        opcodes = load_opcodes(opcode_file)
        print(f"Loaded {len(opcodes)} opcodes from {opcode_file}")
        
        assembler = Assembler(opcodes)
        assembler.assemble(input_file, output_file, format)
        print(f"Assembly successful! Output written to {output_file}")
        print(f"Labels found: {assembler.labels}")
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()