from latch_forward_stage import LatchIF, ForwardingIF, Stage
from typing import Any

### SIMPLEST SCHEME, NO FORWARDING BETWEEN STAGES ###

# class Stage0(Stage):
#     def compute(self, input_data: Any) -> Any: # only stage with explicit input
#         if self.forward_if_read and self.forward_if_read.wait:
#             print(f"[{self.name}] Stalled due to wait from next stage.")
#             return None
#         if self.behind_latch and not self.behind_latch.valid:
#             return None
        
#         fwd_val = self.forward_if_read.pop() if self.forward_if_read else None
#         if fwd_val is not None:
#             output = input_data + fwd_val + 100 # place holder logic for testing
#         else:
#             output = input_data + 100

#         print(f"[{self.name}] Computed output: {output!r} (forward value: {fwd_val!r})")

#         self.send_output(output)
        
    
# class Stage1(Stage):
#     def compute(self) -> Any:
#         if self.forward_if_read and self.forward_if_read.wait:
#             print(f"[{self.name}] Stalled due to wait from next stage.")
#             return None
#         if self.behind_latch and not self.behind_latch.valid:
#             return None
        
#         input_to_stage = self.behind_latch.pop()

#         fwd_val = self.forward_if_read.pop() if self.forward_if_read else None
#         if fwd_val is not None:
#             output = input_to_stage + fwd_val + 100 # place holder logic for testing
#         else: 
#             output = input_to_stage + 100

#         print(f"[{self.name}] Computed output: {output!r} (forward value: {fwd_val!r})")

#         self.send_output(output)

    
# class Stage2(Stage):
#     def compute(self) -> Any:
#         if self.forward_if_read and self.forward_if_read.wait:
#             print(f"[{self.name}] Stalled due to wait from next stage.")
#             return None
#         if self.behind_latch and not self.behind_latch.valid:
#             return None
        
#         input_to_stage = self.behind_latch.pop()
        
#         output = input_to_stage + 100 # place holder logic for testing
#         print(f"[{self.name}] Computed output: {output!r}")

#         return output
    
### MORE COMPLEX SCHEME, STAGE 1 FOWARDS BACK TO STAGE 0, AND STAGE 2 FORWARDS BACK TO STAGE 1 ###

# class Stage0(Stage):
#     def compute(self, input_data: Any) -> Any: # only stage with explicit input
#         if self.forward_if_read and self.forward_if_read.wait:
#             print(f"[{self.name}] Stalled due to wait from next stage.")
#             return None
#         if self.behind_latch and not self.behind_latch.valid:
#             return None
        
#         fwd_val = self.forward_if_read.pop() if self.forward_if_read else None
#         if fwd_val is not None:
#             output = input_data + fwd_val + 100 # place holder logic for testing
#         else:
#             output = input_data + 100

#         print(f"[{self.name}] Computed output: {output!r} (forward value: {fwd_val!r})")

#         self.send_output(output)
        
    
# class Stage1(Stage):
#     def compute(self) -> Any:
#         if self.forward_if_read and self.forward_if_read.wait:
#             print(f"[{self.name}] Stalled due to wait from next stage.")
#             return None
#         if self.behind_latch and not self.behind_latch.valid:
#             return None
        
#         input_to_stage = self.behind_latch.pop()

#         fwd_val = self.forward_if_read.pop() if self.forward_if_read else None
#         if fwd_val is not None:
#             output = input_to_stage + fwd_val + 100 # place holder logic for testing
#         else: 
#             output = input_to_stage + 100

#         print(f"[{self.name}] Computed output: {output!r} (forwarded value: {fwd_val!r})")
        
#         self.forward_signals(100)
#         self.send_output(output)

    
# class Stage2(Stage):
#     def compute(self) -> Any:
#         if self.forward_if_read and self.forward_if_read.wait:
#             print(f"[{self.name}] Stalled due to wait from next stage.")
#             return None
#         if self.behind_latch and not self.behind_latch.valid:
#             return None
        
#         input_to_stage = self.behind_latch.pop()
        
#         output = input_to_stage + 100 # place holder logic for testing
#         print(f"[{self.name}] Computed output: {output!r}")

#         self.forward_signals(200)
#         return output

### EVEN MORE COMPLEX SCHEME, MULTIPLE STAGES MAY FORWARD INTO A SINGLE STAGE NOW, AS WELL AS ONE STAGE MAY FORWARD INTO MULTIPLE STAGES ###
### FOR THIS EXAMPLE, SAY STAGE 2 FORWARDS BACK TO STAGE 1, AND BOTH STAGE 2 AND STAGE 1 FORWARD BACK TO STAGE 0 ###

class Stage0(Stage):
    def compute(self, input_data: Any) -> Any: # only stage with explicit input
        if self.forward_ifs_read and self.forward_ifs_read["Forward1to0"].wait:
            print(f"[{self.name}] Stalled due to wait from next stage.")
            return None
        if self.behind_latch and not self.behind_latch.valid:
            return None
        
        # fwd_val = self.forward_if_read.pop() if self.forward_if_read else None
        fwd_vals = [val for fwd_if in self.forward_ifs_read.values() if (val := fwd_if.pop()) is not None]
        # if fwd_val is not None:
        #     output = input_data + fwd_val + 100 # place holder logic for testing
        # else:
        #     output = input_data + 100
        output = input_data + 100

        print(f"[{self.name}] Computed output: {output!r} (forward value: {fwd_vals!r})")

        self.send_output(output)
        
    
class Stage1(Stage):
    def compute(self) -> Any:
        if self.forward_ifs_read and self.forward_ifs_read["Forward2to1"].wait:
            print(f"[{self.name}] Stalled due to wait from next stage.")
            return None
        if self.behind_latch and not self.behind_latch.valid:
            return None
        
        input_to_stage = self.behind_latch.pop()

        # fwd_val = self.forward_if_read.pop() if self.forward_if_read else None
        fwd_vals = [val for fwd_if in self.forward_ifs_read.values() if (val := fwd_if.pop()) is not None]
        # if fwd_val is not None:
        #     output = input_to_stage + fwd_val + 100 # place holder logic for testing
        # else: 
        #     output = input_to_stage + 100
        output = input_to_stage + 100

        print(f"[{self.name}] Computed output: {output!r} (forwarded value: {fwd_vals!r})")
        
        self.forward_signals(stage1_forward_to_stage0.name, 100)
        self.send_output(output)

    
class Stage2(Stage):
    def compute(self) -> Any:
        if self.forward_ifs_read and self.forward_ifs_read["Forward3to2"].wait:
            print(f"[{self.name}] Stalled due to wait from next stage.")
            return None
        if self.behind_latch and not self.behind_latch.valid:
            return None
        
        input_to_stage = self.behind_latch.pop()
        
        output = input_to_stage + 100 # place holder logic for testing
        print(f"[{self.name}] Computed output: {output!r}")

        self.forward_signals(stage2_forward_to_stage1.name, 150)
        self.forward_signals(stage2_forward_to_stage0.name, 200)
        return output

    
### TESTING ###
# Simple scheme. Stages 0, 1, and 2 are connected, with 1 forwarding back to 0 and 2 forwarding back to 1.

stage0_stage1_latch = LatchIF(name = "Latch0to1")
stage1_stage2_latch = LatchIF(name = "Latch1to2")
stage1_forward_to_stage0 = ForwardingIF(name = "Forward1to0")
stage2_forward_to_stage1 = ForwardingIF(name = "Forward2to1")
stage2_forward_to_stage0 = ForwardingIF(name = "Forward2to0")

stage0 = Stage0(
    name = "Stage0",
    behind_latch = None,
    ahead_latch = stage0_stage1_latch,
    forward_ifs_read = {stage2_forward_to_stage0.name: stage2_forward_to_stage0, stage1_forward_to_stage0.name: stage1_forward_to_stage0},
    forward_ifs_write = None
)

stage1 = Stage1(
    name = "Stage1",
    behind_latch = stage0_stage1_latch,
    ahead_latch = stage1_stage2_latch,
    forward_ifs_read = {stage2_forward_to_stage1.name: stage2_forward_to_stage1},
    forward_ifs_write = {stage1_forward_to_stage0.name: stage1_forward_to_stage0}
)

stage2 = Stage2(
    name = "Stage2",
    behind_latch = stage1_stage2_latch,
    ahead_latch = None,
    forward_ifs_read = None,
    forward_ifs_write = {stage2_forward_to_stage1.name: stage2_forward_to_stage1, stage2_forward_to_stage0.name : stage2_forward_to_stage0}
)

input_values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

for cycle in range(10):
    print(f"\n=== Cycle {cycle} ===")

    stage2.compute()
    stage1.compute()
    stage0.compute(input_values[cycle])