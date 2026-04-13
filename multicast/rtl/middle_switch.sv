// middle_switch.sv
// 3-stage Clos network – middle switch (8 inputs × 8 outputs).
//
// Diagonal routing from the ingress stage guarantees that input port i
// always carries a flit destined for exactly one egress output:
//   egress = (SWITCH_ID - i + NUM_EGRESS) & (NUM_EGRESS - 1)
//
// Equivalently, egress output port e is fed by a fixed source input:
//   src = (SWITCH_ID - e + NUM_INGRESS) & (NUM_INGRESS - 1)
//       = (SWITCH_ID + NUM_INGRESS - e) & (NUM_INGRESS - 1)
//
// Because SRC is a compile-time constant for each output port e
// (via genvar + localparam), the input selection is pure wiring —
// no mux logic, just a wire rename.  No arbitration is needed.
//
// Registered outputs, back-pressure via valid/ready.

`timescale 1ns/1ps

import clos_pkg::*;

module middle_switch #(
  parameter int unsigned SWITCH_ID = 0   // 0-7
) (
  input  logic clk,
  input  logic rst_n,

  // ---- ingress-switch inputs (8 ports, one from each ingress switch) -------
  input  logic  ing_valid [NUM_INGRESS],
  output logic  ing_ready [NUM_INGRESS],
  input  flit_t ing_flit  [NUM_INGRESS],

  // ---- egress-switch outputs (8 ports, one to each egress switch) ----------
  output logic  egr_valid [NUM_EGRESS],
  input  logic  egr_ready [NUM_EGRESS],
  output flit_t egr_flit  [NUM_EGRESS]
);

  // ---------------------------------------------------------------------------
  // One pipeline register per egress output port.
  // For each port e, SRC is the fixed ingress input that feeds it —
  // a compile-time constant, so the assignment is a pure wire connection.
  //
  // Each SRC value is unique across all e (bijection), so ing_ready[SRC]
  // is driven by exactly one generate iteration — no multiple-driver conflict.
  // ---------------------------------------------------------------------------
  generate
    for (genvar e = 0; e < NUM_EGRESS; e++) begin : gen_egr_port

      localparam int unsigned SRC = (SWITCH_ID + NUM_INGRESS - e) & (NUM_INGRESS - 1);

      logic  out_valid_q;
      flit_t out_flit_q;

      // -- Pipeline register --------------------------------------------------
      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
          out_valid_q <= 1'b0;
          out_flit_q  <= '0;
        end else if (!out_valid_q || egr_ready[e]) begin
          out_valid_q <= ing_valid[SRC];
          if (ing_valid[SRC])
            out_flit_q <= ing_flit[SRC];
        end
      end

      // -- Output and back-pressure assignments (pure wires) ------------------
      assign egr_valid[e]   = out_valid_q;
      assign egr_flit[e]    = out_flit_q;
      assign ing_ready[SRC] = !out_valid_q || egr_ready[e];

    end
  endgenerate

endmodule : middle_switch
