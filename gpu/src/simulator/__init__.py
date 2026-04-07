"""
GPU Simulator Package

A cycle-accurate GPU simulator with comprehensive pipeline modeling.
"""

__version__ = "0.1.0"

# Expose key classes at package level for easier imports
from .interfaces import LatchIF, ForwardingIF
from .instruction import Instruction
from .stage import Stage
from .warp import Warp, WarpGroup, WarpState
from .mem_types import MemRequest, PredRequest, DecodeType, ICacheEntry, FetchRequest
from .utils.data_structures.circular_buffer import CircularBuffer
from .utils.data_structures.compact_queue import CompactQueue
from .utils.data_structures.stack import Stack

