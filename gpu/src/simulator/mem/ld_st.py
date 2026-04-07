import enum
from typing import Dict, List, Optional
import logging
from bitstring import Bits

from simulator.interfaces import LatchIF, ForwardingIF
from simulator.instruction import Instruction
from simulator.stage import Stage
from common.custom_enums_multi import I_Op, S_Op, H_Op, P_Op
from simulator.execute.functional_sub_unit import FunctionalSubUnit

logger = logging.getLogger(__name__)