// middle_switch.sv
// 3-stage Clos network – middle switch (8 inputs × 8 outputs).
//
// With diagonal routing from the ingress stage, input port i of middle
// switch SWITCH_ID always carries a flit destined for egress switch
//   e = (SWITCH_ID - i + NUM_EGRESS) % NUM_EGRESS
//
// Because each input targets a distinct egress output, there is zero
// contention — no arbitration is needed.  The switch is a set of 8
// independent pipeline registers, one per output port, each fed from
// its unique fixed source input.
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
  // Diagonal routing: input i → output e = (SWITCH_ID - i + NUM_EGRESS) % NUM_EGRESS
  // Equivalently:     output e ← input i = (SWITCH_ID - e + NUM_INGRESS) % NUM_INGRESS
  // ---------------------------------------------------------------------------

  logic  out_valid_q [NUM_EGRESS];
  flit_t out_flit_q  [NUM_EGRESS];

  // ---------------------------------------------------------------------------
  // Registered outputs — one per egress port, fed from fixed source input
  // ---------------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (int e = 0; e < NUM_EGRESS; e++) begin
        out_valid_q[e] <= 1'b0;
        out_flit_q[e]  <= '0;
      end
    end else begin
      for (int e = 0; e < NUM_EGRESS; e++) begin
        automatic int src = (int'(SWITCH_ID) - e + NUM_INGRESS) % NUM_INGRESS;
        if (!out_valid_q[e] || egr_ready[e]) begin
          out_valid_q[e] <= ing_valid[src];
          if (ing_valid[src])
            out_flit_q[e] <= ing_flit[src];
        end
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Output assignments
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int e = 0; e < NUM_EGRESS; e++) begin
      egr_valid[e] = out_valid_q[e];
      egr_flit[e]  = out_flit_q[e];
    end
  end

  // ---------------------------------------------------------------------------
  // Back-pressure: input i is ready when its target output slot is free
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int i = 0; i < NUM_INGRESS; i++) begin
      automatic int e = (int'(SWITCH_ID) - i + NUM_EGRESS) % NUM_EGRESS;
      ing_ready[i] = !out_valid_q[e] || egr_ready[e];
    end
  end

endmodule : middle_switch
