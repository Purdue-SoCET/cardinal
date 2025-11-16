# Custom ISA Assembler

A two-pass assembler for TWIG instruction set architecture with support for predication, packet control, and multiple instruction formats.

## TL;DR

```bash
# Quick start
python assembler.py program.s output.bin

# Basic assembly syntax
org(0x0040) #set address at any point. following instructions are always pc = pc+4 until next org() directive

add  x1, x2, x3              # R-type: rd, rs1, rs2
addi x1, x2, 10              # I-type: rd, rs1, imm (6-bit)
lw   x1, 4(x2)               # Load: rd, imm(rs1)
sw   x3, 8(x4)               # Store: rs2, imm(rs1)
beq  p1, x5, x6              # Branch: pred_dest, rs1, rs2
jal  x1, label               # Jump to label

# Optional: predicate, start bit, end bit (defaults: 0, 0, 1)
add  x1, x2, x3, p5, 1, 0    # With predication and packet control

# Labels and directives
loop:                        # Define label
    org 0x1000              # Set PC to address
    addi x1, x1, -1
    bne p1, x1, x0
    jpnz p1, loop

# Features: 64 registers (x0-x63), 32 predicates (p0-p31), little-endian encoding
```

There have been syntax changes (lw, sw), but the old syntax should still be supported.

Instruction related changes are on the teal card update log. 

This is not conclusively tested because it's too tedious to match 32 bits for a bajillion edge cases. There may be bugs don't kill me.

## The rest of this readme was created by an llm and not completely verified. I know you're not reading all of it anyway

## Features

- **Two-pass assembly**: First pass resolves labels and addresses, second pass generates machine code
- **Predication support**: 5-bit predicate field (p0-p31) for conditional execution
- **Packet control**: Start and end bits for instruction bundling
- **Little-endian encoding**: Opcode at rightmost bits [6:0]
- **6-bit registers**: Supports x0-x63 register file
- **Flexible addressing**: Labels, PC-relative branches, and memory operands
- **Multiple output formats**: Binary or hexadecimal machine code
- **Configurable opcodes**: Load instruction set from external file

## Installation

No installation required. Just ensure you have Python 3.6+ installed.

```bash
python3 --version  # Check Python version
```

## Usage

### Basic Usage

```bash
python assembler.py <input.s> <output.bin> [format] [opcode_file]
```

**Arguments:**
- `input.s` - Input assembly file (required)
- `output.bin` - Output machine code file (required)
- `format` - Output format: `bin` (default) or `hex` (optional)
- `opcode_file` - Path to opcodes file, default: `opcodes.txt` (optional)

### Examples

```bash
# Assemble to binary (default)
python assembler.py program.s output.bin

# Assemble to hexadecimal
python assembler.py program.s output.hex hex

# Use custom opcode file
python assembler.py program.s output.bin bin my_opcodes.txt
```

## Assembly Language Syntax

### Registers

- **General purpose**: `x0` to `x63` (6-bit addressing)
- **Predicates**: `p0` to `p31` or just `0` to `31` (5-bit addressing)

### Comments

Both `#` and `;` style comments are supported:

```assembly
add x1, x2, x3      # This is a comment
sub x4, x5, x6      ; This is also a comment
```

### Labels

Define labels with a colon. Labels can be on their own line or inline:

```assembly
loop:                   # Label on its own line
    addi x1, x1, -1
    
start: add x2, x0, x0  # Inline label
```

### Memory Addressing Directive

Use `org` to set the current program counter:

```assembly
    org 0x1000      # Next instruction will be at address 0x1000
    add x1, x2, x3
```

### Instruction Formats

#### R-Type (Register-Register)
```assembly
add  rd, rs1, rs2           # Basic form
add  rd, rs1, rs2, p5       # With predicate
add  rd, rs1, rs2, p5, 1, 0 # With predicate, start=1, end=0
```

**R-Type Instructions**: `add`, `sub`, `mul`, `div`, `and`, `or`, `xor`, `slt`, `sltu`, `addf`, `subf`, `mulf`, `divf`, `sll`, `srl`, `sra`

#### I-Type (Register-Immediate)
```assembly
addi rd, rs1, imm           # Immediate (6-bit)
addi rd, rs1, imm, p3       # With predicate
```

**I-Type Instructions**: `addi`, `subi`, `xori`, `ori`, `slti`, `sltiu`, `slli`, `srli`, `srai`

**Immediate range**: -32 to 31 (6-bit signed)

#### Load Instructions (I-Type with Memory Syntax)
```assembly
lw  rd, imm(rs1)            # Load word
lh  rd, imm(rs1)            # Load halfword
lb  rd, imm(rs1)            # Load byte
lw  rd, 10(x5), p2          # With predicate
```

#### Store Instructions (S-Type)
```assembly
sw  rs2, imm(rs1)           # Store word
sh  rs2, imm(rs1)           # Store halfword
sb  rs2, imm(rs1)           # Store byte
sw  x3, -4(x10), p1         # With predicate
```

**Immediate range**: -32 to 31 (6-bit signed)

#### F-Type (Unary Operations)
```assembly
isqrt rd, rs1               # Inverse square root
sin   rd, rs1               # Sine
cos   rd, rs1               # Cosine
itof  rd, rs1               # Integer to float
ftoi  rd, rs1               # Float to integer
```

#### B-Type (Branch/Predicate Write)
```assembly
beq  pred_dest, rs1, rs2    # Set predicate if equal
bne  pred_dest, rs1, rs2    # Set predicate if not equal
blt  pred_dest, rs1, rs2    # Set predicate if less than
bge  pred_dest, rs1, rs2    # Set predicate if greater/equal
```

**B-Type Instructions**: `beq`, `bne`, `bge`, `bgeu`, `blt`, `bltu`, `beqf`, `bnef`, `bgef`, `bltf`

**Note**: These write to predicate registers, not PC-relative branches

#### U-Type (Upper Immediate)
```assembly
lui   rd, imm               # Load upper immediate
lli   rd, imm               # Load lower immediate
lmi   rd, imm               # Load middle immediate
auipc rd, imm               # Add upper immediate to PC
```

**Immediate range**: 0 to 4095 (12-bit unsigned)

#### J-Type (Jump)
```assembly
jal  rd, label              # Jump to label
jal  rd, offset             # Jump with immediate offset
jalr rd, imm(rs1)           # Jump to register + offset
```

**Immediate range**: -65536 to 65535 (17-bit signed for jal, 6-bit for jalr)

#### P-Type (Predicate Operations)
```assembly
jpnz rs1, rs2               # Jump if predicate not zero
prr  rs1, rs2               # Predicate read
prw  rs1, rs2               # Predicate write
```

#### H-Type (Halt)
```assembly
halt                        # Halt execution
```

### Optional Operands (Predication and Packet Control)

All instructions except `halt`, `prw`, `prr`, `jpnz`, `jal`, and `jalr` support optional operands:

1. **Predicate** (default: 0) - Execute only if predicate register is true
2. **Start bit** (default: 0) - First instruction in packet
3. **End bit** (default: 1) - Last instruction in packet

```assembly
# Syntax variations
add x1, x2, x3              # Uses defaults: pred=0, start=0, end=1
add x1, x2, x3, 5           # pred=5 (or use p5)
add x1, x2, x3, p5          # pred=5 (with 'p' prefix)
add x1, x2, x3, p5, 1       # pred=5, start=1, end=1
add x1, x2, x3, p5, 1, 0    # pred=5, start=1, end=0
```

**Predication**: Instruction only executes if the predicate register is set for the current thread.

**Packet bits**: Used for instruction bundling and parallel execution:
- `start=1` marks the first instruction in a packet
- `end=1` marks the last instruction in a packet

## Complete Example

```assembly
# Simple loop example
    org 0x0000
    lli x1, 10              # x1 = 10
    lli x2, 0               # x2 = 0 (accumulator)
    
loop:
    add x2, x2, x1          # x2 = x2 + x1
    subi x1, x1, 1          # x1 = x1 - 1
    bne p1, x1, x0          # p1 = (x1 != 0)
    jpnz p1, x3             # if (p1) jump to loop (x3 has loop addr)
    
    halt

# Memory operations example
    org 0x1000
    lli x10, 100
    sw x10, 0(x5)           # Store x10 to mem[x5+0]
    lw x11, 0(x5)           # Load from mem[x5+0] to x11
```

## Instruction Encoding

All instructions are 32-bit little-endian with the opcode at bits [6:0]:

```
[31] [30] [29:25] [24:19] [18:13] [12:7] [6:0]
 end start  pred   (varies by instruction type) opcode
```

### Bit Layouts by Type

**R-Type**: `[end, start, pred, rs2, rs1, rd, opcode]`
**I-Type**: `[end, start, pred, imm[6], rs1, rd, opcode]`
**F-Type**: `[end, start, pred, x, rs1, rd, opcode]`
**S-Type**: `[end, start, pred, rs2, rs1, imm[6], opcode]`
**B-Type**: `[end, start, pred, rs2, rs1, preddest, opcode]`
**U-Type**: `[end, start, pred, imm[12], rd, opcode]`
**J-Type**: `[end, start, imm[17], rd, opcode]` (no pred)
**P-Type**: `[end, start, 0, rs2, rs1, x, opcode]` (no pred)
**H-Type**: `[1, 0, 1s, opcode]`

## Opcode File Format

The `opcodes.txt` file should contain mnemonic-to-binary mappings:

```
add     0000000
sub     0000001
addi    0010000
lw      0100000
halt    1111111
```

- Lines starting with `#` are ignored (comments)
- Each line: `mnemonic<whitespace>binary_code`
- Binary codes must be 7 bits

## Error Handling

The assembler will report errors for:

- **Invalid registers**: Register numbers outside 0-63 range
- **Invalid predicates**: Predicate numbers outside 0-31 range
- **Immediate overflow**: Values that don't fit in allocated bits
- **Unknown instructions**: Mnemonics not in opcode file
- **Invalid syntax**: Malformed operands or memory addressing
- **Missing files**: Input file or opcode file not found

## Output Formats

### Binary Format (default)
```
10000000000000000000000001100000
10000000000001100000100010010000
```

Each line is a 32-bit binary instruction.

### Hexadecimal Format
```
80000060
80018490
```

Each line is an 8-character hexadecimal instruction.

## Tips and Best practices

1. **Use labels** instead of hard-coded addresses for jumps
2. **Check immediate ranges** before assembly - the assembler will error on overflow
3. **Use org directives** to organize code sections
4. **Comment your code** liberally for maintainability
5. **Test with small programs** before assembling large codebases
6. **Use predication** to avoid branches and improve parallelism

## Limitations

- Instructions are always 4 bytes (32 bits)
- PC increments by 4 for each instruction
- No macro support
- No support for data sections (`.data`, `.text`)
- No floating-point literal support (use integer representations)