// ingress_switch.sv
// 3-stage Clos network – ingress switch (4 inputs × 8 outputs).
//
// Each bank input carries at most one flit per cycle. The arbiter above
// guarantees no two banks target the same egress group in the same cycle,
// so each output port receives at most one flit — no arbitration needed.
//
// For each bank input, the flit is replicated to every output port whose
// egress group appears in dest_mask (diagonal routing: ingress s sends
// egress group e via output port (s+e) % NUM_MIDDLE).  Each copy has its
// dest_mask masked to only the 4 bits for that egress group.
//
// All outputs are registered (one pipeline stage).

`timescale 1ns/1ps

import clos_pkg::*;

module ingress_switch #(
  parameter int unsigned SWITCH_ID = 0   // 0-7
) (
  input  logic clk,
  input  logic rst_n,

  // ---- bank-side inputs (4 ports) -----------------------------------------
  input  logic              bank_valid [BANKS_PER_INGRESS],
  output logic              bank_ready [BANKS_PER_INGRESS],
  input  flit_t             bank_flit  [BANKS_PER_INGRESS],

  // ---- middle-switch outputs (8 ports) -------------------------------------
  output logic              mid_valid  [NUM_MIDDLE],
  input  logic              mid_ready  [NUM_MIDDLE],
  output flit_t             mid_flit   [NUM_MIDDLE]
);

  // ---------------------------------------------------------------------------
  // Output registers — one per middle switch output port
  // ---------------------------------------------------------------------------
  logic  out_valid_q [NUM_MIDDLE];
  flit_t out_flit_q  [NUM_MIDDLE];

  // ---------------------------------------------------------------------------
  // Combinational: for each output port m, find which bank (if any) targets it.
  // Output m serves egress group e_m = (m - SWITCH_ID + NUM_MIDDLE) % NUM_MIDDLE.
  // At most one bank can target each egress group per cycle (arbiter guarantee).
  // ---------------------------------------------------------------------------
  logic  in_valid  [NUM_MIDDLE];
  flit_t in_flit   [NUM_MIDDLE];

  always_comb begin
    for (int m = 0; m < NUM_MIDDLE; m++) begin
      automatic int e_m = (m - int'(SWITCH_ID) + NUM_MIDDLE) % NUM_MIDDLE;
      automatic logic [THREADS_PER_EGRESS-1:0] grp_mask =
        {THREADS_PER_EGRESS{1'b1}} << (e_m * THREADS_PER_EGRESS);

      in_valid[m] = 1'b0;
      in_flit[m]  = '0;

      for (int i = 0; i < BANKS_PER_INGRESS; i++) begin
        if (bank_valid[i] && |(bank_flit[i].dest_mask & grp_mask)) begin
          in_valid[m]           = 1'b1;
          in_flit[m]            = bank_flit[i];
          in_flit[m].dest_mask  = bank_flit[i].dest_mask & {{(NUM_THREADS-THREADS_PER_EGRESS){1'b0}}, grp_mask};
        end
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Registered outputs
  // ---------------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (int m = 0; m < NUM_MIDDLE; m++) begin
        out_valid_q[m] <= 1'b0;
        out_flit_q[m]  <= '0;
      end
    end else begin
      for (int m = 0; m < NUM_MIDDLE; m++) begin
        if (!out_valid_q[m] || mid_ready[m]) begin
          out_valid_q[m] <= in_valid[m];
          if (in_valid[m])
            out_flit_q[m] <= in_flit[m];
        end
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Output assignments
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int m = 0; m < NUM_MIDDLE; m++) begin
      mid_valid[m] = out_valid_q[m];
      mid_flit[m]  = out_flit_q[m];
    end
  end

  // ---------------------------------------------------------------------------
  // Back-pressure: a bank is ready when all output ports it targets are free.
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int i = 0; i < BANKS_PER_INGRESS; i++) begin
      automatic logic all_free = 1'b1;
      for (int m = 0; m < NUM_MIDDLE; m++) begin
        automatic int e_m = (m - int'(SWITCH_ID) + NUM_MIDDLE) % NUM_MIDDLE;
        automatic logic [THREADS_PER_EGRESS-1:0] grp_mask =
          {THREADS_PER_EGRESS{1'b1}} << (e_m * THREADS_PER_EGRESS);
        if (bank_valid[i] && |(bank_flit[i].dest_mask & grp_mask)) begin
          if (out_valid_q[m] && !mid_ready[m])
            all_free = 1'b0;
        end
      end
      bank_ready[i] = all_free;
    end
  end

endmodule : ingress_switch
