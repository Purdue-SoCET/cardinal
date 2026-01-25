# A simple wrapper on all the shared state within the gpu

from dataclasses import dataclass
from reg_file import RegFile, PredicateRegFile
from mem import Mem

@dataclass
class State:
    memory: Mem
    rfile: RegFile
    pfile: PredicateRegFile