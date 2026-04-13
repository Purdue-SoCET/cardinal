// mshr_table.sv
// Per-bank Miss Status Holding Register (MSHR) table.
//
// Coalescing of multiple thread requests into dest_mask is done upstream
// before the alloc call — this table stores and completes entries only.
//
// Each entry holds:
//   valid      – entry in use
//   address    – 32-bit miss address
//   dest_mask  – pre-coalesced bitmask of all destination threads
//   tag        – 5-bit requestor tag
//
// Operations (evaluated combinationally; state updates on posedge clk):
//
//   alloc    – allocate a free entry for a new miss.
//              Inputs : alloc_en, alloc_addr, alloc_tag, alloc_dest_mask
//              Outputs: alloc_entry_id, alloc_valid (1 = success, 0 = full)
//
//   complete – an entry is filled; produce the outgoing flit.
//              Inputs : complete_en, complete_entry_id, complete_data,
//                       complete_error
//              Output : complete_flit (valid combinationally same cycle;
//                       caller latches it then pulses free_en)
//
//   free     – release an entry.
//              Inputs : free_en, free_entry_id

`timescale 1ns/1ps

import clos_pkg::*;

module mshr_table #(
  parameter int unsigned BANK_ID     = 0,
  parameter int unsigned NUM_ENTRIES = 16
) (
  input  logic clk,
  input  logic rst_n,

  // ---- Alloc port ----------------------------------------------------------
  input  logic                             alloc_en,
  input  logic [31:0]                      alloc_addr,
  input  logic [4:0]                       alloc_tag,
  input  logic [DEST_W-1:0]               alloc_dest_mask,   // pre-coalesced
  output logic [$clog2(NUM_ENTRIES)-1:0]   alloc_entry_id,
  output logic                             alloc_valid,       // 1 = allocated OK

  // ---- Complete port -------------------------------------------------------
  input  logic                             complete_en,
  input  logic [$clog2(NUM_ENTRIES)-1:0]   complete_entry_id,
  input  logic [DATA_W-1:0]               complete_data,
  input  logic [ERR_W-1:0]                complete_error,
  output flit_t                            complete_flit,

  // ---- Free port -----------------------------------------------------------
  input  logic                             free_en,
  input  logic [$clog2(NUM_ENTRIES)-1:0]   free_entry_id
);

  // ---------------------------------------------------------------------------
  // MSHR entry storage
  // ---------------------------------------------------------------------------
  logic [NUM_ENTRIES-1:0]    entry_valid_q;
  logic [31:0]               entry_addr_q    [NUM_ENTRIES];
  logic [DEST_W-1:0]         entry_dest_q    [NUM_ENTRIES];
  logic [4:0]                entry_tag_q     [NUM_ENTRIES];

  // ---------------------------------------------------------------------------
  // Alloc: find first free entry (priority encoder)
  // ---------------------------------------------------------------------------
  always_comb begin
    alloc_valid    = 1'b0;
    alloc_entry_id = '0;
    for (int i = NUM_ENTRIES-1; i >= 0; i--) begin
      if (!entry_valid_q[i]) begin
        alloc_valid    = 1'b1;
        alloc_entry_id = i[$clog2(NUM_ENTRIES)-1:0];
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Complete: build the outgoing flit from entry dest_mask + supplied data/error
  // ---------------------------------------------------------------------------
  always_comb begin
    complete_flit           = '0;
    complete_flit.dest_mask = entry_dest_q[complete_entry_id];
    complete_flit.data      = complete_data;
    complete_flit.reserved  = '0;
    complete_flit.error     = complete_error;
  end

  // ---------------------------------------------------------------------------
  // State updates
  // ---------------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      entry_valid_q <= '0;
      for (int i = 0; i < NUM_ENTRIES; i++) begin
        entry_addr_q[i] <= '0;
        entry_dest_q[i] <= '0;
        entry_tag_q[i]  <= '0;
      end
    end else begin

      // --- Alloc ---
      if (alloc_en && alloc_valid) begin
        entry_valid_q[alloc_entry_id] <= 1'b1;
        entry_addr_q [alloc_entry_id] <= alloc_addr;
        entry_tag_q  [alloc_entry_id] <= alloc_tag;
        entry_dest_q [alloc_entry_id] <= alloc_dest_mask;
      end

      // --- Free ---
      if (free_en) begin
        entry_valid_q[free_entry_id] <= 1'b0;
        entry_dest_q [free_entry_id] <= '0;
        entry_addr_q [free_entry_id] <= '0;
        entry_tag_q  [free_entry_id] <= '0;
      end

      // Alloc and Free to same entry in same cycle: alloc wins.
      if (alloc_en && alloc_valid && free_en && (alloc_entry_id == free_entry_id)) begin
        entry_valid_q[alloc_entry_id] <= 1'b1;
      end
    end
  end

endmodule : mshr_table
