// egress_switch.sv
// 3-stage Clos network – egress switch (8 inputs × 4 thread outputs).
//
// Each middle switch input carries a flit whose dest_mask is already masked
// to the 4 bits for this egress group.  At most one flit targets any given
// thread output per cycle (unique-destination guarantee from ingress arbiter).
//
// For each thread output t, TID = BASE_THREAD + t is a compile-time constant
// (via genvar + localparam).  The bit-select dest_mask[TID] is therefore a
// fixed wire tap — zero logic.
//
// Within-group multicast: one flit arrives from one middle switch and is
// fanned out to all targeted thread outputs simultaneously.
//
// Registered outputs, back-pressure via valid/ready.
// thread_rx_flit = flit[THREAD_FLIT_W-1:0] = {data[31:0], error[1:0]}

`timescale 1ns/1ps

import clos_pkg::*;

module egress_switch #(
  parameter int unsigned SWITCH_ID   = 0,
  parameter int unsigned BASE_THREAD = SWITCH_ID * THREADS_PER_EGRESS
) (
  input  logic clk,
  input  logic rst_n,

  // ---- middle-switch inputs (8 ports) --------------------------------------
  input  logic  mid_valid [NUM_MIDDLE],
  output logic  mid_ready [NUM_MIDDLE],
  input  flit_t mid_flit  [NUM_MIDDLE],

  // ---- thread outputs (4 ports) --------------------------------------------
  output logic                     thr_valid [THREADS_PER_EGRESS],
  input  logic                     thr_ready [THREADS_PER_EGRESS],
  output logic [THREAD_FLIT_W-1:0] thr_flit  [THREADS_PER_EGRESS]
);

  // ---------------------------------------------------------------------------
  // Per-thread pipeline — one generate block per thread output t.
  //
  // TID = BASE_THREAD + t is a compile-time constant, so
  // mid_flit[m].dest_mask[TID] is a fixed wire tap into the flit bus.
  // ---------------------------------------------------------------------------
  generate
    for (genvar t = 0; t < THREADS_PER_EGRESS; t++) begin : gen_thread

      localparam int unsigned TID = BASE_THREAD + t;

      logic  in_valid;
      flit_t in_flit;

      // -- Combinational: which middle input (if any) targets this thread -----
      always_comb begin
        in_valid = 1'b0;
        in_flit  = '0;
        for (int m = 0; m < NUM_MIDDLE; m++) begin
          if (mid_valid[m] && mid_flit[m].dest_mask[TID]) begin
            in_valid = 1'b1;
            in_flit  = mid_flit[m];
          end
        end
      end

      // -- Pipeline register --------------------------------------------------
      logic  out_valid_q;
      flit_t out_flit_q;

      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
          out_valid_q <= 1'b0;
          out_flit_q  <= '0;
        end else if (!out_valid_q || thr_ready[t]) begin
          out_valid_q <= in_valid;
          if (in_valid)
            out_flit_q <= in_flit;
        end
      end

      // -- Output assignment — dest field stripped ----------------------------
      assign thr_valid[t] = out_valid_q;
      assign thr_flit[t]  = out_flit_q[THREAD_FLIT_W-1:0];

    end
  endgenerate

  // ---------------------------------------------------------------------------
  // Back-pressure to middle switches.
  // Middle input m is ready when all thread outputs it targets are free.
  // TID is a compile-time constant, so dest_mask[TID] is a fixed wire tap.
  // ---------------------------------------------------------------------------
  generate
    for (genvar m = 0; m < NUM_MIDDLE; m++) begin : gen_mid_ready

      always_comb begin
        mid_ready[m] = 1'b1;
        for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
          automatic int unsigned tid = BASE_THREAD + t;
          if (mid_valid[m] && mid_flit[m].dest_mask[tid])
            if (gen_thread[t].out_valid_q && !thr_ready[t])
              mid_ready[m] = 1'b0;
        end
      end

    end
  endgenerate

endmodule : egress_switch
